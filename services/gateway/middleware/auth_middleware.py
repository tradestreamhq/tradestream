"""Authentication middleware for JWT validation."""

from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..services.auth_service import auth_service, TokenData

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """Get current authenticated user from JWT token.

    Raises HTTPException if token is invalid or missing.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    token_data = auth_service.verify_token(credentials.credentials)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if token_data.is_demo:
        raise HTTPException(
            status_code=403, detail="Demo users cannot access this resource"
        )

    return token_data


async def get_current_user_or_demo(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[TokenData]:
    """Get current user or demo user from JWT token.

    Returns None if no token provided, allows demo users.
    """
    if not credentials:
        return None

    token_data = auth_service.verify_token(credentials.credentials)
    return token_data


def require_permission(permission: str):
    """Dependency factory for checking specific permissions."""

    async def check_permission(
        user: TokenData = Depends(get_current_user),
    ) -> TokenData:
        if permission not in user.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission} required",
            )
        return user

    return check_permission
