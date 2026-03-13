"""Request validation middleware for FastAPI.

Checks Content-Type on requests with bodies, enforces body size limits,
and performs basic input sanitization.
"""

import re
from typing import Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Methods that are expected to carry a request body.
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

# Default maximum body size: 1 MiB.
DEFAULT_MAX_BODY_BYTES = 1 * 1024 * 1024

# Paths that bypass validation (e.g. health checks).
_BYPASS_PATHS = frozenset({"/health", "/ready", "/api/health"})

# Pattern that flags suspicious input (script tags, SQL injection fragments).
_DANGEROUS_PATTERN = re.compile(
    r"<script|javascript:|on\w+\s*=|;.*(?:DROP|DELETE|INSERT|UPDATE)\s",
    re.IGNORECASE,
)


def fastapi_request_validation(
    app,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    allowed_content_types: Optional[Set[str]] = None,
):
    """Add request-validation middleware to a FastAPI/Starlette application.

    Args:
        app: The FastAPI or Starlette application.
        max_body_bytes: Maximum allowed request body size.
        allowed_content_types: Set of acceptable Content-Type values for
            body-bearing requests.  Defaults to ``application/json``.
    """
    content_types = allowed_content_types or {"application/json"}

    class _RequestValidation(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            if path in _BYPASS_PATHS:
                return await call_next(request)

            method = request.method.upper()

            # Content-Type check for body-bearing methods.
            if method in _BODY_METHODS:
                ct = (request.headers.get("content-type") or "").split(";")[0].strip()
                if ct not in content_types:
                    return JSONResponse(
                        status_code=415,
                        content={
                            "error": {
                                "code": "UNSUPPORTED_MEDIA_TYPE",
                                "message": f"Content-Type must be one of: {', '.join(sorted(content_types))}",
                            }
                        },
                    )

            # Body size check.
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > max_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": f"Request body exceeds {max_body_bytes} bytes",
                        }
                    },
                )

            # Query-string sanitization.
            for value in request.query_params.values():
                if _DANGEROUS_PATTERN.search(value):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": {
                                "code": "INVALID_INPUT",
                                "message": "Request contains potentially dangerous input",
                            }
                        },
                    )

            return await call_next(request)

    app.add_middleware(_RequestValidation)
