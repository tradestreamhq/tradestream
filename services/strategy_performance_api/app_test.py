"""Tests for the Strategy Performance Dashboard REST API."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.strategy_performance_api.app import create_app


class FakeRecord(dict):
    """dict-like object that also supports attribute access (like asyncpg.Record)."""

    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    """Create a mock asyncpg pool with async context manager support."""
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
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-performance-api"


class TestPerformanceEndpoint:
    def test_get_performance(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=strategy_id),  # impl exists check
            FakeRecord(
                cumulative_pnl=Decimal("0.1523"),
                win_rate=Decimal("0.65"),
                trade_count=42,
                avg_hold_time_seconds=3600,
                avg_sharpe_ratio=Decimal("1.85"),
                avg_max_drawdown=Decimal("0.12"),
                avg_profit_factor=Decimal("2.1"),
            ),
        ]

        resp = tc.get(f"/{strategy_id}/performance")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["strategy_id"] == str(strategy_id)
        assert attrs["cumulative_pnl"] == pytest.approx(0.1523)
        assert attrs["win_rate"] == pytest.approx(0.65)
        assert attrs["trade_count"] == 42
        assert attrs["avg_hold_time_seconds"] == 3600

    def test_get_performance_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/{uuid.uuid4()}/performance")
        assert resp.status_code == 404

    def test_get_performance_no_data(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=strategy_id),
            FakeRecord(
                cumulative_pnl=Decimal("0"),
                win_rate=Decimal("0"),
                trade_count=0,
                avg_hold_time_seconds=0,
                avg_sharpe_ratio=None,
                avg_max_drawdown=None,
                avg_profit_factor=None,
            ),
        ]

        resp = tc.get(f"/{strategy_id}/performance")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["trade_count"] == 0
        assert attrs["cumulative_pnl"] == 0

    def test_get_performance_with_filters(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.side_effect = [
            FakeRecord(id=strategy_id),
            FakeRecord(
                cumulative_pnl=Decimal("0.05"),
                win_rate=Decimal("0.7"),
                trade_count=10,
                avg_hold_time_seconds=1800,
                avg_sharpe_ratio=Decimal("2.0"),
                avg_max_drawdown=Decimal("0.08"),
                avg_profit_factor=Decimal("1.5"),
            ),
        ]

        resp = tc.get(
            f"/{strategy_id}/performance",
            params={
                "instrument": "BTC/USD",
                "environment": "BACKTEST",
                "from_date": "2026-01-01",
                "to_date": "2026-03-01",
            },
        )
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["trade_count"] == 10


class TestTradesEndpoint:
    def test_list_trades(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        signal_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=strategy_id)
        conn.fetch.return_value = [
            FakeRecord(
                id=signal_id,
                instrument="BTC/USD",
                signal_type="BUY",
                strength=Decimal("0.85"),
                entry_price=Decimal("45000.00"),
                exit_price=Decimal("46500.00"),
                pnl=Decimal("1500.00"),
                pnl_percent=Decimal("3.33"),
                outcome="PROFIT",
                stop_loss=Decimal("44000.00"),
                take_profit=Decimal("47000.00"),
                created_at=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
                exit_time=datetime(2026, 1, 16, 8, 0, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get(f"/{strategy_id}/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        trade = body["data"][0]["attributes"]
        assert trade["instrument"] == "BTC/USD"
        assert trade["pnl"] == 1500.00
        assert trade["outcome"] == "PROFIT"

    def test_list_trades_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None

        resp = tc.get(f"/{uuid.uuid4()}/trades")
        assert resp.status_code == 404

    def test_list_trades_with_pagination(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=strategy_id)
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get(f"/{strategy_id}/trades", params={"limit": 10, "offset": 20})
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 20

    def test_list_trades_with_filters(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=strategy_id)
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get(
            f"/{strategy_id}/trades",
            params={
                "instrument": "ETH/USD",
                "from_date": "2026-01-01",
                "to_date": "2026-02-01",
                "sort_by": "pnl",
                "sort_order": "desc",
            },
        )
        assert resp.status_code == 200

    def test_list_trades_empty(self, client):
        tc, conn = client
        strategy_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(id=strategy_id)
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get(f"/{strategy_id}/trades")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
        assert body["data"] == []


class TestLeaderboardEndpoint:
    def test_leaderboard(self, client):
        tc, conn = client
        impl_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                implementation_id=impl_id,
                strategy_name="MACD_RSI",
                total_return=Decimal("0.2534"),
                win_rate=Decimal("0.72"),
                trade_count=85,
                avg_sharpe_ratio=Decimal("2.1"),
                avg_max_drawdown=Decimal("0.09"),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/leaderboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        ranking = body["data"][0]["attributes"]
        assert ranking["rank"] == 1
        assert ranking["strategy_name"] == "MACD_RSI"
        assert ranking["total_return"] == pytest.approx(0.2534)

    def test_leaderboard_with_filters(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get(
            "/leaderboard",
            params={
                "instrument": "BTC/USD",
                "environment": "LIVE",
                "from_date": "2026-01-01",
                "to_date": "2026-03-01",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["meta"]["total"] == 0

    def test_leaderboard_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/leaderboard", params={"limit": 5, "offset": 10})
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 5
        assert body["meta"]["offset"] == 10

    def test_leaderboard_multiple_strategies(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(
                implementation_id=uuid.uuid4(),
                strategy_name="MACD_RSI",
                total_return=Decimal("0.30"),
                win_rate=Decimal("0.72"),
                trade_count=85,
                avg_sharpe_ratio=Decimal("2.1"),
                avg_max_drawdown=Decimal("0.09"),
            ),
            FakeRecord(
                implementation_id=uuid.uuid4(),
                strategy_name="SMA_BB",
                total_return=Decimal("0.15"),
                win_rate=Decimal("0.60"),
                trade_count=50,
                avg_sharpe_ratio=Decimal("1.5"),
                avg_max_drawdown=Decimal("0.15"),
            ),
        ]
        conn.fetchval.return_value = 2

        resp = tc.get("/leaderboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 2
        assert body["data"][0]["attributes"]["rank"] == 1
        assert body["data"][1]["attributes"]["rank"] == 2
        assert (
            body["data"][0]["attributes"]["total_return"]
            > body["data"][1]["attributes"]["total_return"]
        )
