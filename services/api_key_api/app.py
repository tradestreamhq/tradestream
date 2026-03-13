"""
API Key Management REST API — RMM Level 2.

Provides endpoints to create, list, and revoke API keys,
plus middleware for API key authentication with per-key
permissions and rate limiting.
"""

import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Request
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

LIVE_PREFIX = "ts_live_"
TEST_PREFIX = "ts_test_"
KEY_LENGTH = 32


# --- Request DTOs ---


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Key name")
    permissions: List[str] = Field(
        ..., min_length=1, description="List of permissions"
    )
    expires_at: Optional[str] = Field(
        None, description="Expiry timestamp (ISO format)"
    )
    environment: str = Field(
        "live", description="Environment: 'live' or 'test'", pattern="^(live|test)$"
    )
    rate_limit_per_minute: int = Field(
        60, ge=1, le=10000, description="Rate limit per minute"
    )


# --- Key generation & hashing ---
# Uses SHA-256 with a random salt. API keys are high-entropy secrets
# (32 bytes of randomness), so SHA-256 is appropriate here.


def _hash_key(key: str, salt: str) -> str:
    """Hash an API key with SHA-256 and a salt."""
    return hashlib.sha256(f"{salt}:{key}".encode()).hexdigest()


def generate_api_key(environment: str = "live") -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, prefix, key_hash).

    The key_hash is formatted as 'salt$hash' for storage.
    """
    prefix = LIVE_PREFIX if environment == "live" else TEST_PREFIX
    random_part = secrets.token_urlsafe(KEY_LENGTH)
    full_key = f"{prefix}{random_part}"
    salt = secrets.token_hex(16)
    hashed = _hash_key(full_key, salt)
    key_hash = f"{salt}${hashed}"
    return full_key, prefix, key_hash


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored salted SHA-256 hash."""
    try:
        salt, expected_hash = stored_hash.split("$", 1)
    except ValueError:
        return False
    actual_hash = _hash_key(provided_key, salt)
    return hmac.compare_digest(actual_hash, expected_hash)


# --- Rate limiter (in-memory, per-key) ---


class RateLimiter:
    """Simple sliding-window rate limiter per API key."""

    def __init__(self):
        self._windows: Dict[str, List[float]] = {}

    def is_allowed(self, key_id: str, limit: int) -> bool:
        now = time.monotonic()
        window_start = now - 60.0
        timestamps = self._windows.get(key_id, [])
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= limit:
            self._windows[key_id] = timestamps
            return False
        timestamps.append(now)
        self._windows[key_id] = timestamps
        return True


# Global rate limiter instance
_rate_limiter = RateLimiter()


# --- API Key Auth Middleware ---


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that authenticates requests using API keys from the database."""

    HEALTH_PATHS = frozenset({"/health", "/ready", "/api/health"})

    def __init__(self, app, db_pool: asyncpg.Pool):
        super().__init__(app)
        self.db_pool = db_pool

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.HEALTH_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "Missing API key"}},
            )

        # Extract prefix for efficient lookup
        prefix = None
        for p in (LIVE_PREFIX, TEST_PREFIX):
            if api_key.startswith(p):
                prefix = p
                break

        if not prefix:
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key format"}},
            )

        # Look up candidate keys by prefix
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, key_hash, permissions, expires_at,
                           is_revoked, rate_limit_per_minute
                    FROM api_keys
                    WHERE key_prefix = $1 AND is_revoked = FALSE
                    """,
                    prefix,
                )
        except Exception as e:
            logger.error("DB error during API key lookup: %s", e)
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "SERVER_ERROR", "message": "Internal server error"}},
            )

        # Verify against stored hashes
        matched_key = None
        for row in rows:
            if verify_api_key(api_key, row["key_hash"]):
                matched_key = row
                break

        if not matched_key:
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key"}},
            )

        # Check expiry
        if matched_key["expires_at"] and matched_key["expires_at"].replace(
            tzinfo=timezone.utc
        ) < datetime.now(timezone.utc):
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "API key has expired"}},
            )

        # Rate limiting
        key_id = str(matched_key["id"])
        if not _rate_limiter.is_allowed(key_id, matched_key["rate_limit_per_minute"]):
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMITED", "message": "Rate limit exceeded"}},
            )

        # Update usage stats (fire-and-forget)
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE api_keys
                    SET request_count = request_count + 1,
                        last_used_at = NOW()
                    WHERE id = $1
                    """,
                    matched_key["id"],
                )
        except Exception as e:
            logger.warning("Failed to update API key usage: %s", e)

        # Attach key info to request state
        request.state.api_key_id = key_id
        request.state.api_key_permissions = list(matched_key["permissions"])

        return await call_next(request)


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the API Key Management FastAPI application."""
    app = FastAPI(
        title="API Key Management API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/api-keys",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("api-key-api", check_deps))

    router = APIRouter(tags=["API Keys"])

    @router.post("", status_code=201)
    async def create_api_key(body: CreateApiKeyRequest):
        """Generate a new API key."""
        full_key, prefix, key_hash = generate_api_key(body.environment)

        expires_at = None
        if body.expires_at:
            try:
                expires_at = datetime.fromisoformat(body.expires_at)
            except ValueError:
                return validation_error("Invalid expires_at format. Use ISO format.")

        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO api_keys
                        (name, key_prefix, key_hash, permissions, expires_at,
                         rate_limit_per_minute)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id, name, key_prefix, permissions, expires_at,
                              rate_limit_per_minute, created_at
                    """,
                    body.name,
                    prefix,
                    key_hash,
                    body.permissions,
                    expires_at,
                    body.rate_limit_per_minute,
                )
        except Exception as e:
            logger.error("Failed to create API key: %s", e)
            return server_error(str(e))

        return success_response(
            data={
                "name": row["name"],
                "key": full_key,
                "key_prefix": row["key_prefix"],
                "permissions": list(row["permissions"]),
                "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                "rate_limit_per_minute": row["rate_limit_per_minute"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            },
            resource_type="api_key",
            resource_id=str(row["id"]),
            status_code=201,
        )

    @router.get("")
    async def list_api_keys(pagination: PaginationParams = Depends()):
        """List all API keys (prefix only, never the full key)."""
        query = """
            SELECT id, name, key_prefix, permissions, expires_at,
                   is_revoked, request_count, last_used_at,
                   rate_limit_per_minute, created_at
            FROM api_keys
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM api_keys"
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, pagination.limit, pagination.offset)
                total = await conn.fetchval(count_query)
        except Exception as e:
            logger.error("Failed to list API keys: %s", e)
            return server_error(str(e))

        items = []
        for row in rows:
            item = {
                "id": str(row["id"]),
                "name": row["name"],
                "key_prefix": row["key_prefix"],
                "permissions": list(row["permissions"]),
                "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
                "is_revoked": row["is_revoked"],
                "request_count": row["request_count"],
                "last_used_at": row["last_used_at"].isoformat() if row["last_used_at"] else None,
                "rate_limit_per_minute": row["rate_limit_per_minute"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            items.append(item)

        return collection_response(
            items,
            "api_key",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @router.delete("/{key_id}", status_code=204)
    async def revoke_api_key(key_id: str):
        """Revoke an API key."""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE api_keys SET is_revoked = TRUE
                    WHERE id = $1::uuid AND is_revoked = FALSE
                    RETURNING id
                    """,
                    key_id,
                )
        except Exception as e:
            logger.error("Failed to revoke API key: %s", e)
            return server_error(str(e))

        if not row:
            return not_found("API key", key_id)
        return None

    app.include_router(router)
    return app
