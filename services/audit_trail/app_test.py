"""Tests for the Audit Trail REST API."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.audit_trail.app import create_app


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


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
    app = create_app(pool)
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestRecordEvent:
    def test_record_event(self, client):
        tc, conn = client
        conn.execute.return_value = None

        resp = tc.post(
            "/events?order_id=ORD-001&event_type=created&symbol=BTC/USD&strategy=macd"
        )
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["order_id"] == "ORD-001"
        assert attrs["event_type"] == "created"
        assert attrs["symbol"] == "BTC/USD"
        assert attrs["strategy"] == "macd"
        assert "event_id" in attrs
        assert "timestamp" in attrs

    def test_record_event_minimal(self, client):
        tc, conn = client
        conn.execute.return_value = None

        resp = tc.post("/events?order_id=ORD-002&event_type=submitted")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["event_type"] == "submitted"

    def test_record_event_invalid_type(self, client):
        tc, conn = client
        resp = tc.post("/events?order_id=ORD-003&event_type=invalid")
        assert resp.status_code == 422


class TestOrderTrail:
    def test_get_order_trail(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                event_id="evt-1",
                order_id="ORD-001",
                event_type="created",
                timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
                symbol="BTC/USD",
                strategy="macd",
                details='{"side": "BUY"}',
            ),
            FakeRecord(
                event_id="evt-2",
                order_id="ORD-001",
                event_type="filled",
                timestamp=datetime(2026, 3, 1, 10, 0, 5, tzinfo=timezone.utc),
                symbol="BTC/USD",
                strategy="macd",
                details='{"fill_price": 50000}',
            ),
        ]

        resp = tc.get("/orders/ORD-001")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["attributes"]["event_type"] == "created"
        assert body["data"][1]["attributes"]["event_type"] == "filled"

    def test_get_order_trail_not_found(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/orders/ORD-MISSING")
        assert resp.status_code == 404


class TestSearch:
    def test_search_by_symbol(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                event_id="evt-1",
                order_id="ORD-001",
                event_type="created",
                timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
                symbol="ETH/USD",
                strategy="sma",
                details="{}",
            )
        ]

        resp = tc.get("/search?symbol=ETH/USD")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_search_by_strategy(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/search?strategy=macd")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0

    def test_search_by_event_type(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/search?event_type=filled")
        assert resp.status_code == 200


class TestExportCSV:
    def test_export_csv(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                event_id="evt-1",
                order_id="ORD-001",
                event_type="created",
                timestamp=datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
                symbol="BTC/USD",
                strategy="macd",
                details='{"side": "BUY"}',
            )
        ]

        resp = tc.get("/export?symbol=BTC/USD")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "event_id" in resp.text
        assert "ORD-001" in resp.text

    def test_export_csv_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/export")
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) == 1  # header only
