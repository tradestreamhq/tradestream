"""Tests for the Risk Monitoring REST API."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.risk_monitoring_api.app import create_app


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


class TestRiskSummary:
    def test_get_summary_with_positions(self, client):
        tc, conn = client
        # First call: positions, second: strategy returns, third: portfolio returns
        conn.fetch.side_effect = [
            # positions
            [
                FakeRecord(
                    symbol="BTC/USD",
                    quantity=1.0,
                    avg_entry_price=60000.0,
                    unrealized_pnl=1000.0,
                ),
                FakeRecord(
                    symbol="ETH/USD",
                    quantity=10.0,
                    avg_entry_price=3000.0,
                    unrealized_pnl=500.0,
                ),
            ],
            # strategy returns (trades with spec_id)
            [
                FakeRecord(strategy_id="spec-1", pnl=100.0, exposure=10000.0),
                FakeRecord(strategy_id="spec-1", pnl=-50.0, exposure=10000.0),
                FakeRecord(strategy_id="spec-2", pnl=200.0, exposure=20000.0),
            ],
            # portfolio returns
            [
                FakeRecord(pnl=100.0, exposure=10000.0),
                FakeRecord(pnl=-50.0, exposure=10000.0),
                FakeRecord(pnl=200.0, exposure=20000.0),
            ],
        ]

        resp = tc.get("/summary")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_exposure"] == 90000.0
        assert "BTC/USD" in attrs["exposure_by_asset"]
        assert "ETH/USD" in attrs["exposure_by_asset"]
        assert attrs["position_count"] == 2
        assert attrs["strategy_count"] == 2

    def test_get_summary_empty_portfolio(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], [], []]

        resp = tc.get("/summary")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_exposure"] == 0
        assert attrs["position_count"] == 0
        assert attrs["concentration_alerts"] == []

    def test_get_summary_with_concentration_alert(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            # BTC is 90% of portfolio
            [
                FakeRecord(
                    symbol="BTC/USD",
                    quantity=1.0,
                    avg_entry_price=90000.0,
                    unrealized_pnl=0.0,
                ),
                FakeRecord(
                    symbol="ETH/USD",
                    quantity=1.0,
                    avg_entry_price=10000.0,
                    unrealized_pnl=0.0,
                ),
            ],
            [],
            [],
        ]

        resp = tc.get("/summary")
        assert resp.status_code == 200
        body = resp.json()
        alerts = body["data"]["attributes"]["concentration_alerts"]
        assert len(alerts) == 1
        assert alerts[0]["symbol"] == "BTC/USD"
        assert alerts[0]["weight"] == 0.9

    def test_get_summary_custom_lookback(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], [], []]

        resp = tc.get("/summary?lookback_days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["lookback_days"] == 7


class TestRiskByStrategy:
    def test_strategy_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get("/by-strategy/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_strategy_with_trades(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id="spec-1", name="RSI Reversal"
        )
        conn.fetch.side_effect = [
            # closed trades
            [
                FakeRecord(symbol="BTC/USD", pnl=500.0, quantity=0.1, entry_price=60000.0, exposure=6000.0),
                FakeRecord(symbol="BTC/USD", pnl=-200.0, quantity=0.1, entry_price=60000.0, exposure=6000.0),
            ],
            # open positions
            [
                FakeRecord(symbol="BTC/USD", quantity=0.05, entry_price=62000.0),
            ],
        ]

        resp = tc.get("/by-strategy/spec-1")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["strategy_name"] == "RSI Reversal"
        assert attrs["trade_count"] == 2
        assert attrs["win_rate"] == 0.5
        assert attrs["total_pnl"] == 300.0
        assert attrs["total_exposure"] == 3100.0

    def test_strategy_no_trades(self, client):
        tc, conn = client
        conn.fetchrow.return_value = FakeRecord(
            id="spec-2", name="MACD Trend"
        )
        conn.fetch.side_effect = [[], []]

        resp = tc.get("/by-strategy/spec-2")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["trade_count"] == 0
        assert attrs["win_rate"] is None
        assert attrs["total_pnl"] == 0


class TestRiskHistory:
    def test_get_history(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                trade_date=date(2026, 3, 1),
                daily_pnl=500.0,
                daily_exposure=50000.0,
                trade_count=5,
            ),
            FakeRecord(
                trade_date=date(2026, 3, 2),
                daily_pnl=-200.0,
                daily_exposure=45000.0,
                trade_count=3,
            ),
        ]

        resp = tc.get("/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["attributes"]["daily_pnl"] == 500.0
        assert body["data"][1]["attributes"]["daily_return"] == round(-200 / 45000, 4)

    def test_get_history_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/history?lookback_days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0
