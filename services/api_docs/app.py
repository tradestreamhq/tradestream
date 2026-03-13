"""
API Documentation Service.

Serves a unified Swagger UI at /api/docs for all TradeStream endpoints,
backed by a single OpenAPI 3.0 specification aggregated from all
microservices.
"""

import json
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.api_docs.openapi_spec import get_spec

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create the API documentation FastAPI application."""
    app = FastAPI(
        title="TradeStream API Documentation",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/openapi.json", include_in_schema=False)
    async def openapi_json():
        """Return the unified OpenAPI spec as JSON."""
        return JSONResponse(content=get_spec())

    # Override FastAPI's auto-generated schema with our unified one
    app.openapi_schema = get_spec()

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "healthy", "service": "api-docs"}

    return app


app = create_app()


def main():
    import uvicorn

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8088"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
