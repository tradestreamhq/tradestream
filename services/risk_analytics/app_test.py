"""Tests for the Portfolio Risk Analytics API and core calculations."""

import json
import math
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.risk_analytics.app import create_app
from services.risk_analytics.risk_service import (
    RiskSnapshot,
    StrategyReturn,
    build_risk_snapshot,
    compute_concentration,
    compute_correlation_matrix,
    compute_current_drawdown,
    compute_max_drawdown,
    compute_portfolio_returns,
    compute_sharpe_ratio,
    compute_sortino_ratio,
    compute_var,
)


# --- Helpers ---


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


# --- Realistic mock data ---

STRATEGY_A_RETURNS = [
    0.012, -0.005, 0.008, -0.003, 0.015, -0.010, 0.007, 0.002,
    -0.008, 0.011, 0.004, -0.006, 0.009, -0.002, 0.013, -0.007,
    0.006, 0.003, -0.004, 0.010, -0.001, 0.008, -0.009, 0.005,
    0.011, -0.003, 0.007, -0.005, 0.014, -0.006,
]

STRATEGY_B_RETURNS = [
    -0.003, 0.009, -0.002, 0.011, -0.008, 0.014, -0.005, 0.006,
    0.010, -0.007, 0.003, 0.008, -0.004, 0.012, -0.009, 0.005,
    -0.001, 0.007, 0.011, -0.006, 0.004, -0.003, 0.013, -0.008,
    0.002, 0.009, -0.005, 0.010, -0.007, 0.006,
]

STRATEGY_C_RETURNS = [
    0.005, 0.003, -0.002, 0.007, -0.001, 0.004, 0.002, -0.003,
    0.006, -0.004, 0.008, -0.001, 0.003, 0.005, -0.006, 0.009,
    -0.002, 0.004, -0.003, 0.007, 0.001, -0.005, 0.006, 0.002,
    -0.004, 0.008, -0.001, 0.003, 0.005, -0.002,
]


def _make_strategy_returns():
    return [
        StrategyReturn("strat-a", STRATEGY_A_RETURNS, capital_allocated=50000.0),
        StrategyReturn("strat-b", STRATEGY_B_RETURNS, capital_allocated=30000.0),
        StrategyReturn("strat-c", STRATEGY_C_RETURNS, capital_allocated=20000.0),
    ]


# ===================================================================
# Unit tests — risk_service.py
# ===================================================================


class TestComputeVar:
    def test_returns_none_for_insufficient_data(self):
        assert compute_var([]) is None
        assert compute_var([0.01]) is None

    def test_positive_returns_gives_zero_var(self):
        returns = [0.01, 0.02, 0.03, 0.04, 0.05]
        var = compute_var(returns, 0.95)
        assert var == 0.0

    def test_negative_returns_gives_positive_var(self):
        returns = [-0.05, -0.03, -0.01, 0.02, 0.04, -0.02, 0.01, -0.04,
                   0.03, -0.06, 0.05, -0.01, 0.02, -0.03, 0.01, -0.02,
                   0.04, -0.05, 0.03, -0.01]
        var = compute_var(returns, 0.95)
        assert var is not None
        assert var > 0

    def test_var_99_greater_than_var_95(self):
        returns = [-0.05, -0.03, -0.01, 0.02, 0.04, -0.02, 0.01, -0.04,
                   0.03, -0.06, 0.05, -0.01, 0.02, -0.03, 0.01, -0.02,
                   0.04, -0.05, 0.03, -0.01]
        var_95 = compute_var(returns, 0.95)
        var_99 = compute_var(returns, 0.99)
        assert var_99 >= var_95


class TestComputeMaxDrawdown:
    def test_returns_none_for_insufficient_data(self):
        assert compute_max_drawdown([]) is None
        assert compute_max_drawdown([100.0]) is None

    def test_monotonic_increase_has_zero_drawdown(self):
        curve = [100, 110, 120, 130, 140]
        dd = compute_max_drawdown(curve)
        assert dd == pytest.approx(0.0)

    def test_known_drawdown(self):
        # Peak at 200, drops to 150 = 25% drawdown
        curve = [100, 150, 200, 180, 150, 190]
        dd = compute_max_drawdown(curve)
        assert dd == pytest.approx(0.25)

    def test_multiple_drawdowns_takes_max(self):
        curve = [100, 200, 160, 180, 300, 210]
        dd = compute_max_drawdown(curve)
        # 300 -> 210 = 30% vs 200 -> 160 = 20%. Max = 30%
        assert dd == pytest.approx(0.30)


class TestComputeCurrentDrawdown:
    def test_returns_none_for_empty(self):
        assert compute_current_drawdown([]) is None

    def test_at_peak_gives_zero(self):
        dd = compute_current_drawdown([100, 110, 120])
        assert dd == pytest.approx(0.0)

    def test_below_peak(self):
        dd = compute_current_drawdown([100, 200, 150])
        assert dd == pytest.approx(0.25)


class TestComputeSharpeRatio:
    def test_returns_none_for_insufficient_data(self):
        assert compute_sharpe_ratio([]) is None
        assert compute_sharpe_ratio([0.01]) is None

    def test_zero_volatility_returns_none(self):
        assert compute_sharpe_ratio([0.01, 0.01, 0.01]) is None

    def test_positive_returns_positive_sharpe(self):
        returns = [0.01, 0.02, 0.015, 0.008, 0.012, 0.018, 0.005,
                   0.011, 0.009, 0.014]
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe is not None
        assert sharpe > 0

    def test_negative_returns_negative_sharpe(self):
        returns = [-0.01, -0.02, -0.015, -0.008, -0.012]
        sharpe = compute_sharpe_ratio(returns)
        assert sharpe is not None
        assert sharpe < 0


class TestComputeSortinoRatio:
    def test_returns_none_for_insufficient_data(self):
        assert compute_sortino_ratio([]) is None

    def test_all_positive_returns_none(self):
        # No downside deviation
        assert compute_sortino_ratio([0.01, 0.02, 0.03]) is None

    def test_mixed_returns_gives_value(self):
        returns = [0.01, -0.005, 0.02, -0.01, 0.015, -0.003]
        sortino = compute_sortino_ratio(returns)
        assert sortino is not None

    def test_sortino_greater_than_sharpe_for_skewed_returns(self):
        # Mostly positive with small negatives -> sortino > sharpe
        returns = [0.03, 0.02, -0.001, 0.025, 0.015, -0.002, 0.01,
                   0.02, -0.001, 0.03]
        sharpe = compute_sharpe_ratio(returns)
        sortino = compute_sortino_ratio(returns)
        assert sharpe is not None
        assert sortino is not None
        assert sortino > sharpe


class TestComputeConcentration:
    def test_empty_allocations(self):
        assert compute_concentration({}) == {}

    def test_single_strategy(self):
        result = compute_concentration({"a": 100000.0})
        assert result == {"a": 1.0}

    def test_equal_allocation(self):
        result = compute_concentration({"a": 50000, "b": 50000})
        assert result["a"] == pytest.approx(0.5)
        assert result["b"] == pytest.approx(0.5)

    def test_unequal_allocation(self):
        result = compute_concentration({"a": 60000, "b": 30000, "c": 10000})
        assert result["a"] == pytest.approx(0.6)
        assert result["b"] == pytest.approx(0.3)
        assert result["c"] == pytest.approx(0.1)

    def test_zero_total(self):
        result = compute_concentration({"a": 0, "b": 0})
        assert result["a"] == 0.0


class TestComputeCorrelationMatrix:
    def test_single_strategy(self):
        sr = [StrategyReturn("a", [0.01, 0.02, 0.03])]
        corr = compute_correlation_matrix(sr)
        assert corr["a"]["a"] == 1.0

    def test_perfectly_correlated(self):
        sr = [
            StrategyReturn("a", [0.01, 0.02, 0.03, 0.04]),
            StrategyReturn("b", [0.02, 0.04, 0.06, 0.08]),
        ]
        corr = compute_correlation_matrix(sr)
        assert corr["a"]["b"] == pytest.approx(1.0, abs=0.001)

    def test_negatively_correlated(self):
        sr = [
            StrategyReturn("a", [0.01, 0.02, 0.03, 0.04, 0.05]),
            StrategyReturn("b", [-0.01, -0.02, -0.03, -0.04, -0.05]),
        ]
        corr = compute_correlation_matrix(sr)
        assert corr["a"]["b"] == pytest.approx(-1.0, abs=0.001)

    def test_three_strategies(self):
        sr = _make_strategy_returns()
        corr = compute_correlation_matrix(sr)
        # Diagonal should be 1.0
        for s in ["strat-a", "strat-b", "strat-c"]:
            assert corr[s][s] == pytest.approx(1.0, abs=0.001)
        # Should be symmetric
        assert corr["strat-a"]["strat-b"] == pytest.approx(
            corr["strat-b"]["strat-a"], abs=0.001
        )

    def test_insufficient_data_returns_identity(self):
        sr = [
            StrategyReturn("a", [0.01]),
            StrategyReturn("b", [0.02]),
        ]
        corr = compute_correlation_matrix(sr)
        assert corr["a"]["a"] == 1.0
        assert corr["a"]["b"] == 0.0


class TestComputePortfolioReturns:
    def test_empty_returns_empty(self):
        assert compute_portfolio_returns([]) == []

    def test_single_strategy(self):
        sr = [StrategyReturn("a", [0.01, 0.02], capital_allocated=100.0)]
        result = compute_portfolio_returns(sr)
        assert result == pytest.approx([0.01, 0.02])

    def test_weighted_combination(self):
        sr = [
            StrategyReturn("a", [0.10, 0.20], capital_allocated=75.0),
            StrategyReturn("b", [0.20, 0.10], capital_allocated=25.0),
        ]
        result = compute_portfolio_returns(sr)
        # 0.75 * 0.10 + 0.25 * 0.20 = 0.125
        # 0.75 * 0.20 + 0.25 * 0.10 = 0.175
        assert result[0] == pytest.approx(0.125)
        assert result[1] == pytest.approx(0.175)


class TestBuildRiskSnapshot:
    def test_full_snapshot(self):
        sr = _make_strategy_returns()
        snapshot = build_risk_snapshot(sr, portfolio_value=100000.0)

        assert snapshot.total_exposure == 100000.0
        assert snapshot.net_position == 100000.0
        assert snapshot.portfolio_value == 100000.0
        assert snapshot.strategy_count == 3
        assert snapshot.var_95 is not None
        assert snapshot.max_drawdown is not None
        assert snapshot.sharpe_ratio is not None
        assert snapshot.strategy_concentrations["strat-a"] == pytest.approx(0.5)
        assert snapshot.strategy_concentrations["strat-b"] == pytest.approx(0.3)
        assert snapshot.strategy_concentrations["strat-c"] == pytest.approx(0.2)

    def test_empty_strategies(self):
        snapshot = build_risk_snapshot([], portfolio_value=0.0)
        assert snapshot.total_exposure == 0.0
        assert snapshot.strategy_count == 0
        assert snapshot.var_95 is None


# ===================================================================
# Integration tests — API endpoints
# ===================================================================


def _mock_strategy_perf_rows():
    """Return mock DB rows for strategy_performance query."""
    rows = []
    for i, ret in enumerate(STRATEGY_A_RETURNS[:5]):
        rows.append(
            FakeRecord(
                strategy_id="strat-a",
                total_return=ret,
                period_start=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, i + 2, tzinfo=timezone.utc),
            )
        )
    for i, ret in enumerate(STRATEGY_B_RETURNS[:5]):
        rows.append(
            FakeRecord(
                strategy_id="strat-b",
                total_return=ret,
                period_start=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
                period_end=datetime(2026, 1, i + 2, tzinfo=timezone.utc),
            )
        )
    return rows


def _mock_alloc_rows():
    return [
        FakeRecord(strategy_id="strat-a", capital=60000.0),
        FakeRecord(strategy_id="strat-b", capital=40000.0),
    ]


def _setup_conn_for_risk(conn):
    """Configure mock conn to return realistic data for risk endpoints."""
    conn.fetch.side_effect = [
        _mock_strategy_perf_rows(),
        _mock_alloc_rows(),
    ]
    conn.fetchrow.return_value = FakeRecord(total_value=100000.0)


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200


class TestRiskEndpoint:
    def test_get_risk_snapshot(self, client):
        tc, conn = client
        _setup_conn_for_risk(conn)

        resp = tc.get("/risk")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["total_exposure"] == 100000.0
        assert attrs["strategy_count"] == 2
        assert "strategy_concentrations" in attrs
        assert "var_95" in attrs
        assert "sharpe_ratio" in attrs

    def test_get_risk_no_data(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], []]
        conn.fetchrow.return_value = FakeRecord(total_value=0.0)

        resp = tc.get("/risk")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["strategy_count"] == 0
        assert attrs["total_exposure"] == 0.0


class TestRiskHistoryEndpoint:
    def test_get_risk_history(self, client):
        tc, conn = client
        snap_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=snap_id,
                total_exposure=100000.0,
                net_position=100000.0,
                portfolio_value=100000.0,
                var_95=0.025,
                var_99=0.04,
                max_drawdown=0.08,
                current_drawdown=0.02,
                sharpe_ratio=1.5,
                sortino_ratio=2.1,
                strategy_concentrations={"strat-a": 0.6, "strat-b": 0.4},
                strategy_count=2,
                snapshot_type="PERIODIC",
                created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("/risk/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["meta"]["total"] == 1
        attrs = body["data"][0]["attributes"]
        assert attrs["total_exposure"] == 100000.0

    def test_get_risk_history_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("/risk/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0

    def test_get_risk_history_pagination(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 50

        resp = tc.get("/risk/history?limit=10&offset=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["limit"] == 10
        assert body["meta"]["offset"] == 20


class TestCorrelationEndpoint:
    def test_get_correlation(self, client):
        tc, conn = client
        _setup_conn_for_risk(conn)

        resp = tc.get("/correlation")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["strategy_count"] == 2
        assert "matrix" in attrs
        matrix = attrs["matrix"]
        assert matrix["strat-a"]["strat-a"] == pytest.approx(1.0, abs=0.01)

    def test_get_correlation_empty(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[], []]
        conn.fetchrow.return_value = FakeRecord(total_value=0.0)

        resp = tc.get("/correlation")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["strategy_count"] == 0
