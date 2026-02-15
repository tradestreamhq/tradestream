"""Authentication service for JWT token management."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt, JWTError
from pydantic import BaseModel

from ..config import settings


class TokenData(BaseModel):
    """JWT token data structure."""

    sub: str
    email: Optional[str] = None
    name: Optional[str] = None
    is_demo: bool = False
    is_provider: bool = False
    email_verified: bool = False
    permissions: list[str] = []


class AuthService:
    """Service for authentication and JWT token management."""

    def __init__(self):
        self.secret_key = settings.JWT_SECRET
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        self.demo_token_expire_hours = 1

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode(), salt).decode()

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def create_access_token(
        self,
        user_id: str,
        email: str,
        name: str,
        is_provider: bool = False,
        email_verified: bool = True,
    ) -> str:
        """Create JWT access token for authenticated user."""
        permissions = self._get_permissions(is_provider, email_verified)
        now = datetime.now(timezone.utc)

        claims = {
            "sub": user_id,
            "email": email,
            "name": name,
            "is_demo": False,
            "is_provider": is_provider,
            "email_verified": email_verified,
            "permissions": permissions,
            "iat": now,
            "exp": now + timedelta(minutes=self.access_token_expire_minutes),
            "iss": "tradestream.io",
            "aud": "tradestream-api",
        }
        return jwt.encode(claims, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> tuple[str, str]:
        """Create refresh token and return (token, hash)."""
        token = secrets.token_urlsafe(32)
        token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()
        return token, token_hash

    def create_demo_token(self) -> str:
        """Create limited demo access token."""
        now = datetime.now(timezone.utc)
        claims = {
            "sub": "demo",
            "is_demo": True,
            "permissions": ["read:signals", "read:providers"],
            "iat": now,
            "exp": now + timedelta(hours=self.demo_token_expire_hours),
            "iss": "tradestream.io",
            "aud": "tradestream-api",
        }
        return jwt.encode(claims, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience="tradestream-api",
                issuer="tradestream.io",
            )
            return TokenData(**payload)
        except JWTError:
            return None

    def _get_permissions(self, is_provider: bool, email_verified: bool) -> list[str]:
        """Get permissions based on user type."""
        base = ["read:signals", "read:providers"]
        if email_verified:
            base.extend(
                [
                    "write:settings",
                    "write:watchlist",
                    "write:follows",
                    "write:reactions",
                    "read:achievements",
                ]
            )
        if is_provider:
            base.append("write:provider")
        return base


# Singleton instance
auth_service = AuthService()
