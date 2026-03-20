"""Tests for CORS middleware configuration."""

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from services.rest_api_shared.cors import DEFAULT_ALLOWED_ORIGINS, fastapi_cors


def _create_app(allowed_origins=None):
    async def index(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/", endpoint=index)])
    fastapi_cors(app, allowed_origins=allowed_origins)
    return app


class TestCORS:
    def test_preflight_with_allowed_origin(self):
        app = _create_app(allowed_origins=["https://example.com"])
        client = TestClient(app)
        resp = client.options(
            "/",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "https://example.com"

    def test_preflight_with_disallowed_origin(self):
        app = _create_app(allowed_origins=["https://example.com"])
        client = TestClient(app)
        resp = client.options(
            "/",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") is None

    def test_simple_request_with_allowed_origin(self):
        app = _create_app(allowed_origins=["https://example.com"])
        client = TestClient(app)
        resp = client.get("/", headers={"Origin": "https://example.com"})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://example.com"

    def test_default_origins(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.get("/", headers={"Origin": "http://localhost:3000"})
        assert (
            resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        )

    def test_credentials_allowed(self):
        app = _create_app(allowed_origins=["https://example.com"])
        client = TestClient(app)
        resp = client.options(
            "/",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-credentials") == "true"
