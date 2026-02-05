"""OAuth service for Google and GitHub authentication."""

from typing import Optional

from authlib.integrations.httpx_client import AsyncOAuth2Client
from pydantic import BaseModel

from ..config import settings


class OAuthUserInfo(BaseModel):
    """User info returned from OAuth providers."""

    provider: str
    provider_id: str
    email: str
    name: str
    avatar_url: Optional[str] = None


class GoogleOAuth:
    """Google OAuth2 client."""

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
            await client.fetch_token(
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
    """GitHub OAuth2 client."""

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
            await client.fetch_token(
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


class OAuthService:
    """Service for managing OAuth providers."""

    def __init__(self):
        self.google = GoogleOAuth()
        self.github = GitHubOAuth()

    def get_provider(self, provider: str):
        """Get OAuth provider by name."""
        providers = {
            "google": self.google,
            "github": self.github,
        }
        return providers.get(provider)


# Singleton instance
oauth_service = OAuthService()
