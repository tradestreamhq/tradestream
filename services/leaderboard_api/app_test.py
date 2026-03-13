"""Tests for the Leaderboard REST API."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.leaderboard_api.app import (
    Period,
    SortMetric,
    _normalize_equity_curves,
    create_app,
    period_start_date,
)


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


def _make_leaderboard_row(
    impl_id=None,
    spec_id=None,
    name="Test Strategy",
    status="VALIDATED",
    total_return=0.15,
    sharpe_ratio=1.5,
    max_drawdown=-0.10,
    win_rate=0.55,
    profit_factor=1.8,
    total_trades=100,
    record_count=5,
):
    return FakeRecord(
        implementation_id=impl_id or uuid.uuid4(),
        spec_id=spec_id or uuid.uuid4(),
        strategy_name=name,
        status=status,
        total_return=total_return,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        record_count=record_count,
    )


def _make_comparison_row(
    impl_id=None,
    spec_id=None,
    name="Test Strategy",
    status="VALIDATED",
    total_return=0.15,
    sharpe_ratio=1.5,
    sortino_ratio=2.0,
    max_drawdown=-0.10,
    win_rate=0.55,
    profit_factor=1.8,
    total_trades=100,
    winning_trades=55,
    losing_trades=45,
    annualized_return=0.30,
    volatility=0.12,
    record_count=5,
):
    return FakeRecord(
        implementation_id=impl_id or uuid.uuid4(),
        spec_id=spec_id or uuid.uuid4(),
        strategy_name=name,
        status=status,
        total_return=total_return,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        annualized_return=annualized_return,
        volatility=volatility,
        record_count=record_count,
    )


# --- Period calculation tests ---


class TestPeriodStartDate:
    def test_seven_days(self):
        result = period_start_date(Period.SEVEN_DAYS)
        assert result is not None
        now = datetime.now(timezone.utc)
        delta = now - result
        assert 6.9 < delta.total_seconds() / 86400 < 7.1

    def test_thirty_days(self):
        result = period_start_date(Period.THIRTY_DAYS)
        assert result is not None
        now = datetime.now(timezone.utc)
        delta = now - result
        assert 29.9 < delta.total_seconds() / 86400 < 30.1

    def test_ninety_days(self):
        result = period_start_date(Period.NINETY_DAYS)
        assert result is not None
        now = datetime.now(timezone.utc)
        delta = now - result
        assert 89.9 < delta.total_seconds() / 86400 < 90.1

    def test_ytd(self):
        result = period_start_date(Period.YTD)
        assert result is not None
        now = datetime.now(timezone.utc)
        assert result.year == now.year
        assert result.month == 1
        assert result.day == 1

    def test_all_time(self):
        result = period_start_date(Period.ALL_TIME)
        assert result is None


# --- Ranking logic tests ---


class TestRankingLogic:
    def test_leaderboard_returns_ranked_list(self, client):
        tc, conn = client
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        conn.fetch.return_value = [
            _make_leaderboard_row(impl_id=id1, name="Alpha", sharpe_ratio=2.0),
            _make_leaderboard_row(impl_id=id2, name="Beta", sharpe_ratio=1.5),
        ]

        resp = tc.get("/leaderboard?period=30d&sort_by=sharpe")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["attributes"]["rank"] == 1
        assert body["data"][0]["attributes"]["strategy_name"] == "Alpha"
        assert body["data"][1]["attributes"]["rank"] == 2

    def test_leaderboard_default_params(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        resp = tc.get("/leaderboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []

    def test_leaderboard_sort_by_total_return(self, client):
        tc, conn = client
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        conn.fetch.return_value = [
            _make_leaderboard_row(impl_id=id1, name="High Return", total_return=0.50),
            _make_leaderboard_row(impl_id=id2, name="Low Return", total_return=0.10),
        ]

        resp = tc.get("/leaderboard?sort_by=total_return")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["data"][0]["attributes"]["rank"] == 1

    def test_leaderboard_all_periods(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        for period in ["7d", "30d", "90d", "ytd", "all_time"]:
            resp = tc.get(f"/leaderboard?period={period}")
            assert resp.status_code == 200

    def test_leaderboard_invalid_period(self, client):
        tc, conn = client
        resp = tc.get("/leaderboard?period=invalid")
        assert resp.status_code == 422

    def test_leaderboard_invalid_sort(self, client):
        tc, conn = client
        resp = tc.get("/leaderboard?sort_by=invalid")
        assert resp.status_code == 422


# --- Comparison tests ---


class TestComparison:
    def test_compare_strategies(self, client):
        tc, conn = client
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        conn.fetch.side_effect = [
            # comparison query
            [
                _make_comparison_row(impl_id=id1, name="Alpha"),
                _make_comparison_row(impl_id=id2, name="Beta"),
            ],
            # equity curve query
            [],
        ]

        resp = tc.get(f"/leaderboard/compare?ids={id1},{id2}")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["strategies"]) == 2
        assert attrs["period"] == "30d"

    def test_compare_no_ids(self, client):
        tc, conn = client
        resp = tc.get("/leaderboard/compare?ids=")
        assert resp.status_code == 422

    def test_compare_too_many_ids(self, client):
        tc, conn = client
        ids = ",".join(str(uuid.uuid4()) for _ in range(11))
        resp = tc.get(f"/leaderboard/compare?ids={ids}")
        assert resp.status_code == 422

    def test_compare_with_equity_curves(self, client):
        tc, conn = client
        id1 = uuid.uuid4()
        now = datetime.now(timezone.utc)
        conn.fetch.side_effect = [
            [_make_comparison_row(impl_id=id1, name="Alpha")],
            [
                FakeRecord(
                    implementation_id=id1,
                    strategy_name="Alpha",
                    period_start=now - timedelta(days=2),
                    period_end=now - timedelta(days=1),
                    total_return=0.05,
                ),
                FakeRecord(
                    implementation_id=id1,
                    strategy_name="Alpha",
                    period_start=now - timedelta(days=1),
                    period_end=now,
                    total_return=0.03,
                ),
            ],
        ]

        resp = tc.get(f"/leaderboard/compare?ids={id1}")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        curves = attrs["equity_curves"]
        assert str(id1) in curves
        points = curves[str(id1)]["points"]
        assert len(points) == 2
        # First equity = 1.0 * (1 + 0.05) = 1.05
        assert abs(points[0]["equity"] - 1.05) < 0.001
        # Second equity = 1.05 * (1 + 0.03) = 1.0815
        assert abs(points[1]["equity"] - 1.0815) < 0.001


# --- Equity curve normalization tests ---


class TestEquityCurveNormalization:
    def test_empty_rows(self):
        result = _normalize_equity_curves([])
        assert result == {}

    def test_single_strategy(self):
        id1 = uuid.uuid4()
        now = datetime.now(timezone.utc)
        rows = [
            FakeRecord(
                implementation_id=id1,
                strategy_name="Alpha",
                period_start=now - timedelta(days=2),
                period_end=now - timedelta(days=1),
                total_return=0.10,
            ),
            FakeRecord(
                implementation_id=id1,
                strategy_name="Alpha",
                period_start=now - timedelta(days=1),
                period_end=now,
                total_return=-0.05,
            ),
        ]
        result = _normalize_equity_curves(rows)
        assert str(id1) in result
        points = result[str(id1)]["points"]
        assert len(points) == 2
        assert abs(points[0]["equity"] - 1.10) < 0.001
        assert abs(points[1]["equity"] - 1.045) < 0.001

    def test_multiple_strategies(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(timezone.utc)
        rows = [
            FakeRecord(
                implementation_id=id1,
                strategy_name="Alpha",
                period_start=now - timedelta(days=1),
                period_end=now,
                total_return=0.10,
            ),
            FakeRecord(
                implementation_id=id2,
                strategy_name="Beta",
                period_start=now - timedelta(days=1),
                period_end=now,
                total_return=0.20,
            ),
        ]
        result = _normalize_equity_curves(rows)
        assert len(result) == 2
        assert abs(result[str(id1)]["points"][0]["equity"] - 1.10) < 0.001
        assert abs(result[str(id2)]["points"][0]["equity"] - 1.20) < 0.001

    def test_null_return_treated_as_zero(self):
        id1 = uuid.uuid4()
        now = datetime.now(timezone.utc)
        rows = [
            FakeRecord(
                implementation_id=id1,
                strategy_name="Alpha",
                period_start=now - timedelta(days=1),
                period_end=now,
                total_return=None,
            ),
        ]
        result = _normalize_equity_curves(rows)
        assert abs(result[str(id1)]["points"][0]["equity"] - 1.0) < 0.001


# --- Cache tests ---


class TestCaching:
    def test_leaderboard_caches_response(self, client):
        tc, conn = client
        conn.fetch.return_value = [
            _make_leaderboard_row(name="Cached Strategy"),
        ]

        resp1 = tc.get("/leaderboard?period=7d&sort_by=sharpe")
        resp2 = tc.get("/leaderboard?period=7d&sort_by=sharpe")
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Should only have called fetch once (second was cached)
        assert conn.fetch.call_count == 1

    def test_different_params_not_cached(self, client):
        tc, conn = client
        conn.fetch.return_value = []

        tc.get("/leaderboard?period=7d&sort_by=sharpe")
        tc.get("/leaderboard?period=30d&sort_by=sharpe")
        assert conn.fetch.call_count == 2


# --- Health endpoint tests ---


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
