"""Tests for the Risk Dashboard REST API."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.risk_dashboard.app import create_app


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
        assert resp.json()["service"] == "risk-dashboard"


class TestDashboardEndpoint:
    def test_dashboard_empty_portfolio(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            [],  # positions
            [],  # daily PnL
        ]
        conn.fetchval.side_effect = [
            0,     # active strategy count
            0.0,   # unrealized
            0.0,   # realized
        ]

        resp = tc.get("/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["position_count"] == 0
        assert attrs["var_95"]["var_absolute"] == 0.0
        assert attrs["total_exposure"] == 0.0

    def test_dashboard_with_positions(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            # positions
            [
                FakeRecord(
                    symbol="BTC/USD",
                    quantity=0.5,
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
            # daily PnL rows
            [
                FakeRecord(symbol="BTC/USD", trade_date=datetime(2026, 3, 1), daily_pnl=300.0),
                FakeRecord(symbol="BTC/USD", trade_date=datetime(2026, 3, 2), daily_pnl=-150.0),
                FakeRecord(symbol="BTC/USD", trade_date=datetime(2026, 3, 3), daily_pnl=200.0),
                FakeRecord(symbol="BTC/USD", trade_date=datetime(2026, 3, 4), daily_pnl=-100.0),
                FakeRecord(symbol="BTC/USD", trade_date=datetime(2026, 3, 5), daily_pnl=250.0),
                FakeRecord(symbol="ETH/USD", trade_date=datetime(2026, 3, 1), daily_pnl=150.0),
                FakeRecord(symbol="ETH/USD", trade_date=datetime(2026, 3, 2), daily_pnl=-75.0),
                FakeRecord(symbol="ETH/USD", trade_date=datetime(2026, 3, 3), daily_pnl=100.0),
                FakeRecord(symbol="ETH/USD", trade_date=datetime(2026, 3, 4), daily_pnl=-50.0),
                FakeRecord(symbol="ETH/USD", trade_date=datetime(2026, 3, 5), daily_pnl=125.0),
            ],
        ]
        conn.fetchval.side_effect = [
            5,       # active strategy count
            1500.0,  # unrealized
            3000.0,  # realized
        ]

        resp = tc.get("/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]

        assert attrs["position_count"] == 2
        assert attrs["active_strategy_count"] == 5
        assert attrs["total_exposure"] == 60000.0
        assert attrs["var_95"]["confidence_level"] == 0.95
        assert attrs["var_95"]["var_absolute"] > 0
        assert attrs["var_99"]["confidence_level"] == 0.99
        assert attrs["concentration"]["herfindahl_index"] > 0
        assert "BTC/USD" in attrs["concentration"]["asset_weights"]
        assert "ETH/USD" in attrs["concentration"]["asset_weights"]
        assert attrs["portfolio_beta"]["benchmark"] == "BTC/USD"

    def test_dashboard_handles_error(self, client):
        tc, conn = client
        conn.fetch.side_effect = Exception("DB connection lost")

        resp = tc.get("/dashboard")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "SERVER_ERROR"
