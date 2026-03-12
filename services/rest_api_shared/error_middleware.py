"""FastAPI error handling middleware for standardized error responses.

Catches unhandled exceptions and circuit breaker errors, formatting
them according to the REST API error response standard.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from services.rest_api_shared.circuit_breaker import CircuitOpenError

logger = logging.getLogger(__name__)


def install_error_handlers(app: FastAPI) -> None:
    """Install exception handlers that return standardized error responses.

    Must be called after app creation but before routes are served.
    """

    @app.exception_handler(CircuitOpenError)
    async def circuit_open_handler(
        request: Request, exc: CircuitOpenError
    ) -> JSONResponse:
        logger.warning("Circuit open for %s: %s", exc.service_name, exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": f"Service '{exc.service_name}' is temporarily unavailable. "
                    f"Please retry after {exc.retry_after:.0f}s.",
                }
            },
            headers={"Retry-After": str(int(exc.retry_after))},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = []
        for error in exc.errors():
            loc = ".".join(str(l) for l in error["loc"] if l != "body")
            details.append({"field": loc, "message": error["msg"]})
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "SERVER_ERROR",
                    "message": "Internal server error",
                }
            },
        )
