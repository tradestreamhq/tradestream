# Auth Service Specification

## Goal

Provide secure authentication for the viral trading platform supporting email/password registration, OAuth providers (Google, GitHub), JWT-based sessions, and anonymous demo mode.

## Target Behavior

The auth service is part of the gateway-api and handles all authentication flows. It issues JWT access tokens (15 min) and refresh tokens (7 days) for authenticated sessions, plus limited demo tokens for anonymous users.

## Authentication Flows

### Email/Password Registration

```
┌─────────┐     POST /auth/register      ┌─────────────┐
│  User   │ ─────────────────────────────▶│  Gateway    │
│ Browser │                               │    API      │
└─────────┘                               └──────┬──────┘
                                                 │
     1. Validate email format                    │
     2. Hash password (bcrypt)                   │
     3. Create user record                       │
     4. Generate email verification token        │
     5. Send verification email via Resend       │
                                                 │
                                                 ▼
┌─────────┐     Email with link          ┌─────────────┐
│  User   │ ◀────────────────────────────│   Resend    │
│ Inbox   │                              │    API      │
└─────────┘                              └─────────────┘

     6. User clicks link
     7. GET /auth/verify-email?token=xxx
     8. Mark email as verified
     9. Redirect to login page
```

### OAuth Flow (Google/GitHub)

```
┌─────────┐     GET /auth/oauth/google   ┌─────────────┐
│  User   │ ─────────────────────────────▶│  Gateway    │
│ Browser │                               │    API      │
└─────────┘                               └──────┬──────┘
     │                                           │
     │ 302 Redirect to Google                    │
     ▼                                           │
┌─────────┐     Authorize                ┌─────────────┐
│ Google  │ ◀────────────────────────────│             │
│  OAuth  │                              │             │
└────┬────┘                              │             │
     │                                   │             │
     │ 302 Redirect with code            │             │
     ▼                                   │             │
┌─────────┐     GET /auth/oauth/google/callback
│  User   │ ─────────────────────────────▶│  Gateway    │
│ Browser │                               │    API      │
└─────────┘                               └──────┬──────┘
                                                 │
     1. Exchange code for tokens                 │
     2. Fetch user profile from Google           │
     3. Create/update user record                │
     4. Issue JWT access + refresh tokens        │
     5. Set refresh token as httpOnly cookie     │
                                                 │
                                                 ▼
     6. Redirect to dashboard with access token in URL fragment
```

### Demo Mode

```
┌─────────┐     POST /auth/demo          ┌─────────────┐
│  User   │ ─────────────────────────────▶│  Gateway    │
│ Browser │                               │    API      │
└─────────┘                               └──────┬──────┘
                                                 │
     1. Generate anonymous demo JWT              │
     2. No database record created               │
     3. Limited permissions                      │
                                                 │
                                                 ▼
     Returns: { access_token, is_demo: true }
```

## API Endpoints

### Registration & Login

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/auth/register` | POST | Create account with email/password | None |
| `/auth/login` | POST | Login with email/password | None |
| `/auth/logout` | POST | Revoke refresh token | Required |
| `/auth/refresh` | POST | Get new access token | Refresh token |
| `/auth/demo` | POST | Get demo access token | None |

### Email Verification

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/auth/verify-email` | GET | Verify email with token | None |
| `/auth/resend-verification` | POST | Resend verification email | Required |

### Password Reset

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/auth/forgot-password` | POST | Request password reset | None |
| `/auth/reset-password` | POST | Reset password with token | None |

### OAuth

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/auth/oauth/{provider}` | GET | Initiate OAuth flow | None |
| `/auth/oauth/{provider}/callback` | GET | Handle OAuth callback | None |

## Request/Response Schemas

### POST /auth/register

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecureP@ss123",
  "display_name": "TraderJoe"
}
```

**Response (201 Created):**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "display_name": "TraderJoe",
  "email_verified": false,
  "message": "Verification email sent. Please check your inbox."
}
```

**Errors:**
- `400 Bad Request` - Invalid email format or weak password
- `409 Conflict` - Email already registered

### POST /auth/login

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecureP@ss123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "display_name": "TraderJoe",
    "avatar_url": null,
    "email_verified": true,
    "is_provider": false
  }
}
```

**Note:** Refresh token is set as httpOnly cookie.

**Errors:**
- `401 Unauthorized` - Invalid credentials
- `403 Forbidden` - Email not verified

### POST /auth/refresh

**Request:** (Refresh token from httpOnly cookie)

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**Errors:**
- `401 Unauthorized` - Invalid or expired refresh token

### POST /auth/demo

**Request:** (No body required)

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "is_demo": true
}
```

### POST /auth/forgot-password

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "If an account exists with this email, a reset link has been sent."
}
```

**Note:** Always returns 200 to prevent email enumeration.

### POST /auth/reset-password

**Request:**
```json
{
  "token": "abc123...",
  "new_password": "NewSecureP@ss456"
}
```

**Response (200 OK):**
```json
{
  "message": "Password reset successful. You can now login."
}
```

**Errors:**
- `400 Bad Request` - Token expired or invalid
- `400 Bad Request` - Password doesn't meet requirements

## JWT Token Structure

### Access Token Claims

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "TraderJoe",
  "is_demo": false,
  "is_provider": false,
  "email_verified": true,
  "permissions": [
    "read:signals",
    "write:settings",
    "write:watchlist",
    "read:providers",
    "write:follows"
  ],
  "iat": 1706745600,
  "exp": 1706746500,
  "iss": "tradestream.io",
  "aud": "tradestream-api"
}
```

### Demo Token Claims

```json
{
  "sub": "demo",
  "is_demo": true,
  "permissions": [
    "read:signals",
    "read:providers"
  ],
  "iat": 1706745600,
  "exp": 1706749200,
  "iss": "tradestream.io",
  "aud": "tradestream-api"
}
```

### Permission Definitions

| Permission | Description | Demo | Auth |
|------------|-------------|------|------|
| `read:signals` | View trading signals | Yes | Yes |
| `read:providers` | View provider profiles | Yes | Yes |
| `write:settings` | Update user settings | No | Yes |
| `write:watchlist` | Manage watchlist | No | Yes |
| `write:follows` | Follow/unfollow providers | No | Yes |
| `write:reactions` | Like/comment on signals | No | Yes |
| `read:achievements` | View own achievements | No | Yes |
| `write:provider` | Publish signals (providers) | No | Provider |

## OAuth Configuration

### Google OAuth

```python
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = "https://tradestream.io/auth/oauth/google/callback"

# Scopes
GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile"
]
```

### GitHub OAuth

```python
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = "https://tradestream.io/auth/oauth/github/callback"

# Scopes
GITHUB_SCOPES = [
    "user:email",
    "read:user"
]
```

## Email Templates

### Verification Email

**Subject:** Verify your TradeStream account

**Body:**
```html
<h1>Welcome to TradeStream!</h1>
<p>Click the button below to verify your email address:</p>
<a href="https://tradestream.io/auth/verify-email?token={{token}}">
  Verify Email
</a>
<p>This link expires in 24 hours.</p>
<p>If you didn't create an account, you can ignore this email.</p>
```

### Password Reset Email

**Subject:** Reset your TradeStream password

**Body:**
```html
<h1>Password Reset Request</h1>
<p>Click the button below to reset your password:</p>
<a href="https://tradestream.io/reset-password?token={{token}}">
  Reset Password
</a>
<p>This link expires in 1 hour.</p>
<p>If you didn't request this, you can ignore this email.</p>
```

## Implementation

### File Structure

```
services/gateway/
├── routers/
│   └── auth.py              # All auth endpoints
├── services/
│   ├── auth_service.py      # JWT, password hashing
│   ├── email_service.py     # Resend integration
│   └── oauth_service.py     # OAuth provider clients
├── models/
│   ├── auth.py              # Request/response models
│   └── user.py              # User models
└── middleware/
    └── auth_middleware.py   # JWT validation
```

### auth_service.py

```python
from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import jwt, JWTError
from pydantic import BaseModel

from ..config import settings

class TokenData(BaseModel):
    sub: str
    email: Optional[str]
    name: Optional[str]
    is_demo: bool = False
    is_provider: bool = False
    email_verified: bool = False
    permissions: list[str]
    exp: datetime
    iat: datetime
    iss: str = "tradestream.io"
    aud: str = "tradestream-api"


class AuthService:
    def __init__(self):
        self.secret_key = settings.JWT_SECRET
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 15
        self.refresh_token_expire_days = 7
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
        now = datetime.utcnow()

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
        import secrets
        token = secrets.token_urlsafe(32)
        token_hash = bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()
        return token, token_hash

    def create_demo_token(self) -> str:
        """Create limited demo access token."""
        now = datetime.utcnow()
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
            base.extend([
                "write:settings",
                "write:watchlist",
                "write:follows",
                "write:reactions",
                "read:achievements",
            ])
        if is_provider:
            base.append("write:provider")
        return base
```

### email_service.py

```python
import resend
from ..config import settings


class EmailService:
    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY
        self.from_email = "TradeStream <noreply@tradestream.io>"

    async def send_verification_email(self, to_email: str, token: str) -> bool:
        """Send email verification link."""
        verify_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"

        try:
            resend.Emails.send({
                "from": self.from_email,
                "to": [to_email],
                "subject": "Verify your TradeStream account",
                "html": f"""
                <h1>Welcome to TradeStream!</h1>
                <p>Click the button below to verify your email address:</p>
                <p>
                    <a href="{verify_url}"
                       style="display:inline-block;padding:12px 24px;
                              background:#0ea5e9;color:white;text-decoration:none;
                              border-radius:6px;font-weight:600;">
                        Verify Email
                    </a>
                </p>
                <p>Or copy this link: {verify_url}</p>
                <p>This link expires in 24 hours.</p>
                <p style="color:#666;font-size:12px;">
                    If you didn't create an account, you can ignore this email.
                </p>
                """,
            })
            return True
        except Exception as e:
            print(f"Failed to send verification email: {e}")
            return False

    async def send_password_reset_email(self, to_email: str, token: str) -> bool:
        """Send password reset link."""
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        try:
            resend.Emails.send({
                "from": self.from_email,
                "to": [to_email],
                "subject": "Reset your TradeStream password",
                "html": f"""
                <h1>Password Reset Request</h1>
                <p>Click the button below to reset your password:</p>
                <p>
                    <a href="{reset_url}"
                       style="display:inline-block;padding:12px 24px;
                              background:#0ea5e9;color:white;text-decoration:none;
                              border-radius:6px;font-weight:600;">
                        Reset Password
                    </a>
                </p>
                <p>Or copy this link: {reset_url}</p>
                <p>This link expires in 1 hour.</p>
                <p style="color:#666;font-size:12px;">
                    If you didn't request this, you can ignore this email.
                </p>
                """,
            })
            return True
        except Exception as e:
            print(f"Failed to send password reset email: {e}")
            return False

    async def send_welcome_email(self, to_email: str, display_name: str) -> bool:
        """Send welcome email after verification."""
        try:
            resend.Emails.send({
                "from": self.from_email,
                "to": [to_email],
                "subject": "Welcome to TradeStream!",
                "html": f"""
                <h1>Welcome, {display_name}!</h1>
                <p>Your TradeStream account is ready to go.</p>
                <h2>Get Started:</h2>
                <ul>
                    <li>View real-time trading signals</li>
                    <li>Follow top signal providers</li>
                    <li>Build your watchlist</li>
                    <li>Earn achievements and climb the leaderboard</li>
                </ul>
                <p>
                    <a href="{settings.FRONTEND_URL}/dashboard"
                       style="display:inline-block;padding:12px 24px;
                              background:#0ea5e9;color:white;text-decoration:none;
                              border-radius:6px;font-weight:600;">
                        Go to Dashboard
                    </a>
                </p>
                """,
            })
            return True
        except Exception as e:
            print(f"Failed to send welcome email: {e}")
            return False
```

### oauth_service.py

```python
from authlib.integrations.httpx_client import AsyncOAuth2Client
from typing import Optional
from pydantic import BaseModel

from ..config import settings


class OAuthUserInfo(BaseModel):
    provider: str
    provider_id: str
    email: str
    name: str
    avatar_url: Optional[str]


class OAuthService:
    def __init__(self):
        self.google = GoogleOAuth()
        self.github = GitHubOAuth()

    def get_provider(self, provider: str):
        providers = {
            "google": self.google,
            "github": self.github,
        }
        return providers.get(provider)


class GoogleOAuth:
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = f"{settings.API_URL}/auth/oauth/google/callback"
        self.authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"

    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth authorization URL."""
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope="openid email profile",
        )
        url, _ = client.create_authorization_url(
            self.authorize_url,
            state=state,
        )
        return url

    async def get_user_info(self, code: str) -> OAuthUserInfo:
        """Exchange code for tokens and fetch user info."""
        async with AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
        ) as client:
            token = await client.fetch_token(
                self.token_url,
                code=code,
            )
            resp = await client.get(self.userinfo_url)
            data = resp.json()

            return OAuthUserInfo(
                provider="google",
                provider_id=data["sub"],
                email=data["email"],
                name=data.get("name", data["email"].split("@")[0]),
                avatar_url=data.get("picture"),
            )


class GitHubOAuth:
    def __init__(self):
        self.client_id = settings.GITHUB_CLIENT_ID
        self.client_secret = settings.GITHUB_CLIENT_SECRET
        self.redirect_uri = f"{settings.API_URL}/auth/oauth/github/callback"
        self.authorize_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.userinfo_url = "https://api.github.com/user"
        self.emails_url = "https://api.github.com/user/emails"

    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth authorization URL."""
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope="user:email read:user",
        )
        url, _ = client.create_authorization_url(
            self.authorize_url,
            state=state,
        )
        return url

    async def get_user_info(self, code: str) -> OAuthUserInfo:
        """Exchange code for tokens and fetch user info."""
        async with AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
        ) as client:
            token = await client.fetch_token(
                self.token_url,
                code=code,
                headers={"Accept": "application/json"},
            )

            # Get user profile
            resp = await client.get(self.userinfo_url)
            data = resp.json()

            # Get primary email
            email_resp = await client.get(self.emails_url)
            emails = email_resp.json()
            primary_email = next(
                (e["email"] for e in emails if e["primary"]),
                emails[0]["email"] if emails else None,
            )

            return OAuthUserInfo(
                provider="github",
                provider_id=str(data["id"]),
                email=primary_email,
                name=data.get("name") or data["login"],
                avatar_url=data.get("avatar_url"),
            )
```

### auth.py (Router)

```python
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
import secrets

from ..services.auth_service import AuthService
from ..services.email_service import EmailService
from ..services.oauth_service import OAuthService
from ..services.db import get_db
from ..middleware.auth_middleware import get_current_user, get_current_user_or_demo

router = APIRouter(prefix="/auth", tags=["auth"])

auth_service = AuthService()
email_service = EmailService()
oauth_service = OAuthService()


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


# Endpoints
@router.post("/register", status_code=201)
async def register(data: RegisterRequest, db=Depends(get_db)):
    """Register new user with email and password."""
    # Check if email exists
    existing = await db.fetchrow(
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
    user = await db.fetchrow(
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
    await db.execute(
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
async def login(data: LoginRequest, response: Response, db=Depends(get_db)):
    """Login with email and password."""
    user = await db.fetchrow(
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
    await db.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, NOW() + INTERVAL '7 days')
        """,
        user["user_id"],
        refresh_hash,
    )

    # Update last login
    await db.execute(
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
async def refresh(request: Request, response: Response, db=Depends(get_db)):
    """Refresh access token using refresh token from cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Refresh token required")

    # Find valid refresh token
    import bcrypt
    tokens = await db.fetch(
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
    await db.execute(
        "UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_id = $1",
        valid_token["token_id"],
    )

    new_refresh_token, new_refresh_hash = auth_service.create_refresh_token(
        str(valid_token["user_id"])
    )

    await db.execute(
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
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Logout and revoke refresh token."""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        # Revoke all refresh tokens for this user
        await db.execute(
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


@router.get("/verify-email")
async def verify_email(token: str, db=Depends(get_db)):
    """Verify email with token from email link."""
    result = await db.fetchrow(
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
    await db.execute(
        "UPDATE email_verification_tokens SET used_at = NOW() WHERE token = $1",
        token,
    )

    # Mark email as verified
    await db.execute(
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


@router.post("/forgot-password")
async def forgot_password(data: PasswordResetRequest, db=Depends(get_db)):
    """Request password reset email."""
    user = await db.fetchrow(
        "SELECT user_id FROM users WHERE email = $1 AND oauth_provider IS NULL",
        data.email,
    )

    # Always return success to prevent email enumeration
    if user:
        token = secrets.token_urlsafe(32)
        await db.execute(
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
async def reset_password(data: PasswordResetConfirm, db=Depends(get_db)):
    """Reset password with token from email."""
    result = await db.fetchrow(
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
    await db.execute(
        "UPDATE users SET password_hash = $1 WHERE user_id = $2",
        password_hash,
        result["user_id"],
    )

    # Mark token as used
    await db.execute(
        "UPDATE password_reset_tokens SET used_at = NOW() WHERE token = $1",
        data.token,
    )

    # Revoke all refresh tokens (force re-login)
    await db.execute(
        "UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = $1",
        result["user_id"],
    )

    return {"message": "Password reset successful. You can now login."}


# OAuth Routes
@router.get("/oauth/{provider}")
async def oauth_authorize(provider: str, request: Request):
    """Initiate OAuth flow."""
    oauth = oauth_service.get_provider(provider)
    if not oauth:
        raise HTTPException(400, f"Unknown OAuth provider: {provider}")

    state = secrets.token_urlsafe(32)
    # Store state in session/cache for validation
    # TODO: Use Redis for state storage

    url = oauth.get_authorization_url(state)
    return RedirectResponse(url=url)


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    response: Response,
    db=Depends(get_db),
):
    """Handle OAuth callback."""
    # TODO: Validate state from Redis

    oauth = oauth_service.get_provider(provider)
    if not oauth:
        raise HTTPException(400, f"Unknown OAuth provider: {provider}")

    # Get user info from provider
    user_info = await oauth.get_user_info(code)

    # Find or create user
    user = await db.fetchrow(
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
        existing = await db.fetchrow(
            "SELECT user_id FROM users WHERE email = $1",
            user_info.email,
        )

        if existing:
            # Link OAuth to existing account
            await db.execute(
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
            user = await db.fetchrow(
                "SELECT user_id, email, display_name, avatar_url, is_provider FROM users WHERE user_id = $1",
                existing["user_id"],
            )
        else:
            # Create new user
            user = await db.fetchrow(
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
    await db.execute(
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

    await db.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, NOW() + INTERVAL '7 days')
        """,
        user["user_id"],
        refresh_hash,
    )

    # Set refresh token cookie
    response = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback#access_token={access_token}",
        status_code=302,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )

    return response
```

## Security Considerations

### Password Requirements

- Minimum 8 characters
- Future: Add complexity requirements (uppercase, number, special char)
- Future: Check against common password lists

### Token Security

- Access tokens: Short-lived (15 min), stored in memory
- Refresh tokens: Long-lived (7 days), httpOnly cookie, rotated on use
- Demo tokens: 1 hour, no persistence

### Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `/auth/register` | 5/minute per IP |
| `/auth/login` | 10/minute per IP |
| `/auth/forgot-password` | 3/minute per IP |
| `/auth/oauth/*` | 10/minute per IP |

### CORS Configuration

```python
origins = [
    "https://tradestream.io",
    "https://www.tradestream.io",
    "http://localhost:3000",  # Development
]
```

## Constraints

- Passwords hashed with bcrypt (cost factor 12)
- JWT tokens signed with HS256
- All tokens have `iss` and `aud` claims
- Email verification required before login (email/password)
- OAuth users are automatically verified
- Refresh tokens rotated on each use

## Acceptance Criteria

- [ ] User can register with email/password
- [ ] Verification email sent via Resend
- [ ] User can verify email via link
- [ ] User can login with verified email
- [ ] Login returns JWT access token
- [ ] Refresh token set as httpOnly cookie
- [ ] Refresh endpoint returns new access token
- [ ] User can logout (refresh token revoked)
- [ ] User can request password reset
- [ ] User can reset password with token
- [ ] Google OAuth flow works end-to-end
- [ ] GitHub OAuth flow works end-to-end
- [ ] OAuth creates new user if not exists
- [ ] OAuth links to existing account by email
- [ ] Demo mode returns limited JWT
- [ ] Demo JWT has only read permissions
- [ ] Rate limiting enforced on auth endpoints
- [ ] All tokens properly validated on protected routes

## Notes

### OAuth State Management

For production, OAuth state should be stored in Redis with 10-minute TTL to prevent CSRF attacks:

```python
# Store state
await redis.setex(f"oauth_state:{state}", 600, user_agent)

# Verify state
stored = await redis.get(f"oauth_state:{state}")
if not stored:
    raise HTTPException(400, "Invalid state")
await redis.delete(f"oauth_state:{state}")
```

### Account Linking

When a user signs up with email/password and later tries OAuth with the same email:
1. If email matches, link the OAuth provider to existing account
2. User can then login with either method
3. Password remains valid for email login
