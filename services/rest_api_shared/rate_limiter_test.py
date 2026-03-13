"""Tests for the rate limiter middleware."""

import json

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from services.rest_api_shared.rate_limiter import (
    RateLimitConfig,
    RateLimitStore,
    fastapi_rate_limiter,
)


def _create_app(route_limits=None, store=None):
    async def index(request):
        return JSONResponse({"ok": True})

    async def other(request):
        return JSONResponse({"other": True})

    app = Starlette(
        routes=[
            Route("/", endpoint=index),
            Route("/other", endpoint=other),
        ],
    )
    fastapi_rate_limiter(app, route_limits=route_limits, store=store)
    return app


class TestRateLimiter:
    def test_allows_requests_within_limit(self):
        limits = {"/": RateLimitConfig(max_requests=5, window_seconds=60)}
        app = _create_app(route_limits=limits)
        client = TestClient(app)
        for _ in range(5):
            resp = client.get("/")
            assert resp.status_code == 200

    def test_blocks_requests_over_limit(self):
        limits = {"/": RateLimitConfig(max_requests=2, window_seconds=60)}
        store = RateLimitStore()
        app = _create_app(route_limits=limits, store=store)
        client = TestClient(app)

        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        resp = client.get("/")
        assert resp.status_code == 429

    def test_429_has_retry_after_header(self):
        limits = {"/": RateLimitConfig(max_requests=1, window_seconds=60)}
        app = _create_app(route_limits=limits)
        client = TestClient(app)

        client.get("/")
        resp = client.get("/")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) > 0

    def test_429_response_body(self):
        limits = {"/": RateLimitConfig(max_requests=1, window_seconds=60)}
        app = _create_app(route_limits=limits)
        client = TestClient(app)

        client.get("/")
        resp = client.get("/")
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMITED"

    def test_per_route_limits(self):
        limits = {
            "/": RateLimitConfig(max_requests=1, window_seconds=60),
            "/other": RateLimitConfig(max_requests=3, window_seconds=60),
        }
        app = _create_app(route_limits=limits)
        client = TestClient(app)

        # "/" is limited to 1
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 429

        # "/other" still has capacity
        for _ in range(3):
            assert client.get("/other").status_code == 200
        assert client.get("/other").status_code == 429

    def test_no_matching_route_passes_through(self):
        limits = {"/api": RateLimitConfig(max_requests=1, window_seconds=60)}
        app = _create_app(route_limits=limits)
        client = TestClient(app)

        # "/" doesn't match "/api" prefix, so no rate limiting.
        for _ in range(10):
            assert client.get("/").status_code == 200


class TestRateLimitStore:
    def test_window_reset(self):
        store = RateLimitStore()
        allowed, _ = store.is_allowed("k", max_requests=1, window_seconds=0)
        assert allowed
        # Window of 0 seconds means immediate reset.
        allowed, _ = store.is_allowed("k", max_requests=1, window_seconds=0)
        assert allowed
