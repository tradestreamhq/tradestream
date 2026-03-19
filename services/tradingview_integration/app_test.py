"""Tests for the TradingView Integration API endpoints."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.tradingview_integration.app import create_app


class FakeRecord(dict):
    """Dict subclass that mimics asyncpg Record."""

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


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


class TestHealth:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


# ------------------------------------------------------------------
# Webhook Receiver
# ------------------------------------------------------------------


class TestWebhookReceiver:
    def test_valid_webhook(self, client):
        tc, conn = client
        conn_id = str(uuid.uuid4())

        # First call: look up connection by token
        conn.fetchrow.side_effect = [
            FakeRecord(
                id=conn_id,
                name="My BTC Strategy",
                strategy_name="momentum_btc",
                instrument="BTC/USD",
                alert_mapping=None,
                active=True,
            ),
            None,  # pine script lookup (if any)
        ]
        conn.execute.return_value = "INSERT 0 1"

        resp = tc.post(
            "/webhook/test-token-abc123",
            json={
                "ticker": "BTCUSD",
                "action": "buy",
                "price": 65000.0,
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["signal_type"] == "BUY"
        assert body["data"]["attributes"]["instrument"] == "BTC/USD"
        assert body["data"]["attributes"]["strategy_name"] == "momentum_btc"

    def test_invalid_token(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.post(
            "/webhook/invalid-token",
            json={"ticker": "BTCUSD", "action": "buy"},
        )
        assert resp.status_code == 401

    def test_disabled_connection(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=str(uuid.uuid4()),
            name="Disabled",
            strategy_name=None,
            instrument=None,
            alert_mapping=None,
            active=False,
        )

        resp = tc.post(
            "/webhook/disabled-token",
            json={"ticker": "BTCUSD", "action": "buy"},
        )
        assert resp.status_code == 403

    def test_invalid_payload(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id=str(uuid.uuid4()),
            name="Test",
            strategy_name=None,
            instrument=None,
            alert_mapping=None,
            active=True,
        )

        # Missing required fields
        resp = tc.post(
            "/webhook/some-token",
            json={"message": "no ticker or action"},
        )
        assert resp.status_code == 422

    def test_webhook_with_custom_mapping(self, client):
        tc, conn = client
        conn_id = str(uuid.uuid4())

        conn.fetchrow.side_effect = [
            FakeRecord(
                id=conn_id,
                name="Custom Mapping",
                strategy_name="custom_strat",
                instrument="ETH/USD",
                alert_mapping=json.dumps({"enter": "BUY", "exit": "SELL"}),
                active=True,
            ),
        ]
        conn.execute.return_value = "INSERT 0 1"

        resp = tc.post(
            "/webhook/custom-token",
            json={"ticker": "ETHUSD", "action": "enter", "price": 3200.0},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["data"]["attributes"]["signal_type"] == "BUY"

    def test_webhook_with_all_fields(self, client):
        tc, conn = client
        conn_id = str(uuid.uuid4())

        conn.fetchrow.side_effect = [
            FakeRecord(
                id=conn_id,
                name="Full Alert",
                strategy_name=None,
                instrument=None,
                alert_mapping=None,
                active=True,
            ),
        ]
        conn.execute.return_value = "INSERT 0 1"

        resp = tc.post(
            "/webhook/full-token",
            json={
                "ticker": "BINANCE:BTCUSDT",
                "action": "sell",
                "price": 65000.0,
                "stoploss": 66000.0,
                "takeprofit": 60000.0,
                "quantity": 0.5,
                "strategy": "tv_momentum",
                "message": "Death cross",
                "time": "2026-03-19T10:30:00Z",
                "interval": "4H",
                "exchange": "BINANCE",
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["signal_type"] == "SELL"
        assert attrs["instrument"] == "BTC/USDT"
        assert attrs["strategy_name"] == "tv_momentum"


# ------------------------------------------------------------------
# Connection Management
# ------------------------------------------------------------------


class TestConnections:
    def test_create_connection(self, client):
        tc, conn = client
        conn.execute.return_value = "INSERT 0 1"

        resp = tc.post(
            "/connections",
            json={"name": "My BTC Strategy", "strategy_name": "momentum_btc"},
        )

        assert resp.status_code == 201
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["name"] == "My BTC Strategy"
        assert "webhook_token" in attrs
        assert "webhook_url" in attrs
        assert attrs["active"] is True

    def test_list_connections(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                id=str(uuid.uuid4()),
                name="Strategy A",
                webhook_token="token-a",
                strategy_name="strat_a",
                instrument="BTC/USD",
                active=True,
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            ),
        ]

        resp = tc.get("/connections")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["attributes"]["name"] == "Strategy A"
        assert "webhook_url" in body["data"][0]["attributes"]

    def test_get_connection(self, client):
        tc, conn = client
        conn_id = str(uuid.uuid4())
        conn.fetchrow.return_value = FakeRecord(
            id=conn_id,
            name="My Strategy",
            webhook_token="secret-token",
            strategy_name="strat",
            instrument="ETH/USD",
            alert_mapping=None,
            active=True,
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        resp = tc.get(f"/connections/{conn_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["name"] == "My Strategy"

    def test_get_connection_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/connections/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_update_connection(self, client):
        tc, conn = client
        conn_id = str(uuid.uuid4())
        conn.fetchrow.return_value = FakeRecord(
            id=conn_id, name="Updated Name", active=True
        )

        resp = tc.patch(
            f"/connections/{conn_id}",
            json={"name": "Updated Name", "active": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["name"] == "Updated Name"

    def test_update_connection_no_fields(self, client):
        tc, conn = client
        resp = tc.patch(f"/connections/{uuid.uuid4()}", json={})
        assert resp.status_code == 422

    def test_delete_connection(self, client):
        tc, conn = client
        conn_id = str(uuid.uuid4())
        conn.execute.return_value = "UPDATE 1"

        resp = tc.delete(f"/connections/{conn_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "disconnected"

    def test_delete_connection_not_found(self, client):
        tc, conn = client
        conn.execute.return_value = "UPDATE 0"

        resp = tc.delete(f"/connections/{uuid.uuid4()}")
        assert resp.status_code == 404


# ------------------------------------------------------------------
# Pine Script Generator
# ------------------------------------------------------------------


class TestPineScript:
    def test_generate_indicator(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(webhook_token="token-xyz")

        resp = tc.post(
            "/pine-script",
            json={
                "strategy_name": "momentum_btc",
                "template_type": "indicator",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["template_type"] == "indicator"
        assert "//@version=5" in attrs["pine_script"]
        assert "indicator(" in attrs["pine_script"]
        assert "token-xyz" in attrs["webhook_url"]

    def test_generate_strategy(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None  # No existing connection

        resp = tc.post(
            "/pine-script",
            json={
                "strategy_name": "test_strat",
                "template_type": "strategy",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert "strategy(" in attrs["pine_script"]
        assert attrs["webhook_url"] == "<YOUR_WEBHOOK_URL>"

    def test_invalid_template_type(self, client):
        tc, conn = client
        resp = tc.post(
            "/pine-script",
            json={
                "strategy_name": "test",
                "template_type": "invalid",
            },
        )
        assert resp.status_code == 422


# ------------------------------------------------------------------
# Webhook Log
# ------------------------------------------------------------------


class TestWebhookLog:
    def test_get_log(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                id=str(uuid.uuid4()),
                connection_id=str(uuid.uuid4()),
                signal_id=str(uuid.uuid4()),
                raw_payload='{"ticker": "BTCUSD", "action": "buy"}',
                created_at=datetime(2026, 3, 19, tzinfo=timezone.utc),
                connection_name="My Strategy",
            )
        ]

        resp = tc.get("/webhook-log")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1

    def test_get_log_filtered(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get(f"/webhook-log?connection_id={uuid.uuid4()}&limit=10")
        assert resp.status_code == 200
