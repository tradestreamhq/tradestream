"""Tests for the combined middleware stack."""

import json
import os
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from services.rest_api_shared.middleware import apply_middleware
from services.rest_api_shared.rate_limiter import RateLimitConfig


def _create_app(rate_limits=None, allowed_origins=None, max_body_bytes=1024 * 1024):
    async def index(request: Request):
        return JSONResponse({"ok": True})

    async def create(request: Request):
        body = await request.json()
        return JSONResponse({"received": body})

    async def health(request: Request):
        return JSONResponse({"status": "healthy"})

    app = Starlette(
        routes=[
            Route("/", endpoint=index),
            Route("/create", endpoint=create, methods=["POST"]),
            Route("/health", endpoint=health),
        ],
    )
    apply_middleware(
        app,
        rate_limits=rate_limits,
        allowed_origins=allowed_origins,
        max_body_bytes=max_body_bytes,
    )
    return app


class TestMiddlewareStack:
    def test_normal_get_request(self):
        app = _create_app()
        client = TestClient(app)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRADESTREAM_API_KEY", None)
            resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_cors_headers_present(self):
        app = _create_app(allowed_origins=["https://example.com"])
        client = TestClient(app)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRADESTREAM_API_KEY", None)
            resp = client.get("/", headers={"Origin": "https://example.com"})
        assert resp.headers.get("access-control-allow-origin") == "https://example.com"

    def test_rate_limiting_applies(self):
        limits = {"/": RateLimitConfig(max_requests=1, window_seconds=60)}
        app = _create_app(rate_limits=limits)
        client = TestClient(app)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRADESTREAM_API_KEY", None)
            assert client.get("/").status_code == 200
            assert client.get("/").status_code == 429

    def test_request_validation_applies(self):
        app = _create_app()
        client = TestClient(app)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRADESTREAM_API_KEY", None)
            resp = client.post(
                "/create",
                content="not json",
                headers={"content-type": "text/plain"},
            )
        assert resp.status_code == 415

    def test_health_bypasses_all(self):
        limits = {"/": RateLimitConfig(max_requests=0, window_seconds=60)}
        app = _create_app(rate_limits=limits)
        client = TestClient(app)
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret"}):
            # Health should bypass auth and rate limiting.
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_auth_still_works(self):
        app = _create_app()
        client = TestClient(app)
        with patch.dict(os.environ, {"TRADESTREAM_API_KEY": "secret123"}):
            resp = client.get("/")
            assert resp.status_code == 401

            resp = client.get("/", headers={"X-API-Key": "secret123"})
            assert resp.status_code == 200
