"""Tests for the error handling middleware."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.rest_api_shared.circuit_breaker import CircuitOpenError
from services.rest_api_shared.error_middleware import install_error_handlers


def _make_app():
    app = FastAPI()
    install_error_handlers(app)
    return app


class TestCircuitOpenHandler:
    def test_returns_503_with_retry_after(self):
        app = _make_app()

        @app.get("/test")
        async def test_route():
            raise CircuitOpenError("postgres", retry_after=30.0)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 503
        body = resp.json()
        assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "postgres" in body["error"]["message"]
        assert resp.headers["retry-after"] == "30"


class TestValidationHandler:
    def test_returns_422_with_details(self):
        from pydantic import BaseModel, Field

        app = _make_app()

        class Item(BaseModel):
            name: str = Field(..., min_length=1)
            count: int = Field(..., gt=0)

        @app.post("/items")
        async def create_item(item: Item):
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/items", json={"name": "", "count": -1})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert len(body["error"]["details"]) > 0


class TestUnhandledExceptionHandler:
    def test_returns_500_for_unhandled(self):
        app = _make_app()

        @app.get("/boom")
        async def boom():
            raise RuntimeError("unexpected")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "SERVER_ERROR"
        assert body["error"]["message"] == "Internal server error"
