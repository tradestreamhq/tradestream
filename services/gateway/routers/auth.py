"""Authentication router for registration, login, OAuth, and password reset."""

import secrets
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr

from ..config import settings
from ..middleware.auth_middleware import get_current_user
from ..services.auth_service import auth_service, TokenData
from ..services.db import get_pool
from ..services.email_service import email_service
from ..services.oauth_service import oauth_service

router = APIRouter(prefix="/auth", tags=["auth"])


# Request/Response Models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    is_demo: bool = False
    user: Optional[dict] = None


# Registration & Login Endpoints
@router.post("/register", status_code=201)
async def register(data: RegisterRequest):
    """Register new user with email and password."""
    pool = await get_pool()

    # Check if email exists
    existing = await pool.fetchrow(
        "SELECT user_id FROM users WHERE email = $1",
        data.email,
    )
    if existing:
        raise HTTPException(409, "Email already registered")

    # Validate password strength
    if len(data.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    # Create user
    password_hash = auth_service.hash_password(data.password)
    user = await pool.fetchrow(
        """
        INSERT INTO users (email, password_hash, display_name)
        VALUES ($1, $2, $3)
        RETURNING user_id, email, display_name
        """,
        data.email,
        password_hash,
        data.display_name,
    )

    # Create verification token
    token = secrets.token_urlsafe(32)
    await pool.execute(
        """
        INSERT INTO email_verification_tokens (user_id, token, expires_at)
        VALUES ($1, $2, NOW() + INTERVAL '24 hours')
        """,
        user["user_id"],
        token,
    )

    # Send verification email
    await email_service.send_verification_email(data.email, token)

    return {
        "user_id": str(user["user_id"]),
        "email": user["email"],
        "display_name": user["display_name"],
        "email_verified": False,
        "message": "Verification email sent. Please check your inbox.",
    }


@router.post("/login")
async def login(data: LoginRequest, response: Response):
    """Login with email and password."""
    pool = await get_pool()

    user = await pool.fetchrow(
        """
        SELECT user_id, email, password_hash, display_name, avatar_url,
               email_verified, is_provider
        FROM users
        WHERE email = $1 AND oauth_provider IS NULL
        """,
        data.email,
    )

    if not user or not auth_service.verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    if not user["email_verified"]:
        raise HTTPException(403, "Please verify your email before logging in")

    # Create tokens
    access_token = auth_service.create_access_token(
        user_id=str(user["user_id"]),
        email=user["email"],
        name=user["display_name"],
        is_provider=user["is_provider"],
        email_verified=user["email_verified"],
    )

    refresh_token, refresh_hash = auth_service.create_refresh_token(str(user["user_id"]))

    # Store refresh token
    await pool.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, NOW() + INTERVAL '7 days')
        """,
        user["user_id"],
        refresh_hash,
    )

    # Update last login
    await pool.execute(
        "UPDATE users SET last_login_at = NOW() WHERE user_id = $1",
        user["user_id"],
    )

    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=900,  # 15 minutes
        user={
            "user_id": str(user["user_id"]),
            "email": user["email"],
            "display_name": user["display_name"],
            "avatar_url": user["avatar_url"],
            "email_verified": user["email_verified"],
            "is_provider": user["is_provider"],
        },
    )


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    """Refresh access token using refresh token from cookie."""
    pool = await get_pool()

    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Refresh token required")

    # Find valid refresh token
    tokens = await pool.fetch(
        """
        SELECT rt.token_id, rt.token_hash, rt.user_id,
               u.email, u.display_name, u.is_provider, u.email_verified
        FROM refresh_tokens rt
        JOIN users u ON u.user_id = rt.user_id
        WHERE rt.expires_at > NOW() AND rt.revoked_at IS NULL
        ORDER BY rt.created_at DESC
        LIMIT 10
        """,
    )

    valid_token = None
    for t in tokens:
        if bcrypt.checkpw(refresh_token.encode(), t["token_hash"].encode()):
            valid_token = t
            break

    if not valid_token:
        raise HTTPException(401, "Invalid refresh token")

    # Rotate refresh token
    await pool.execute(
        "UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_id = $1",
        valid_token["token_id"],
    )

    new_refresh_token, new_refresh_hash = auth_service.create_refresh_token(
        str(valid_token["user_id"])
    )

    await pool.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, NOW() + INTERVAL '7 days')
        """,
        valid_token["user_id"],
        new_refresh_hash,
    )

    # Create new access token
    access_token = auth_service.create_access_token(
        user_id=str(valid_token["user_id"]),
        email=valid_token["email"],
        name=valid_token["display_name"],
        is_provider=valid_token["is_provider"],
        email_verified=valid_token["email_verified"],
    )

    # Set new refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )

    return TokenResponse(access_token=access_token, expires_in=900)


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    user: TokenData = Depends(get_current_user),
):
    """Logout and revoke refresh token."""
    pool = await get_pool()

    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        # Revoke all refresh tokens for this user
        await pool.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = NOW()
            WHERE user_id = $1 AND revoked_at IS NULL
            """,
            user.sub,
        )

    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}


@router.post("/demo")
async def demo_login():
    """Get demo access token without registration."""
    access_token = auth_service.create_demo_token()
    return TokenResponse(
        access_token=access_token,
        expires_in=3600,  # 1 hour
        is_demo=True,
    )


# Email Verification Endpoints
@router.get("/verify-email")
async def verify_email(token: str):
    """Verify email with token from email link."""
    pool = await get_pool()

    result = await pool.fetchrow(
        """
        SELECT evt.user_id, u.email, u.display_name
        FROM email_verification_tokens evt
        JOIN users u ON u.user_id = evt.user_id
        WHERE evt.token = $1
          AND evt.expires_at > NOW()
          AND evt.used_at IS NULL
        """,
        token,
    )

    if not result:
        raise HTTPException(400, "Invalid or expired verification token")

    # Mark token as used
    await pool.execute(
        "UPDATE email_verification_tokens SET used_at = NOW() WHERE token = $1",
        token,
    )

    # Mark email as verified
    await pool.execute(
        "UPDATE users SET email_verified = TRUE WHERE user_id = $1",
        result["user_id"],
    )

    # Send welcome email
    await email_service.send_welcome_email(result["email"], result["display_name"])

    # Redirect to login page
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}/login?verified=true",
        status_code=302,
    )


# Password Reset Endpoints
@router.post("/forgot-password")
async def forgot_password(data: PasswordResetRequest):
    """Request password reset email."""
    pool = await get_pool()

    user = await pool.fetchrow(
        "SELECT user_id FROM users WHERE email = $1 AND oauth_provider IS NULL",
        data.email,
    )

    # Always return success to prevent email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        await pool.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '1 hour')
            """,
            user["user_id"],
            token,
        )
        await email_service.send_password_reset_email(data.email, token)

    return {"message": "If an account exists with this email, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(data: PasswordResetConfirm):
    """Reset password with token from email."""
    pool = await get_pool()

    result = await pool.fetchrow(
        """
        SELECT user_id
        FROM password_reset_tokens
        WHERE token = $1
          AND expires_at > NOW()
          AND used_at IS NULL
        """,
        data.token,
    )

    if not result:
        raise HTTPException(400, "Invalid or expired reset token")

    if len(data.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    # Update password
    password_hash = auth_service.hash_password(data.new_password)
    await pool.execute(
        "UPDATE users SET password_hash = $1 WHERE user_id = $2",
        password_hash,
        result["user_id"],
    )

    # Mark token as used
    await pool.execute(
        "UPDATE password_reset_tokens SET used_at = NOW() WHERE token = $1",
        data.token,
    )

    # Revoke all refresh tokens (force re-login)
    await pool.execute(
        "UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = $1",
        result["user_id"],
    )

    return {"message": "Password reset successful. You can now login."}


# OAuth Routes
@router.get("/oauth/{provider}")
async def oauth_authorize(provider: str):
    """Initiate OAuth flow."""
    oauth = oauth_service.get_provider(provider)
    if not oauth:
        raise HTTPException(400, f"Unknown OAuth provider: {provider}")

    state = secrets.token_urlsafe(32)
    # TODO: Store state in Redis for validation

    url = oauth.get_authorization_url(state)
    return RedirectResponse(url=url)


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    response: Response,
):
    """Handle OAuth callback."""
    pool = await get_pool()

    # TODO: Validate state from Redis

    oauth = oauth_service.get_provider(provider)
    if not oauth:
        raise HTTPException(400, f"Unknown OAuth provider: {provider}")

    # Get user info from provider
    user_info = await oauth.get_user_info(code)

    # Find or create user
    user = await pool.fetchrow(
        """
        SELECT user_id, email, display_name, avatar_url, is_provider
        FROM users
        WHERE oauth_provider = $1 AND oauth_id = $2
        """,
        user_info.provider,
        user_info.provider_id,
    )

    if not user:
        # Check if email already exists (link accounts)
        existing = await pool.fetchrow(
            "SELECT user_id FROM users WHERE email = $1",
            user_info.email,
        )

        if existing:
            # Link OAuth to existing account
            await pool.execute(
                """
                UPDATE users
                SET oauth_provider = $1, oauth_id = $2, avatar_url = COALESCE(avatar_url, $3)
                WHERE user_id = $4
                """,
                user_info.provider,
                user_info.provider_id,
                user_info.avatar_url,
                existing["user_id"],
            )
            user = await pool.fetchrow(
                "SELECT user_id, email, display_name, avatar_url, is_provider FROM users WHERE user_id = $1",
                existing["user_id"],
            )
        else:
            # Create new user
            user = await pool.fetchrow(
                """
                INSERT INTO users (email, email_verified, oauth_provider, oauth_id, display_name, avatar_url)
                VALUES ($1, TRUE, $2, $3, $4, $5)
                RETURNING user_id, email, display_name, avatar_url, is_provider
                """,
                user_info.email,
                user_info.provider,
                user_info.provider_id,
                user_info.name,
                user_info.avatar_url,
            )

    # Update last login
    await pool.execute(
        "UPDATE users SET last_login_at = NOW() WHERE user_id = $1",
        user["user_id"],
    )

    # Create tokens
    access_token = auth_service.create_access_token(
        user_id=str(user["user_id"]),
        email=user["email"],
        name=user["display_name"],
        is_provider=user["is_provider"],
        email_verified=True,
    )

    refresh_token, refresh_hash = auth_service.create_refresh_token(str(user["user_id"]))

    await pool.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, NOW() + INTERVAL '7 days')
        """,
        user["user_id"],
        refresh_hash,
    )

    # Set refresh token cookie and redirect
    redirect_response = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback#access_token={access_token}",
        status_code=302,
    )
    redirect_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )

    return redirect_response
