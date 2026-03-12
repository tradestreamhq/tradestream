"""Tests for the Dashboard REST API."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.dashboard_api.app import create_app


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
        assert resp.json()["service"] == "dashboard-api"


class TestStrategyPerformance:
    def test_performance_found(self, client):
        tc, conn = client
        strategy_id = str(uuid.uuid4())

        # First call: check strategy exists
        # Second call: fetch performance
        conn.fetchrow.side_effect = [
            FakeRecord(id=strategy_id, name="RSI Momentum"),
            FakeRecord(
                total_records=5,
                total_trades=100,
                winning_trades=60,
                losing_trades=40,
                total_pnl=Decimal("1500.50"),
                avg_sharpe_ratio=Decimal("1.45"),
                max_drawdown=Decimal("-0.12"),
                avg_win_rate=Decimal("0.60"),
                avg_profit_factor=Decimal("1.80"),
                avg_sortino_ratio=Decimal("2.10"),
                avg_volatility=Decimal("0.15"),
            ),
        ]

        resp = tc.get(f"/strategies/{strategy_id}/performance")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["strategy_name"] == "RSI Momentum"
        assert attrs["total_trades"] == 100
        assert attrs["winning_trades"] == 60
        assert attrs["win_rate"] == 0.6
        assert attrs["total_pnl"] == 1500.50
        assert attrs["sharpe_ratio"] == 1.45
        assert attrs["period"] == "30d"
        assert body["data"]["id"] == strategy_id

    def test_performance_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/strategies/{uuid.uuid4()}/performance")
        assert resp.status_code == 404

    def test_performance_with_period(self, client):
        tc, conn = client
        strategy_id = str(uuid.uuid4())
        conn.fetchrow.side_effect = [
            FakeRecord(id=strategy_id, name="MACD Cross"),
            FakeRecord(
                total_records=2,
                total_trades=30,
                winning_trades=18,
                losing_trades=12,
                total_pnl=Decimal("500.00"),
                avg_sharpe_ratio=Decimal("1.20"),
                max_drawdown=Decimal("-0.08"),
                avg_win_rate=Decimal("0.60"),
                avg_profit_factor=Decimal("1.50"),
                avg_sortino_ratio=Decimal("1.80"),
                avg_volatility=Decimal("0.10"),
            ),
        ]

        resp = tc.get(f"/strategies/{strategy_id}/performance?period=7d")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["period"] == "7d"

    def test_performance_no_trades(self, client):
        tc, conn = client
        strategy_id = str(uuid.uuid4())
        conn.fetchrow.side_effect = [
            FakeRecord(id=strategy_id, name="Empty Strategy"),
            FakeRecord(
                total_records=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl=Decimal("0"),
                avg_sharpe_ratio=None,
                max_drawdown=None,
                avg_win_rate=None,
                avg_profit_factor=None,
                avg_sortino_ratio=None,
                avg_volatility=None,
            ),
        ]

        resp = tc.get(f"/strategies/{strategy_id}/performance")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["win_rate"] == 0.0
        assert attrs["total_trades"] == 0


class TestStrategyTrades:
    def test_trades_found(self, client):
        tc, conn = client
        strategy_id = str(uuid.uuid4())
        trade_id = uuid.uuid4()

        conn.fetchrow.return_value = FakeRecord(id=strategy_id)
        conn.fetch.return_value = [
            FakeRecord(
                id=trade_id,
                instrument="BTC-USD",
                action="BUY",
                entry_price=Decimal("50000.00"),
                exit_price=Decimal("52000.00"),
                pnl_absolute=Decimal("200.00"),
                pnl_percent=Decimal("4.00"),
                hold_duration=timedelta(hours=6),
                exit_reason="take_profit",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                exit_timestamp=datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/strategies/{strategy_id}/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["instrument"] == "BTC-USD"
        assert attrs["entry_price"] == 50000.00
        assert attrs["exit_price"] == 52000.00
        assert attrs["pnl_absolute"] == 200.00
        assert body["meta"]["total"] == 1

    def test_trades_not_found_strategy(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/strategies/{uuid.uuid4()}/trades")
        assert resp.status_code == 404

    def test_trades_pagination(self, client):
        tc, conn = client
        strategy_id = str(uuid.uuid4())

        conn.fetchrow.return_value = FakeRecord(id=strategy_id)
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get(f"/strategies/{strategy_id}/trades?limit=10&offset=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 20


class TestPortfolioSummary:
    def test_summary_with_positions(self, client):
        tc, conn = client

        conn.fetch.return_value = [
            FakeRecord(
                symbol="BTC-USD",
                quantity=Decimal("0.5"),
                avg_entry_price=Decimal("50000.00"),
                unrealized_pnl=Decimal("1000.00"),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            FakeRecord(
                symbol="ETH-USD",
                quantity=Decimal("10.0"),
                avg_entry_price=Decimal("3000.00"),
                unrealized_pnl=Decimal("-200.00"),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        conn.fetchrow.side_effect = [
            FakeRecord(
                total_trades=50,
                winning_trades=30,
                losing_trades=20,
                total_realized_pnl=Decimal("5000.00"),
            ),
            FakeRecord(open_count=3),
        ]

        resp = tc.get("/portfolio/summary")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["position_count"] == 2
        assert attrs["total_unrealized_pnl"] == 800.00
        assert attrs["total_realized_pnl"] == 5000.00
        assert attrs["total_pnl"] == 5800.00
        assert "BTC-USD" in attrs["allocation"]
        assert "ETH-USD" in attrs["allocation"]
        assert attrs["trade_stats"]["total_trades"] == 50
        assert attrs["open_trade_count"] == 3

    def test_summary_empty_portfolio(self, client):
        tc, conn = client

        conn.fetch.return_value = []
        conn.fetchrow.side_effect = [
            FakeRecord(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_realized_pnl=Decimal("0"),
            ),
            FakeRecord(open_count=0),
        ]

        resp = tc.get("/portfolio/summary")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["position_count"] == 0
        assert attrs["total_pnl"] == 0.0
        assert attrs["allocation"] == {}
