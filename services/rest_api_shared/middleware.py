"""Convenience function to apply the full middleware stack to a FastAPI app.

Middleware is added in reverse order because Starlette processes middleware
in LIFO order (last added = first to execute).  The execution order is:

    request → logging → cors → request_validation → rate_limiter → auth → handler
"""

from typing import Dict, Optional, Sequence

from services.rest_api_shared.cors import fastapi_cors
from services.rest_api_shared.rate_limiter import RateLimitConfig, fastapi_rate_limiter
from services.rest_api_shared.request_logging import fastapi_request_logging
from services.rest_api_shared.request_validation import fastapi_request_validation
from services.shared.auth import fastapi_auth_middleware


def apply_middleware(
    app,
    *,
    rate_limits: Optional[Dict[str, RateLimitConfig]] = None,
    allowed_origins: Optional[Sequence[str]] = None,
    max_body_bytes: int = 1 * 1024 * 1024,
    log_headers: bool = False,
):
    """Apply the standard middleware stack to *app*.

    Middleware executes in this order (outermost first):
    1. Request logging
    2. CORS
    3. Request validation (Content-Type, body size, sanitization)
    4. Rate limiting
    5. Authentication (existing ``fastapi_auth_middleware``)

    Args:
        app: The FastAPI or Starlette application.
        rate_limits: Per-route rate limit configs.
        allowed_origins: CORS allowed origins.
        max_body_bytes: Max request body size in bytes.
        log_headers: Whether to log request headers.
    """
    # Added in reverse order — Starlette executes LIFO.
    fastapi_auth_middleware(app)
    fastapi_rate_limiter(app, route_limits=rate_limits)
    fastapi_request_validation(app, max_body_bytes=max_body_bytes)
    fastapi_cors(app, allowed_origins=allowed_origins)
    fastapi_request_logging(app, log_headers=log_headers)
