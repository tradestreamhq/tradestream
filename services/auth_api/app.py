"""Auth & API Key Management REST API.

Provides endpoints for user registration, JWT login/refresh/logout,
and API key CRUD for programmatic access.
"""

import logging
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Request
from pydantic import BaseModel, EmailStr, Field

from services.auth_api.auth_service import AuthService, decode_access_token
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    success_response,
    validation_error,
)

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    name: str = Field(..., min_length=1, description="User display name")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token to invalidate")


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Key display name")
    permissions: List[str] = Field(
        default_factory=lambda: ["read"],
        description="Permission scopes (e.g. read, write, trade)",
    )
    rate_limit_per_minute: int = Field(
        default=60, ge=1, le=1000, description="Rate limit per minute"
    )


# --- Helpers ---


def _get_user_from_token(request: Request) -> dict:
    """Extract user info from JWT in Authorization header.

    Raises ValueError if token is missing or invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header")
    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
    except Exception:
        raise ValueError("Invalid or expired access token")
    return {"user_id": payload["sub"], "email": payload["email"]}


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Auth API FastAPI application."""
    app = FastAPI(
        title="Auth & API Key Management API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/auth",
    )

    auth_svc = AuthService(db_pool)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("auth-api", check_deps))

    auth_router = APIRouter(tags=["Auth"])
    keys_router = APIRouter(prefix="/api-keys", tags=["API Keys"])

    # --- Auth endpoints ---

    @auth_router.post("/register", status_code=201)
    async def register(body: RegisterRequest):
        user = await auth_svc.register_user(body.email, body.password, body.name)
        if user is None:
            return validation_error("Email already registered")
        tokens = await auth_svc.create_token_pair(user["id"], user["email"])
        return success_response(
            {"user": user, **tokens},
            resource_type="auth",
            resource_id=user["id"],
            status_code=201,
        )

    @auth_router.post("/login")
    async def login(body: LoginRequest):
        user = await auth_svc.authenticate_user(body.email, body.password)
        if user is None:
            return validation_error("Invalid email or password")
        tokens = await auth_svc.create_token_pair(user["id"], user["email"])
        return success_response(
            {"user": user, **tokens},
            resource_type="auth",
            resource_id=user["id"],
        )

    @auth_router.post("/refresh")
    async def refresh(body: RefreshRequest):
        tokens = await auth_svc.refresh_access_token(body.refresh_token)
        if tokens is None:
            return validation_error("Invalid or expired refresh token")
        return success_response(tokens, resource_type="auth")

    @auth_router.post("/logout")
    async def logout(body: LogoutRequest):
        revoked = await auth_svc.logout(body.refresh_token)
        return success_response(
            {"revoked": revoked},
            resource_type="auth",
        )

    # --- API Key endpoints ---

    @keys_router.post("", status_code=201)
    async def create_api_key(body: CreateApiKeyRequest, request: Request):
        try:
            user = _get_user_from_token(request)
        except ValueError as e:
            return validation_error(str(e))

        key_info = await auth_svc.create_api_key(
            user["user_id"],
            body.name,
            body.permissions,
            body.rate_limit_per_minute,
        )
        return success_response(
            key_info,
            resource_type="api_key",
            resource_id=key_info["id"],
            status_code=201,
        )

    @keys_router.get("")
    async def list_api_keys(request: Request):
        try:
            user = _get_user_from_token(request)
        except ValueError as e:
            return validation_error(str(e))

        keys = await auth_svc.list_api_keys(user["user_id"])
        return success_response(keys, resource_type="api_keys")

    @keys_router.delete("/{key_id}", status_code=200)
    async def revoke_api_key(key_id: str, request: Request):
        try:
            user = _get_user_from_token(request)
        except ValueError as e:
            return validation_error(str(e))

        revoked = await auth_svc.revoke_api_key(user["user_id"], key_id)
        if not revoked:
            return validation_error("API key not found or already revoked")
        return success_response({"revoked": True}, resource_type="api_key")

    app.include_router(auth_router)
    app.include_router(keys_router)
    return app
