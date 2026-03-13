"""Tests for request validation middleware."""

import json

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from services.rest_api_shared.request_validation import (
    DEFAULT_MAX_BODY_BYTES,
    fastapi_request_validation,
)


def _create_app(max_body_bytes=DEFAULT_MAX_BODY_BYTES):
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
    fastapi_request_validation(app, max_body_bytes=max_body_bytes)
    return app


class TestContentTypeCheck:
    def test_post_with_json_content_type(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.post(
            "/create",
            json={"name": "test"},
        )
        assert resp.status_code == 200

    def test_post_without_json_content_type(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.post(
            "/create",
            content="not json",
            headers={"content-type": "text/plain"},
        )
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"

    def test_get_without_content_type_is_fine(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200


class TestBodySizeLimit:
    def test_body_within_limit(self):
        app = _create_app(max_body_bytes=1024)
        client = TestClient(app)
        resp = client.post(
            "/create",
            json={"x": "a" * 100},
        )
        assert resp.status_code == 200

    def test_body_exceeds_limit(self):
        app = _create_app(max_body_bytes=10)
        client = TestClient(app)
        resp = client.post(
            "/create",
            content=json.dumps({"x": "a" * 100}),
            headers={
                "content-type": "application/json",
                "content-length": "200",
            },
        )
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


class TestInputSanitization:
    def test_clean_query_params(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.get("/?search=hello")
        assert resp.status_code == 200

    def test_script_tag_in_query(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.get("/?search=<script>alert(1)</script>")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_INPUT"

    def test_sql_injection_in_query(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.get("/?id=1;DROP TABLE users")
        assert resp.status_code == 400


class TestBypassPaths:
    def test_health_bypasses_validation(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
