"""Tests for the Strategy Leaderboard API."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.leaderboard_api.app import (
    TimePeriod,
    _period_start,
    compute_composite_score,
    create_app,
)


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


# --- Unit tests for scoring ---


class TestCompositeScore:
    def test_all_zeros(self):
        score = compute_composite_score(0, 0, 0, 0, 0)
        assert score == pytest.approx(0.2, abs=0.01)  # only max_drawdown contributes (1.0 * 0.20)

    def test_strong_strategy(self):
        score = compute_composite_score(
            sharpe_ratio=2.0,
            total_return=1.5,
            max_drawdown=-0.1,
            win_rate=0.65,
            total_trades=200,
        )
        assert score > 0.5
        assert score <= 1.0

    def test_negative_sharpe_clamped(self):
        score = compute_composite_score(
            sharpe_ratio=-1.0,
            total_return=-0.5,
            max_drawdown=-0.5,
            win_rate=0.3,
            total_trades=10,
        )
        # Negative sharpe and return contribute 0
        assert score >= 0.0
        assert score < 0.5

    def test_none_values_treated_as_zero(self):
        score = compute_composite_score(None, None, None, None, 0)
        assert score == pytest.approx(0.2, abs=0.01)

    def test_custom_weights(self):
        weights = {
            "sharpe_ratio": 1.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "total_trades": 0.0,
        }
        score = compute_composite_score(2.0, 0, 0, 0, 0, weights=weights)
        # sharpe=2.0 normalized: 2/(2+1) = 0.6667
        assert score == pytest.approx(0.6667, abs=0.01)


class TestPeriodStart:
    def test_all_returns_none(self):
        assert _period_start(TimePeriod.ALL) is None

    def test_one_day(self):
        now = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
        start = _period_start(TimePeriod.ONE_DAY, now=now)
        assert start == datetime(2026, 3, 11, 12, 0, tzinfo=timezone.utc)

    def test_ytd(self):
        now = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
        start = _period_start(TimePeriod.YTD, now=now)
        assert start == datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_one_week(self):
        now = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
        start = _period_start(TimePeriod.ONE_WEEK, now=now)
        assert start == datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc)

    def test_three_months(self):
        now = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
        start = _period_start(TimePeriod.THREE_MONTHS, now=now)
        assert start == datetime(2025, 12, 12, 12, 0, tzinfo=timezone.utc)


# --- API endpoint tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "leaderboard-api"


class TestLeaderboardEndpoint:
    def _make_row(self, impl_id=None, strategy_name="macd", **overrides):
        defaults = {
            "implementation_id": impl_id or uuid.uuid4(),
            "strategy_name": strategy_name,
            "instrument": "BTC/USD",
            "environment": "BACKTEST",
            "avg_sharpe_ratio": Decimal("1.5000"),
            "total_return": Decimal("0.4500"),
            "max_drawdown": Decimal("-0.1200"),
            "avg_win_rate": Decimal("0.5800"),
            "total_trades": 150,
            "avg_sortino_ratio": Decimal("2.0000"),
            "avg_profit_factor": Decimal("1.8000"),
            "latest_period_end": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "record_count": 5,
        }
        defaults.update(overrides)
        return FakeRecord(**defaults)

    def test_leaderboard_returns_entries(self, client):
        tc, conn = client
        impl_id = uuid.uuid4()
        conn.fetch.return_value = [self._make_row(impl_id=impl_id)]
        conn.fetchval.return_value = 1

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1
        entry = body["data"][0]
        assert entry["type"] == "leaderboard_entry"
        attrs = entry["attributes"]
        assert attrs["implementation_id"] == str(impl_id)
        assert attrs["strategy_name"] == "macd"
        assert "composite_score" in attrs
        assert attrs["composite_score"] > 0

    def test_leaderboard_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0
        assert body["data"] == []

    def test_leaderboard_with_period_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._make_row()]
        conn.fetchval.return_value = 1

        resp = tc.get("/?period=1w")
        assert resp.status_code == 200

    def test_leaderboard_with_environment_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._make_row(environment="LIVE")]
        conn.fetchval.return_value = 1

        resp = tc.get("/?environment=LIVE")
        assert resp.status_code == 200

    def test_leaderboard_with_instrument_filter(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._make_row(instrument="ETH/USD")]
        conn.fetchval.return_value = 1

        resp = tc.get("/?instrument=ETH/USD")
        assert resp.status_code == 200

    def test_leaderboard_sort_by_sharpe(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            self._make_row(strategy_name="rsi", avg_sharpe_ratio=Decimal("2.5000")),
            self._make_row(strategy_name="macd", avg_sharpe_ratio=Decimal("1.0000")),
        ]
        conn.fetchval.return_value = 2

        resp = tc.get("/?sort_by=sharpe_ratio")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2

    def test_leaderboard_sort_by_composite(self, client):
        tc, conn = client
        row_a = self._make_row(
            strategy_name="weak",
            avg_sharpe_ratio=Decimal("0.5000"),
            total_return=Decimal("0.1000"),
            total_trades=10,
        )
        row_b = self._make_row(
            strategy_name="strong",
            avg_sharpe_ratio=Decimal("2.5000"),
            total_return=Decimal("1.5000"),
            total_trades=200,
        )
        conn.fetch.return_value = [row_a, row_b]
        conn.fetchval.return_value = 2

        resp = tc.get("/?sort_by=composite_score")
        assert resp.status_code == 200
        body = resp.json()
        entries = body["data"]
        # Strong strategy should rank first after Python re-sort
        assert entries[0]["attributes"]["strategy_name"] == "strong"
        assert entries[1]["attributes"]["strategy_name"] == "weak"

    def test_leaderboard_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = [self._make_row()]
        conn.fetchval.return_value = 10

        resp = tc.get("/?limit=1&offset=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 1
        assert body["meta"]["offset"] == 5
        assert body["meta"]["total"] == 10

    def test_leaderboard_db_error(self, client):
        tc, conn = client
        conn.fetch.side_effect = Exception("connection lost")

        resp = tc.get("/")
        assert resp.status_code == 500


class TestScoringWeightsEndpoint:
    def test_get_weights(self, client):
        tc, conn = client
        resp = tc.get("/scoring-weights")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["sharpe_ratio"] == 0.35
        assert attrs["total_return"] == 0.25
        assert attrs["max_drawdown"] == 0.20
        assert attrs["win_rate"] == 0.15
        assert attrs["total_trades"] == 0.05
