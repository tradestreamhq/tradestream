"""Exchange Keys REST API — multi-exchange API key management.

Provides CRUD endpoints for securely storing and rotating
exchange API credentials with encryption at rest.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import asyncpg
from fastapi import FastAPI
from pydantic import BaseModel, Field

from services.exchange_keys_api.encryption import decrypt, encrypt, mask
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class CreateExchangeKey(BaseModel):
    exchange_name: str = Field(
        ..., description="Exchange identifier (e.g. binance, kraken)"
    )
    api_key: str = Field(..., description="API key")
    api_secret: str = Field(..., description="API secret")
    label: Optional[str] = Field(None, description="Human-readable label")
    permissions: List[str] = Field(
        default=["read"],
        description="Permissions: read, trade, withdraw",
    )


class UpdateExchangeKey(BaseModel):
    label: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class RotateExchangeKey(BaseModel):
    api_key: str = Field(..., description="New API key")
    api_secret: str = Field(..., description="New API secret")


# --- Helpers ---


def _row_to_dict(row) -> dict:
    """Convert a DB row to a response dict, masking secrets."""
    item = dict(row)
    item["id"] = str(item["id"])
    # Decrypt then mask secrets for display
    if item.get("api_key_encrypted"):
        try:
            decrypted_key = decrypt(item["api_key_encrypted"])
            item["api_key"] = mask(decrypted_key)
        except Exception:
            item["api_key"] = "****"
    if item.get("api_secret_encrypted"):
        item["api_secret"] = "****"
    # Remove encrypted columns from response
    item.pop("api_key_encrypted", None)
    item.pop("api_secret_encrypted", None)
    # Serialize datetimes
    for field in ("created_at", "updated_at", "last_used_at"):
        if item.get(field) and isinstance(item[field], datetime):
            item[field] = item[field].isoformat()
    # Convert permissions list
    if item.get("permissions") and not isinstance(item["permissions"], list):
        item["permissions"] = list(item["permissions"])
    return item


_VALID_PERMISSIONS = {"read", "trade", "withdraw"}


def _validate_permissions(permissions: List[str]) -> Optional[str]:
    invalid = set(permissions) - _VALID_PERMISSIONS
    if invalid:
        return f"Invalid permissions: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(_VALID_PERMISSIONS))}"
    return None


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Exchange Keys API FastAPI application."""
    app = FastAPI(
        title="Exchange Keys API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/exchange-keys",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("exchange-keys-api", check_deps))

    # --- CREATE ---

    @app.post("/keys", tags=["Exchange Keys"])
    async def create_key(body: CreateExchangeKey):
        """Create a new exchange API key."""
        err = _validate_permissions(body.permissions)
        if err:
            return validation_error(err)

        key_id = uuid.uuid4()
        encrypted_key = encrypt(body.api_key)
        encrypted_secret = encrypt(body.api_secret)

        query = """
            INSERT INTO exchange_keys (
                id, exchange_name, api_key_encrypted, api_secret_encrypted,
                label, permissions, is_active
            ) VALUES ($1, $2, $3, $4, $5, $6, TRUE)
            RETURNING *
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    key_id,
                    body.exchange_name.lower(),
                    encrypted_key,
                    encrypted_secret,
                    body.label,
                    body.permissions,
                )
            return success_response(
                _row_to_dict(row),
                "exchange_key",
                resource_id=str(key_id),
                status_code=201,
            )
        except Exception as e:
            logger.exception("Failed to create exchange key")
            return server_error(str(e))

    # --- LIST ---

    @app.get("/keys", tags=["Exchange Keys"])
    async def list_keys(exchange_name: Optional[str] = None):
        """List all exchange API keys (secrets masked)."""
        if exchange_name:
            query = """
                SELECT * FROM exchange_keys
                WHERE exchange_name = $1
                ORDER BY created_at DESC
            """
            params = [exchange_name.lower()]
        else:
            query = "SELECT * FROM exchange_keys ORDER BY created_at DESC"
            params = []

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = [_row_to_dict(row) for row in rows]
        return collection_response(items, "exchange_key")

    # --- GET ---

    @app.get("/keys/{key_id}", tags=["Exchange Keys"])
    async def get_key(key_id: str):
        """Get a single exchange API key by ID (secrets masked)."""
        try:
            uid = uuid.UUID(key_id)
        except ValueError:
            return validation_error(f"Invalid key ID: {key_id}")

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM exchange_keys WHERE id = $1", uid)

        if not row:
            return not_found("ExchangeKey", key_id)
        return success_response(_row_to_dict(row), "exchange_key", resource_id=key_id)

    # --- UPDATE ---

    @app.patch("/keys/{key_id}", tags=["Exchange Keys"])
    async def update_key(key_id: str, body: UpdateExchangeKey):
        """Update an exchange API key's metadata."""
        try:
            uid = uuid.UUID(key_id)
        except ValueError:
            return validation_error(f"Invalid key ID: {key_id}")

        if body.permissions is not None:
            err = _validate_permissions(body.permissions)
            if err:
                return validation_error(err)

        sets = []
        params = []
        idx = 1

        if body.label is not None:
            sets.append(f"label = ${idx}")
            params.append(body.label)
            idx += 1
        if body.permissions is not None:
            sets.append(f"permissions = ${idx}")
            params.append(body.permissions)
            idx += 1
        if body.is_active is not None:
            sets.append(f"is_active = ${idx}")
            params.append(body.is_active)
            idx += 1

        if not sets:
            return validation_error("No fields to update")

        sets.append("updated_at = NOW()")
        params.append(uid)
        query = (
            f"UPDATE exchange_keys SET {', '.join(sets)} WHERE id = ${idx} RETURNING *"
        )

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return not_found("ExchangeKey", key_id)
        return success_response(_row_to_dict(row), "exchange_key", resource_id=key_id)

    # --- DELETE ---

    @app.delete("/keys/{key_id}", tags=["Exchange Keys"])
    async def delete_key(key_id: str):
        """Delete an exchange API key."""
        try:
            uid = uuid.UUID(key_id)
        except ValueError:
            return validation_error(f"Invalid key ID: {key_id}")

        async with db_pool.acquire() as conn:
            result = await conn.execute("DELETE FROM exchange_keys WHERE id = $1", uid)

        if result == "DELETE 0":
            return not_found("ExchangeKey", key_id)
        return success_response({"deleted": True}, "exchange_key", resource_id=key_id)

    # --- TEST KEY ---

    @app.post("/keys/{key_id}/test", tags=["Exchange Keys"])
    async def test_key(key_id: str):
        """Test that exchange API credentials are valid by calling the exchange."""
        try:
            uid = uuid.UUID(key_id)
        except ValueError:
            return validation_error(f"Invalid key ID: {key_id}")

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM exchange_keys WHERE id = $1", uid)

        if not row:
            return not_found("ExchangeKey", key_id)

        exchange_name = row["exchange_name"]
        try:
            api_key = decrypt(row["api_key_encrypted"])
            api_secret = decrypt(row["api_secret_encrypted"])
        except Exception:
            return server_error("Failed to decrypt credentials")

        # Use ccxt to verify credentials
        try:
            import ccxt

            exchange_class = getattr(ccxt, exchange_name, None)
            if exchange_class is None:
                return validation_error(f"Unsupported exchange: {exchange_name}")

            exchange = exchange_class(
                {"apiKey": api_key, "secret": api_secret, "timeout": 10000}
            )
            balance = exchange.fetch_balance()

            # Update last_used_at
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE exchange_keys SET last_used_at = NOW() WHERE id = $1", uid
                )

            return success_response(
                {"valid": True, "exchange": exchange_name},
                "key_test",
                resource_id=key_id,
            )
        except ccxt.AuthenticationError:
            return success_response(
                {
                    "valid": False,
                    "error": "Authentication failed",
                    "exchange": exchange_name,
                },
                "key_test",
                resource_id=key_id,
            )
        except Exception as e:
            return success_response(
                {"valid": False, "error": str(e), "exchange": exchange_name},
                "key_test",
                resource_id=key_id,
            )

    # --- ROTATE ---

    @app.post("/keys/{key_id}/rotate", tags=["Exchange Keys"])
    async def rotate_key(key_id: str, body: RotateExchangeKey):
        """Rotate credentials: set new key+secret, verify they work, then commit."""
        try:
            uid = uuid.UUID(key_id)
        except ValueError:
            return validation_error(f"Invalid key ID: {key_id}")

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM exchange_keys WHERE id = $1", uid)

        if not row:
            return not_found("ExchangeKey", key_id)

        exchange_name = row["exchange_name"]

        # Verify new credentials work before committing
        try:
            import ccxt

            exchange_class = getattr(ccxt, exchange_name, None)
            if exchange_class is None:
                return validation_error(f"Unsupported exchange: {exchange_name}")

            exchange = exchange_class(
                {"apiKey": body.api_key, "secret": body.api_secret, "timeout": 10000}
            )
            exchange.fetch_balance()
        except Exception as e:
            return validation_error(f"New credentials failed verification: {e}")

        # Credentials work — encrypt and store
        encrypted_key = encrypt(body.api_key)
        encrypted_secret = encrypt(body.api_secret)

        query = """
            UPDATE exchange_keys
            SET api_key_encrypted = $1,
                api_secret_encrypted = $2,
                last_used_at = NOW(),
                updated_at = NOW()
            WHERE id = $3
            RETURNING *
        """
        async with db_pool.acquire() as conn:
            updated = await conn.fetchrow(query, encrypted_key, encrypted_secret, uid)

        return success_response(
            _row_to_dict(updated), "exchange_key", resource_id=key_id
        )

    return app
