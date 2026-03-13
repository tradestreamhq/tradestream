"""Core authentication service: JWT tokens, password hashing, user management."""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
import jwt

logger = logging.getLogger(__name__)

# Configuration via environment variables
JWT_SECRET = os.environ.get("TRADESTREAM_JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("JWT_REFRESH_EXPIRE_DAYS", "30"))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token() -> str:
    """Create a cryptographically secure refresh token string."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Hash a token (refresh token or API key) using SHA-256."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises jwt.InvalidTokenError on invalid/expired tokens.
    """
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def generate_api_key() -> str:
    """Generate a new API key with a ts_ prefix."""
    return f"ts_{secrets.token_urlsafe(32)}"


def get_api_key_prefix(api_key: str) -> str:
    """Extract the display prefix from an API key (first 8 chars)."""
    return api_key[:8]


class AuthService:
    """Database-backed authentication operations."""

    def __init__(self, db_pool):
        self._pool = db_pool

    async def register_user(
        self, email: str, password: str, name: str
    ) -> Optional[Dict[str, Any]]:
        """Register a new user. Returns user dict or None if email exists."""
        pw_hash = hash_password(password)
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (email, name, password_hash)
                    VALUES ($1, $2, $3)
                    RETURNING id, email, name, is_active, created_at
                    """,
                    email.lower().strip(),
                    name.strip(),
                    pw_hash,
                )
        except Exception as e:
            if "unique" in str(e).lower():
                return None
            raise
        return _user_to_dict(row)

    async def authenticate_user(
        self, email: str, password: str
    ) -> Optional[Dict[str, Any]]:
        """Authenticate a user by email/password. Returns user dict or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, name, password_hash, is_active FROM users WHERE email = $1",
                email.lower().strip(),
            )
        if not row:
            return None
        if not row["is_active"]:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return {"id": str(row["id"]), "email": row["email"], "name": row["name"]}

    async def create_token_pair(
        self, user_id: str, email: str
    ) -> Dict[str, str]:
        """Create an access + refresh token pair, storing refresh token in DB."""
        access_token = create_access_token(user_id, email)
        refresh_token = create_refresh_token()
        token_h = hash_token(refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES ($1::uuid, $2, $3)
                """,
                user_id,
                token_h,
                expires_at,
            )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def refresh_access_token(
        self, refresh_token: str
    ) -> Optional[Dict[str, str]]:
        """Use a refresh token to get new tokens. Returns token dict or None."""
        token_h = hash_token(refresh_token)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked,
                       u.email, u.is_active
                FROM refresh_tokens rt
                JOIN users u ON u.id = rt.user_id
                WHERE rt.token_hash = $1
                """,
                token_h,
            )
        if not row:
            return None
        if row["revoked"] or not row["is_active"]:
            return None
        if row["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None

        # Revoke old refresh token
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE id = $1",
                row["id"],
            )

        # Issue new pair
        return await self.create_token_pair(str(row["user_id"]), row["email"])

    async def logout(self, refresh_token: str) -> bool:
        """Revoke a refresh token. Returns True if token was found."""
        token_h = hash_token(refresh_token)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = $1 AND revoked = FALSE",
                token_h,
            )
        return result != "UPDATE 0"

    # --- API Key management ---

    async def create_api_key(
        self, user_id: str, name: str, permissions: List[str], rate_limit: int = 60
    ) -> Dict[str, Any]:
        """Create a new API key. Returns key info including the raw key (shown once)."""
        raw_key = generate_api_key()
        prefix = get_api_key_prefix(raw_key)
        key_h = hash_token(raw_key)

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO api_keys (user_id, name, key_prefix, key_hash, permissions, rate_limit_per_minute)
                VALUES ($1::uuid, $2, $3, $4, $5, $6)
                RETURNING id, name, key_prefix, permissions, rate_limit_per_minute, created_at
                """,
                user_id,
                name,
                prefix,
                key_h,
                permissions,
                rate_limit,
            )
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "key": raw_key,
            "key_prefix": row["key_prefix"],
            "permissions": list(row["permissions"]),
            "rate_limit_per_minute": row["rate_limit_per_minute"],
            "created_at": row["created_at"].isoformat(),
        }

    async def list_api_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """List all API keys for a user (keys are masked)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, key_prefix, permissions, is_active,
                       rate_limit_per_minute, last_used_at, created_at
                FROM api_keys
                WHERE user_id = $1::uuid AND is_active = TRUE
                ORDER BY created_at DESC
                """,
                user_id,
            )
        return [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "key_prefix": r["key_prefix"] + "...",
                "permissions": list(r["permissions"]),
                "is_active": r["is_active"],
                "rate_limit_per_minute": r["rate_limit_per_minute"],
                "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        """Revoke an API key. Returns True if found and revoked."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE api_keys SET is_active = FALSE
                WHERE id = $1::uuid AND user_id = $2::uuid AND is_active = TRUE
                """,
                key_id,
                user_id,
            )
        return result != "UPDATE 0"

    async def validate_api_key(self, raw_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return user + permissions info."""
        key_h = hash_token(raw_key)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ak.id AS key_id, ak.user_id, ak.permissions,
                       ak.rate_limit_per_minute, u.email, u.is_active AS user_active
                FROM api_keys ak
                JOIN users u ON u.id = ak.user_id
                WHERE ak.key_hash = $1 AND ak.is_active = TRUE
                """,
                key_h,
            )
        if not row or not row["user_active"]:
            return None

        # Update last_used_at
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1",
                row["key_id"],
            )

        return {
            "user_id": str(row["user_id"]),
            "email": row["email"],
            "permissions": list(row["permissions"]),
            "rate_limit_per_minute": row["rate_limit_per_minute"],
            "key_id": str(row["key_id"]),
        }


def _user_to_dict(row) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "name": row["name"],
        "is_active": row["is_active"],
        "created_at": row["created_at"].isoformat(),
    }
