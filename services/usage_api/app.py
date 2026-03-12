"""
Usage API — Rate limiting and usage tracking service.

Provides endpoints for viewing API usage statistics and enforces
per-tier rate limits via middleware. Rate limit information is
communicated through standard headers on every response.
"""

import logging
from typing import Optional

from fastapi import APIRouter, FastAPI, Query, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware
from services.usage_api.rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting
_EXEMPT_PATHS = frozenset({"/health", "/ready", "/api/health"})

# Header used to identify the user (set by auth middleware or gateway)
_USER_HEADER = "X-API-Key"


def _get_user_id(request: Request) -> str:
    """Extract user identifier from request."""
    return request.headers.get(_USER_HEADER, "anonymous")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limits and adds rate limit headers."""

    def __init__(self, app, limiter: SlidingWindowRateLimiter):
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        user_id = _get_user_id(request)
        endpoint = request.url.path

        allowed, limit, remaining, reset_ts = self.limiter.check_and_record(
            user_id, endpoint
        )

        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests. Please retry later.",
                    }
                },
            )
        else:
            response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_ts))

        return response


def create_app(
    limiter: Optional[SlidingWindowRateLimiter] = None,
) -> FastAPI:
    """Create the Usage API FastAPI application.

    Args:
        limiter: Optional rate limiter instance. Creates a default if not provided.
    """
    if limiter is None:
        limiter = SlidingWindowRateLimiter()

    app = FastAPI(
        title="Usage API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/usage",
    )
    fastapi_auth_middleware(app)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.include_router(create_health_router("usage-api"))

    usage_router = APIRouter(tags=["Usage"])

    @usage_router.get("/current")
    async def current_usage(request: Request):
        """Get current usage stats for the authenticated user."""
        user_id = _get_user_id(request)
        usage = limiter.get_current_usage(user_id)
        return success_response(usage, "usage", resource_id=user_id)

    @usage_router.get("/history")
    async def usage_history(
        request: Request,
        days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    ):
        """Get daily usage breakdown for the authenticated user."""
        user_id = _get_user_id(request)
        history = limiter.get_usage_history(user_id, days=days)
        return collection_response(history, "usage_day")

    app.include_router(usage_router)
    return app
