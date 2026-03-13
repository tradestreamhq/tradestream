"""Tests for the shared API key authentication middleware."""

import os
from unittest.mock import patch

import pytest
from flask import Flask, jsonify
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from services.shared.auth import flask_auth_middleware, starlette_auth_middleware


def _create_test_app():
    """Create a minimal Flask app with auth middleware for testing."""
    app = Flask(__name__)
    flask_auth_middleware(app)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    @app.route("/data")
    def data():
        return jsonify({"value": 42})

    return app


class TestFlaskAuthMiddleware:
    """Tests for Flask API key auth middleware."""

    def test_health_endpoint_bypasses_auth(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/health")
                assert resp.status_code == 200

    def test_api_health_endpoint_bypasses_auth(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/api/health")
                assert resp.status_code == 200

    def test_no_key_configured_allows_all(self):
        app = _create_test_app()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRADESTREAM_API_KEY", None)
            with app.test_client() as client:
                resp = client.get("/data")
                assert resp.status_code == 200

    def test_valid_api_key(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data", headers={"X-API-Key": "secret123"})
                assert resp.status_code == 200

    def test_invalid_api_key(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data", headers={"X-API-Key": "wrong"})
                assert resp.status_code == 401

    def test_missing_api_key_header(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data")
                assert resp.status_code == 401

    def test_401_response_body(self):
        app = _create_test_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data")
                data = resp.get_json()
                assert data["error"] == "Invalid or missing API key"

    def test_jwt_bearer_token_bypasses_api_key(self):
        """A valid JWT Bearer token should authenticate even with API key configured."""
        from services.auth_api.auth_service import create_access_token

        app = _create_test_app()
        token = create_access_token("user-1", "user@example.com")
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            with app.test_client() as client:
                resp = client.get("/data", headers={"Authorization": f"Bearer {token}"})
                assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Starlette / MCP SSE auth middleware tests
# ---------------------------------------------------------------------------


def _create_starlette_app():
    """Create a minimal Starlette app with auth middleware for testing."""

    async def health(request):
        return JSONResponse({"status": "ok"})

    async def data(request):
        return JSONResponse({"value": 42})

    async def sse(request):
        return JSONResponse({"stream": "connected"})

    async def messages(request):
        return JSONResponse({"accepted": True})

    app = Starlette(
        routes=[
            Route("/health", endpoint=health),
            Route("/data", endpoint=data),
            Route("/sse", endpoint=sse),
            Route("/messages", endpoint=messages, methods=["POST"]),
        ],
    )
    starlette_auth_middleware(app)
    return app


class TestStarletteAuthMiddleware:
    """Tests for Starlette API key auth middleware (used by MCP SSE servers)."""

    def test_health_endpoint_bypasses_auth(self):
        app = _create_starlette_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_no_key_configured_allows_all(self):
        app = _create_starlette_app()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRADESTREAM_API_KEY", None)
            client = TestClient(app)
            resp = client.get("/sse")
            assert resp.status_code == 200

    def test_valid_api_key_on_sse(self):
        app = _create_starlette_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            client = TestClient(app)
            resp = client.get("/sse", headers={"X-API-Key": "secret123"})
            assert resp.status_code == 200

    def test_invalid_api_key_on_sse(self):
        app = _create_starlette_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            client = TestClient(app)
            resp = client.get("/sse", headers={"X-API-Key": "wrong"})
            assert resp.status_code == 401

    def test_missing_api_key_on_messages(self):
        app = _create_starlette_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            client = TestClient(app)
            resp = client.post("/messages")
            assert resp.status_code == 401

    def test_valid_api_key_on_messages(self):
        app = _create_starlette_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            client = TestClient(app)
            resp = client.post("/messages", headers={"X-API-Key": "secret123"})
            assert resp.status_code == 200

    def test_401_response_body(self):
        app = _create_starlette_app()
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            client = TestClient(app)
            resp = client.get("/data")
            assert resp.json()["error"] == "Invalid or missing API key"

    def test_jwt_bearer_token_authenticates(self):
        """A valid JWT Bearer token should authenticate via Starlette middleware."""
        from services.auth_api.auth_service import create_access_token

        app = _create_starlette_app()
        token = create_access_token("user-1", "user@example.com")
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            client = TestClient(app)
            resp = client.get("/data", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
