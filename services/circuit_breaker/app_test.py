"""Tests for the Circuit Breaker REST API."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.circuit_breaker.app import create_app
from services.circuit_breaker.models import BreakerLevel


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


@pytest.fixture
def client():
    pool, conn = _make_pool()
    app = create_app(pool, poll_interval=999999)
    return TestClient(app, raise_server_exceptions=False), app


class TestHealthEndpoints:
    def test_health(self, client):
        tc, app = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "circuit-breaker"


class TestStatus:
    def test_get_status_initial(self, client):
        tc, app = client
        resp = tc.get("/status")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["level"] == "NORMAL"
        assert attrs["is_halted"] is False
        assert attrs["trading_allowed"] is True
        assert "thresholds" in attrs
        assert attrs["thresholds"]["warning"] == 0.05
        assert attrs["thresholds"]["halt"] == 0.10
        assert attrs["thresholds"]["emergency"] == 0.20

    def test_get_status_after_halt(self, client):
        tc, app = client
        breaker = app.state.breaker
        breaker.update_equity(10000.0)
        breaker.update_equity(9000.0, strategies=["MACD_CROSSOVER"])

        resp = tc.get("/status")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["level"] == "HALT"
        assert attrs["is_halted"] is True
        assert attrs["trading_allowed"] is False
        assert "MACD_CROSSOVER" in attrs["halted_strategies"]
        assert len(attrs["recent_events"]) > 0


class TestReset:
    def test_reset_halted_breaker(self, client):
        tc, app = client
        breaker = app.state.breaker
        breaker.update_equity(10000.0)
        breaker.update_equity(9000.0, strategies=["STRAT_A"])
        assert breaker.state.is_halted is True

        resp = tc.post("/reset", json={"acknowledged_by": "admin@tradestream.io"})
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["level"] == "NORMAL"
        assert attrs["is_halted"] is False
        assert attrs["trading_allowed"] is True
        assert attrs["reset_by"] == "admin@tradestream.io"

    def test_reset_not_halted_returns_409(self, client):
        tc, app = client
        resp = tc.post("/reset", json={"acknowledged_by": "admin"})
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "NOT_HALTED"

    def test_reset_missing_body_returns_422(self, client):
        tc, app = client
        resp = tc.post("/reset", json={})
        assert resp.status_code == 422

    def test_reset_empty_acknowledged_by_returns_422(self, client):
        tc, app = client
        resp = tc.post("/reset", json={"acknowledged_by": ""})
        assert resp.status_code == 422


class TestResponseFormat:
    def test_status_follows_rmm_envelope(self, client):
        tc, app = client
        resp = tc.get("/status")
        body = resp.json()
        assert "data" in body
        assert body["data"]["type"] == "circuit_breaker_status"
        assert "attributes" in body["data"]

    def test_reset_follows_rmm_envelope(self, client):
        tc, app = client
        breaker = app.state.breaker
        breaker.update_equity(10000.0)
        breaker.update_equity(9000.0)

        resp = tc.post("/reset", json={"acknowledged_by": "admin"})
        body = resp.json()
        assert "data" in body
        assert body["data"]["type"] == "circuit_breaker_reset"
