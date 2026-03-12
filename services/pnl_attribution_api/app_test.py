"""Tests for the PnL Attribution REST API."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.pnl_attribution_api.app import create_app


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


def _strategy_rows():
    return [
        FakeRecord(
            strategy_type="momentum",
            trade_count=5,
            total_pnl=1000.0,
            winning_trades=3,
            losing_trades=2,
            avg_win=500.0,
            avg_loss=-250.0,
        ),
        FakeRecord(
            strategy_type="mean_reversion",
            trade_count=3,
            total_pnl=500.0,
            winning_trades=2,
            losing_trades=1,
            avg_win=400.0,
            avg_loss=-300.0,
        ),
    ]


def _asset_rows():
    return [
        FakeRecord(symbol="BTC/USD", trade_count=4, total_pnl=800.0),
        FakeRecord(symbol="ETH/USD", trade_count=4, total_pnl=700.0),
    ]


def _direction_rows():
    return [
        FakeRecord(side="BUY", trade_count=5, total_pnl=1200.0),
        FakeRecord(side="SELL", trade_count=3, total_pnl=300.0),
    ]


def _time_rows():
    return [
        FakeRecord(
            bucket=datetime(2026, 3, 10, tzinfo=timezone.utc),
            trade_count=4,
            total_pnl=600.0,
            winning_trades=3,
            losing_trades=1,
        ),
        FakeRecord(
            bucket=datetime(2026, 3, 9, tzinfo=timezone.utc),
            trade_count=4,
            total_pnl=900.0,
            winning_trades=2,
            losing_trades=2,
        ),
    ]


def _setup_conn(conn):
    """Set up mock conn to return proper data for each query in compute_attribution."""
    # compute_attribution calls fetch 4 times (strategy, asset, direction, time)
    # and fetchrow 2 times (realized pnl, unrealized pnl)
    conn.fetch.side_effect = [
        _strategy_rows(),
        _asset_rows(),
        _direction_rows(),
        _time_rows(),
    ]
    conn.fetchrow.side_effect = [
        FakeRecord(realized_pnl=1500.0),
        FakeRecord(unrealized_pnl=200.0),
    ]


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestAttribution:
    def test_get_full_attribution(self, client):
        tc, conn = client
        _setup_conn(conn)

        resp = tc.get("/attribution?period=daily")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_pnl"] == 1700.0
        assert attrs["total_trades"] == 8
        assert len(attrs["by_strategy"]) == 2
        assert len(attrs["by_asset"]) == 2
        assert len(attrs["by_direction"]) == 2
        assert attrs["realization"]["realized_pnl"] == 1500.0
        assert attrs["realization"]["unrealized_pnl"] == 200.0
        assert len(attrs["by_time"]) == 2

    def test_get_full_attribution_with_dates(self, client):
        tc, conn = client
        _setup_conn(conn)

        resp = tc.get("/attribution?start=2026-03-01&end=2026-03-12")
        assert resp.status_code == 200

    def test_get_full_attribution_invalid_start(self, client):
        tc, conn = client
        resp = tc.get("/attribution?start=not-a-date")
        assert resp.status_code == 422

    def test_get_full_attribution_weekly(self, client):
        tc, conn = client
        _setup_conn(conn)

        resp = tc.get("/attribution?period=weekly")
        assert resp.status_code == 200

    def test_get_full_attribution_monthly(self, client):
        tc, conn = client
        _setup_conn(conn)

        resp = tc.get("/attribution?period=monthly")
        assert resp.status_code == 200


class TestStrategyAttribution:
    def test_get_strategy_attribution(self, client):
        tc, conn = client
        _setup_conn(conn)

        resp = tc.get("/attribution/strategies")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["strategies"]) == 2
        momentum = attrs["strategies"][0]
        assert momentum["strategy_type"] == "momentum"
        assert momentum["hit_rate"] == 0.6
        assert momentum["total_pnl"] == 1000.0


class TestAssetAttribution:
    def test_get_asset_attribution(self, client):
        tc, conn = client
        _setup_conn(conn)

        resp = tc.get("/attribution/assets")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["assets"]) == 2
        btc = attrs["assets"][0]
        assert btc["symbol"] == "BTC/USD"
        assert btc["total_pnl"] == 800.0


class TestEmptyData:
    def test_attribution_no_trades(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], [], [], []]
        conn.fetchrow.side_effect = [
            FakeRecord(realized_pnl=0.0),
            FakeRecord(unrealized_pnl=0.0),
        ]

        resp = tc.get("/attribution")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_pnl"] == 0.0
        assert attrs["total_trades"] == 0
        assert attrs["by_strategy"] == []
        assert attrs["by_asset"] == []
