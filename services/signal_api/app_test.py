"""Tests for the Signal REST API."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.signal_api.app import create_app


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


class TestSubscribe:
    def test_subscribe_success(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None  # no existing subscription
        conn.execute.return_value = "INSERT 0 1"

        resp = tc.post(
            "/subscribe",
            json={"channel": "telegram", "endpoint": "12345"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["channel"] == "telegram"
        assert "subscription_id" in body["data"]["attributes"]

    def test_subscribe_duplicate(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(id=str(uuid.uuid4()))

        resp = tc.post(
            "/subscribe",
            json={"channel": "webhook", "endpoint": "https://example.com/hook"},
        )
        assert resp.status_code == 409

    def test_subscribe_invalid_channel(self, client):
        tc, conn = client
        resp = tc.post(
            "/subscribe",
            json={"channel": "sms", "endpoint": "+1234567890"},
        )
        assert resp.status_code == 422

    def test_subscribe_with_filters(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        conn.execute.return_value = "INSERT 0 1"

        resp = tc.post(
            "/subscribe",
            json={
                "channel": "telegram",
                "endpoint": "99999",
                "strategies": ["momentum_btc"],
                "pairs": ["BTC/USD"],
            },
        )
        assert resp.status_code == 201


class TestUnsubscribe:
    def test_unsubscribe_success(self, client):
        tc, conn = client
        conn.execute.return_value = "UPDATE 1"
        sub_id = str(uuid.uuid4())

        resp = tc.delete(f"/subscribe/{sub_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "unsubscribed"

    def test_unsubscribe_not_found(self, client):
        tc, conn = client
        conn.execute.return_value = "UPDATE 0"

        resp = tc.delete(f"/subscribe/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestListSubscriptions:
    def test_list_active(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                id=str(uuid.uuid4()),
                channel="telegram",
                endpoint="12345",
                strategies=None,
                pairs=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/subscribe")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["channel"] == "telegram"


class TestLatestSignals:
    def test_get_latest(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                id=str(uuid.uuid4()),
                strategy_name="momentum_btc",
                instrument="BTC/USD",
                direction="BUY",
                entry_price=65000.0,
                stop_loss=63000.0,
                take_profit=70000.0,
                confidence=0.85,
                timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["direction"] == "BUY"
        assert attrs["instrument"] == "BTC/USD"

    def test_get_latest_with_filters(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/?strategy=momentum_btc&pair=BTC/USD&limit=5")
        assert resp.status_code == 200


class TestSignalHistory:
    def test_history(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [
            FakeRecord(
                id=str(uuid.uuid4()),
                strategy_name="mean_reversion",
                instrument="ETH/USD",
                direction="SELL",
                entry_price=3200.0,
                stop_loss=3400.0,
                take_profit=2800.0,
                confidence=0.72,
                outcome="PROFIT",
                exit_price=2850.0,
                pnl=350.0,
                pnl_percent=10.94,
                timestamp=datetime(2026, 2, 15, tzinfo=timezone.utc),
            )
        ]

        resp = tc.get("/history?limit=10&strategy=mean_reversion")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1

    def test_history_date_range(self, client):
        tc, conn = client
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []

        resp = tc.get("/history?start_date=2026-01-01&end_date=2026-03-01")
        assert resp.status_code == 200


class TestPerformance:
    def test_performance(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                strategy_name="momentum_btc",
                total_signals=100,
                wins=65,
                losses=30,
                pending=5,
                win_rate_pct=68.42,
                avg_return_pct=2.5,
                max_drawdown_pct=-8.3,
                total_pnl=15000.0,
            )
        ]

        resp = tc.get("/performance")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["win_rate_pct"] == 68.42
        assert attrs["total_pnl"] == 15000.0

    def test_performance_filtered(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/performance?strategy=nonexistent")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0
