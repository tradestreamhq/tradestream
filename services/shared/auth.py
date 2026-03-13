"""Authentication middleware for HTTP services.

Supports three authentication methods (checked in order):
1. JWT Bearer token (Authorization: Bearer <jwt>)
2. Per-user API key (X-API-Key: ts_...)
3. Service-level API key via TRADESTREAM_API_KEY env var (legacy)

Supports FastAPI, Flask, and Starlette.
Health check endpoints are excluded from authentication.
"""

import logging
import os

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"
API_KEY_ENV_VAR = "TRADESTREAM_API_KEY"

# Paths that bypass authentication
_HEALTH_PATHS = frozenset({"/health", "/api/health"})


def _get_api_key() -> str | None:
    """Return the configured service-level API key, or None if not set."""
    return os.environ.get(API_KEY_ENV_VAR)


def _is_health_check(path: str) -> bool:
    return path in _HEALTH_PATHS


def _try_jwt_auth(auth_header: str) -> dict | None:
    """Attempt to validate a JWT Bearer token. Returns user info or None."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        from services.auth_api.auth_service import decode_access_token

        payload = decode_access_token(auth_header[7:])
        return {"user_id": payload["sub"], "email": payload["email"], "auth_type": "jwt"}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


def fastapi_auth_middleware(app, *, db_pool=None):
    """Add authentication to a FastAPI/Starlette application.

    Accepts JWT Bearer tokens, per-user API keys (ts_* prefix), and
    the legacy service-level TRADESTREAM_API_KEY.

    If db_pool is provided, per-user API keys are validated against the
    database. Otherwise, only JWT and service-level keys are checked.
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class _AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if _is_health_check(request.url.path):
                return await call_next(request)

            # 1. Try JWT Bearer token
            auth_header = request.headers.get("Authorization", "")
            jwt_result = _try_jwt_auth(auth_header)
            if jwt_result:
                request.state.auth = jwt_result
                return await call_next(request)

            # 2. Try per-user API key (ts_* prefix)
            api_key_value = request.headers.get(API_KEY_HEADER, "")
            if api_key_value.startswith("ts_") and db_pool is not None:
                try:
                    from services.auth_api.auth_service import AuthService

                    svc = AuthService(db_pool)
                    key_info = await svc.validate_api_key(api_key_value)
                    if key_info:
                        request.state.auth = {
                            "user_id": key_info["user_id"],
                            "email": key_info["email"],
                            "auth_type": "api_key",
                            "permissions": key_info["permissions"],
                            "rate_limit_per_minute": key_info["rate_limit_per_minute"],
                        }
                        return await call_next(request)
                except Exception:
                    logger.exception("Error validating user API key")

            # 3. Try legacy service-level API key
            service_key = _get_api_key()
            if not service_key:
                # No auth configured — allow all (backwards compatible)
                return await call_next(request)

            if api_key_value == service_key:
                request.state.auth = {"auth_type": "service_key"}
                return await call_next(request)

            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or missing API key"},
            )

    app.add_middleware(_AuthMiddleware)


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

        # Try JWT Bearer token
        auth_header = request.headers.get("Authorization", "")
        jwt_result = _try_jwt_auth(auth_header)
        if jwt_result:
            request.auth = jwt_result
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
