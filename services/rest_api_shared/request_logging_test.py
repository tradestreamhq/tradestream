"""Tests for request logging middleware."""

import logging

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from services.rest_api_shared.request_logging import (
    DEFAULT_SENSITIVE_HEADERS,
    _mask_headers,
    fastapi_request_logging,
)


def _create_app(log_headers=False):
    async def index(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/", endpoint=index)])
    fastapi_request_logging(app, log_headers=log_headers)
    return app


class TestMaskHeaders:
    def test_masks_authorization(self):
        headers = {"Authorization": "Bearer secret", "Accept": "application/json"}
        masked = _mask_headers(headers, DEFAULT_SENSITIVE_HEADERS)
        assert masked["Authorization"] == "***"
        assert masked["Accept"] == "application/json"

    def test_masks_api_key(self):
        headers = {"X-API-Key": "my-key"}
        masked = _mask_headers(headers, DEFAULT_SENSITIVE_HEADERS)
        assert masked["X-API-Key"] == "***"

    def test_masks_cookie(self):
        headers = {"Cookie": "session=abc123"}
        masked = _mask_headers(headers, DEFAULT_SENSITIVE_HEADERS)
        assert masked["Cookie"] == "***"

    def test_preserves_safe_headers(self):
        headers = {"Content-Type": "application/json", "Accept": "text/html"}
        masked = _mask_headers(headers, DEFAULT_SENSITIVE_HEADERS)
        assert masked == headers


class TestRequestLogging:
    def test_logs_request(self, caplog):
        app = _create_app()
        client = TestClient(app)
        with caplog.at_level(logging.INFO, logger="tradestream.request"):
            resp = client.get("/")
        assert resp.status_code == 200
        assert any(
            "GET" in record.message and "200" in record.message
            for record in caplog.records
        )

    def test_response_passthrough(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
