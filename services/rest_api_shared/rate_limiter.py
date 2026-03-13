"""Per-route rate limiter middleware for FastAPI.

Uses an in-memory sliding-window counter store. Each route can have its own
limit via ``RateLimitConfig``.  Excess requests receive a 429 with a
``Retry-After`` header.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


@dataclass
class RateLimitConfig:
    """Rate limit settings for a single route."""

    max_requests: int
    window_seconds: int


@dataclass
class _TokenBucket:
    """Simple fixed-window counter."""

    count: int = 0
    window_start: float = 0.0


class RateLimitStore:
    """In-memory rate-limit state keyed by (client_ip, path)."""

    def __init__(self) -> None:
        self._buckets: Dict[str, _TokenBucket] = defaultdict(_TokenBucket)

    def is_allowed(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int]:
        """Check whether *key* is within its limit.

        Returns ``(allowed, retry_after_seconds)``.
        """
        now = time.monotonic()
        bucket = self._buckets[key]

        if now - bucket.window_start >= window_seconds:
            bucket.count = 0
            bucket.window_start = now

        bucket.count += 1
        if bucket.count > max_requests:
            retry_after = int(window_seconds - (now - bucket.window_start)) + 1
            return False, max(retry_after, 1)
        return True, 0


# Default per-route configs.  Keys are path prefixes.
DEFAULT_RATE_LIMITS: Dict[str, RateLimitConfig] = {
    "/": RateLimitConfig(max_requests=100, window_seconds=60),
}


def fastapi_rate_limiter(
    app,
    route_limits: Optional[Dict[str, RateLimitConfig]] = None,
    store: Optional[RateLimitStore] = None,
):
    """Add rate-limiting middleware to a FastAPI/Starlette application.

    Args:
        app: The FastAPI or Starlette application.
        route_limits: Mapping of path prefixes to ``RateLimitConfig``.
            Falls back to ``DEFAULT_RATE_LIMITS`` when *None*.
        store: Optional shared ``RateLimitStore`` instance (useful for testing).
    """
    limits = route_limits or DEFAULT_RATE_LIMITS
    limit_store = store or RateLimitStore()

    class _RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            config = _match_route(path, limits)
            if config is None:
                return await call_next(request)

            client_ip = request.client.host if request.client else "unknown"
            key = f"{client_ip}:{path}"
            allowed, retry_after = limit_store.is_allowed(
                key, config.max_requests, config.window_seconds
            )

            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests",
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            return await call_next(request)

    app.add_middleware(_RateLimitMiddleware)


def _match_route(
    path: str, limits: Dict[str, RateLimitConfig]
) -> Optional[RateLimitConfig]:
    """Return the most specific matching config for *path*."""
    best: Optional[RateLimitConfig] = None
    best_len = -1
    for prefix, config in limits.items():
        if path.startswith(prefix) and len(prefix) > best_len:
            best = config
            best_len = len(prefix)
    return best
