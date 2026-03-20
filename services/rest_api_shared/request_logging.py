"""Request logging middleware for FastAPI.

Logs method, path, status code, and duration for every request.  Sensitive
header values are masked so they do not leak into log output.
"""

import logging
import time
from typing import FrozenSet, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("tradestream.request")

# Headers whose values are replaced with "***" in log output.
DEFAULT_SENSITIVE_HEADERS: FrozenSet[str] = frozenset(
    {
        "authorization",
        "x-api-key",
        "cookie",
        "set-cookie",
    }
)

_MASK = "***"


def _mask_headers(headers: dict, sensitive: FrozenSet[str]) -> dict:
    """Return a copy of *headers* with sensitive values masked."""
    masked = {}
    for key, value in headers.items():
        if key.lower() in sensitive:
            masked[key] = _MASK
        else:
            masked[key] = value
    return masked


def fastapi_request_logging(
    app,
    sensitive_headers: Optional[FrozenSet[str]] = None,
    log_headers: bool = False,
):
    """Add request-logging middleware to a FastAPI/Starlette application.

    Args:
        app: The FastAPI or Starlette application.
        sensitive_headers: Header names to mask.  Defaults to
            ``DEFAULT_SENSITIVE_HEADERS``.
        log_headers: Whether to include request headers in log output.
    """
    sensitive = sensitive_headers or DEFAULT_SENSITIVE_HEADERS

    class _RequestLogging(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start = time.monotonic()
            method = request.method
            path = request.url.path

            response = await call_next(request)

            duration_ms = (time.monotonic() - start) * 1000
            extra = {
                "method": method,
                "path": path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }

            if log_headers:
                raw_headers = dict(request.headers)
                extra["headers"] = _mask_headers(raw_headers, sensitive)

            logger.info(
                "%s %s %d (%.1fms)",
                method,
                path,
                response.status_code,
                duration_ms,
                extra=extra,
            )
            return response

    app.add_middleware(_RequestLogging)
