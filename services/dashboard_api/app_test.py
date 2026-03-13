"""Tests for the Dashboard REST API."""

from datetime import datetime, timezone
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


class TestOverview:
    def test_get_overview(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(portfolio_value=100000.0, total_unrealized_pnl=5000.0),
            FakeRecord(total_realized_pnl=12000.0, pnl_today=500.0, pnl_week=2000.0, pnl_month=8000.0),
            FakeRecord(active_strategies=5),
            FakeRecord(open_positions=3),
            FakeRecord(pending_alerts=2),
        ]

        resp = tc.get("/overview")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["portfolio_value"] == 100000.0
        assert attrs["pnl_today"] == 500.0
        assert attrs["active_strategies"] == 5
        assert attrs["open_positions"] == 3
        assert attrs["pending_alerts"] == 2

    def test_overview_cached(self, client):
        tc, conn = client
        conn.fetchrow.side_effect = [
            FakeRecord(portfolio_value=100000.0, total_unrealized_pnl=5000.0),
            FakeRecord(total_realized_pnl=12000.0, pnl_today=500.0, pnl_week=2000.0, pnl_month=8000.0),
            FakeRecord(active_strategies=5),
            FakeRecord(open_positions=3),
            FakeRecord(pending_alerts=2),
        ]

        resp1 = tc.get("/overview")
        assert resp1.status_code == 200

        # Second call should use cache (no additional DB calls needed)
        resp2 = tc.get("/overview")
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()
        # Only 5 fetchrow calls from the first request
        assert conn.fetchrow.call_count == 5


class TestPortfolioChart:
    def test_get_chart_default_period(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(ts=datetime(2026, 1, 1, tzinfo=timezone.utc), value=1000.0),
            FakeRecord(ts=datetime(2026, 1, 2, tzinfo=timezone.utc), value=1050.0),
        ]

        resp = tc.get("/portfolio-chart")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["period"] == "1m"
        assert len(attrs["points"]) == 2

    def test_get_chart_custom_period(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            FakeRecord(ts=datetime(2026, 1, 1, tzinfo=timezone.utc), value=500.0),
        ]

        resp = tc.get("/portfolio-chart?period=1w")
        assert resp.status_code == 200
        attrs = resp.json()["data"]["attributes"]
        assert attrs["period"] == "1w"

    def test_get_chart_invalid_period(self, client):
        tc, conn = client
        resp = tc.get("/portfolio-chart?period=2y")
        assert resp.status_code == 422


class TestTopStrategies:
    def test_get_top_strategies(self, client):
        tc, conn = client
        conn.fetch.side_effect = [
            # Main strategy query
            [
                FakeRecord(
                    id=1,
                    strategy_name="SMA Crossover",
                    status="active",
                    sharpe_ratio=1.5,
                    total_return=0.25,
                    max_drawdown=0.08,
                    total_trades=50,
                    win_rate=0.65,
                ),
            ],
            # Sparkline query
            [
                FakeRecord(day=datetime(2026, 1, 1, tzinfo=timezone.utc), daily_pnl=100.0),
                FakeRecord(day=datetime(2026, 1, 2, tzinfo=timezone.utc), daily_pnl=-50.0),
            ],
        ]

        resp = tc.get("/top-strategies")
        assert resp.status_code == 200
        body = resp.json()
        strategies = body["data"]["attributes"]["strategies"]
        assert len(strategies) == 1
        assert strategies[0]["strategy_name"] == "SMA Crossover"
        assert strategies[0]["sparkline"] == [100.0, -50.0]

    def test_top_strategies_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/top-strategies")
        assert resp.status_code == 200
        strategies = resp.json()["data"]["attributes"]["strategies"]
        assert strategies == []


class TestRecentActivity:
    def test_get_recent_activity(self, client):
        tc, conn = client
        now = datetime(2026, 3, 13, 12, 0, 0, tzinfo=timezone.utc)
        earlier = datetime(2026, 3, 13, 11, 0, 0, tzinfo=timezone.utc)

        conn.fetch.side_effect = [
            # Trades
            [
                FakeRecord(
                    activity_type="trade",
                    title="BTC/USD",
                    description="BUY 0.5 @ 60000",
                    occurred_at=now,
                    pnl=500.0,
                ),
            ],
            # Signals
            [
                FakeRecord(
                    activity_type="signal",
                    title="ETH/USD",
                    description="BUY signal (strength: 0.85)",
                    occurred_at=earlier,
                    pnl=None,
                ),
            ],
        ]

        resp = tc.get("/recent-activity")
        assert resp.status_code == 200
        body = resp.json()
        activities = body["data"]["attributes"]["activities"]
        assert len(activities) == 2
        # Sorted by time descending — trade (12:00) before signal (11:00)
        assert activities[0]["activity_type"] == "trade"
        assert activities[1]["activity_type"] == "signal"

    def test_recent_activity_custom_limit(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], []]

        resp = tc.get("/recent-activity?limit=5")
        assert resp.status_code == 200
        assert resp.json()["data"]["attributes"]["count"] == 0


class TestMarketSummary:
    def test_get_market_summary(self, client):
        tc, conn = client
        now = datetime(2026, 3, 13, 12, 0, 0, tzinfo=timezone.utc)

        conn.fetch.return_value = [FakeRecord(symbol="BTC/USD")]
        conn.fetchrow.side_effect = [
            FakeRecord(instrument="BTC/USD", price=65000.0, created_at=now),
            FakeRecord(price=63000.0),
        ]

        resp = tc.get("/market-summary")
        assert resp.status_code == 200
        body = resp.json()
        pairs = body["data"]["attributes"]["pairs"]
        assert len(pairs) == 1
        assert pairs[0]["symbol"] == "BTC/USD"
        assert pairs[0]["price"] == 65000.0
        expected_change = round((65000.0 - 63000.0) / 63000.0 * 100, 2)
        assert pairs[0]["change_24h_pct"] == expected_change

    def test_market_summary_no_prev_price(self, client):
        tc, conn = client
        now = datetime(2026, 3, 13, 12, 0, 0, tzinfo=timezone.utc)

        conn.fetch.return_value = [FakeRecord(symbol="ETH/USD")]
        conn.fetchrow.side_effect = [
            FakeRecord(instrument="ETH/USD", price=3500.0, created_at=now),
            None,  # No previous price
        ]

        resp = tc.get("/market-summary")
        assert resp.status_code == 200
        pairs = resp.json()["data"]["attributes"]["pairs"]
        assert pairs[0]["change_24h_pct"] == 0.0

    def test_market_summary_no_signals(self, client):
        tc, conn = client
        conn.fetch.return_value = [FakeRecord(symbol="SOL/USD")]
        conn.fetchrow.side_effect = [None, None]

        resp = tc.get("/market-summary")
        assert resp.status_code == 200
        pairs = resp.json()["data"]["attributes"]["pairs"]
        assert pairs[0]["price"] is None
