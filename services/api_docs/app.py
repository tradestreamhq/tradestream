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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from services.api_docs.openapi_spec import get_spec

logger = logging.getLogger(__name__)

# Path to static docs directory (relative to repo root)
_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "api")


def _read_doc_file(filename: str) -> str | None:
    """Read a file from the docs/api directory, return None if missing."""
    path = os.path.join(_DOCS_DIR, filename)
    if os.path.isfile(path):
        with open(path) as f:
            return f.read()
    return None


def create_app() -> FastAPI:
    """Create the API documentation FastAPI application."""
    app = FastAPI(
        title="TradeStream API Documentation",
        description=(
            "Unified API documentation for the TradeStream platform — "
            "134 endpoints across signals, strategies, marketplace, billing, "
            "backtesting, opportunities, user management, and integrations."
        ),
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

    @app.get("/api/openapi.yaml", include_in_schema=False)
    async def openapi_yaml():
        """Return the unified OpenAPI spec as YAML."""
        try:
            import yaml

            return PlainTextResponse(
                content=yaml.dump(
                    get_spec(), default_flow_style=False, sort_keys=False
                ),
                media_type="application/x-yaml",
            )
        except ImportError:
            # Fallback to JSON if PyYAML not available
            return JSONResponse(content=get_spec())

    @app.get("/", include_in_schema=False)
    async def docs_index():
        """Serve the API documentation landing page."""
        content = _read_doc_file("index.html")
        if content:
            return HTMLResponse(content=content)
        # Redirect to Swagger UI if no index page
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/api/docs")

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
