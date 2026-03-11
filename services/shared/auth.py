"""API key authentication middleware for HTTP services.

Supports FastAPI, Flask, and Starlette. The API key is read from the
TRADESTREAM_API_KEY environment variable and validated against
the X-API-Key request header.

Health check endpoints are excluded from authentication.
"""

import functools
import logging
import os

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"
API_KEY_ENV_VAR = "TRADESTREAM_API_KEY"

# Paths that bypass authentication
_HEALTH_PATHS = frozenset({"/health", "/api/health"})


def _get_api_key() -> str | None:
    """Return the configured API key, or None if not set."""
    return os.environ.get(API_KEY_ENV_VAR)


def _is_health_check(path: str) -> bool:
    return path in _HEALTH_PATHS


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


def fastapi_auth_middleware(app):
    """Add API key authentication to a FastAPI/Starlette application.

    Usage:
        from services.shared.auth import fastapi_auth_middleware
        app = FastAPI()
        fastapi_auth_middleware(app)
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class _APIKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if _is_health_check(request.url.path):
                return await call_next(request)

            api_key = _get_api_key()
            if not api_key:
                # No key configured — auth disabled
                return await call_next(request)

            provided = request.headers.get(API_KEY_HEADER)
            if provided != api_key:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or missing API key"},
                )
            return await call_next(request)

    app.add_middleware(_APIKeyMiddleware)


# ---------------------------------------------------------------------------
# Flask middleware
# ---------------------------------------------------------------------------


def flask_auth_middleware(app):
    """Add API key authentication to a Flask application.

    Usage:
        from services.shared.auth import flask_auth_middleware
        app = Flask(__name__)
        flask_auth_middleware(app)
    """
    from flask import jsonify, request

    @app.before_request
    def _check_api_key():
        if _is_health_check(request.path):
            return None

        api_key = _get_api_key()
        if not api_key:
            return None

        provided = request.headers.get(API_KEY_HEADER)
        if provided != api_key:
            return jsonify({"error": "Invalid or missing API key"}), 401

        return None


# ---------------------------------------------------------------------------
# Starlette middleware (alias for MCP SSE servers and other Starlette apps)
# ---------------------------------------------------------------------------

# starlette_auth_middleware is the same as fastapi_auth_middleware since
# FastAPI is built on Starlette.  The alias makes intent clearer when the
# caller is a plain Starlette application (e.g. MCP SSE transport).
starlette_auth_middleware = fastapi_auth_middleware
