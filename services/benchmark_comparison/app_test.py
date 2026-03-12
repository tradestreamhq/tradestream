"""Tests for the Benchmark Comparison REST API."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from services.benchmark_comparison.app import create_app


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


class TestBenchmarkComparison:
    def _strategy_returns(self):
        return [
            FakeRecord(daily_return=0.01),
            FakeRecord(daily_return=-0.005),
            FakeRecord(daily_return=0.02),
            FakeRecord(daily_return=0.003),
            FakeRecord(daily_return=-0.01),
        ]

    def _benchmark_returns(self):
        return [
            FakeRecord(daily_return=0.005),
            FakeRecord(daily_return=-0.002),
            FakeRecord(daily_return=0.015),
            FakeRecord(daily_return=0.001),
            FakeRecord(daily_return=-0.005),
        ]

    def test_get_comparison_default_benchmarks(self, client):
        tc, conn = client
        strat_returns = self._strategy_returns()
        bench_returns = self._benchmark_returns()

        # First call returns strategy returns, next 3 return benchmark returns
        conn.fetch.side_effect = [
            strat_returns,
            bench_returns,
            bench_returns,
            bench_returns,
        ]

        resp = tc.get("/strat-123")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["strategy_id"] == "strat-123"
        assert len(attrs["comparisons"]) == 3

    def test_get_comparison_custom_benchmarks(self, client):
        tc, conn = client
        strat_returns = self._strategy_returns()
        bench_returns = self._benchmark_returns()

        conn.fetch.side_effect = [strat_returns, bench_returns]

        resp = tc.get("/strat-456?benchmarks=SPY&period=1m")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["comparisons"]) == 1
        assert attrs["comparisons"][0]["benchmark"] == "SPY"

    def test_strategy_not_found(self, client):
        tc, conn = client
        conn.fetch.side_effect = [[]]  # no strategy returns

        resp = tc.get("/nonexistent")
        assert resp.status_code == 404

    def test_benchmark_not_found_skipped(self, client):
        tc, conn = client
        strat_returns = self._strategy_returns()

        # Strategy returns exist, but all benchmarks return empty
        conn.fetch.side_effect = [strat_returns, [], [], []]

        resp = tc.get("/strat-789")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["comparisons"]) == 0

    def test_period_ytd(self, client):
        tc, conn = client
        strat_returns = self._strategy_returns()
        bench_returns = self._benchmark_returns()

        conn.fetch.side_effect = [
            strat_returns,
            bench_returns,
            bench_returns,
            bench_returns,
        ]

        resp = tc.get("/strat-123?period=ytd")
        assert resp.status_code == 200

    def test_comparison_metrics_present(self, client):
        tc, conn = client
        strat_returns = self._strategy_returns()
        bench_returns = self._benchmark_returns()

        conn.fetch.side_effect = [strat_returns, bench_returns]

        resp = tc.get("/strat-123?benchmarks=SPY&period=3m")
        assert resp.status_code == 200
        body = resp.json()
        comparison = body["data"]["attributes"]["comparisons"][0]
        metrics = comparison["metrics"]
        assert "alpha" in metrics
        assert "beta" in metrics
        assert "information_ratio" in metrics
        assert "tracking_error" in metrics
        assert "strategy_return" in metrics
        assert "benchmark_return" in metrics
        assert "excess_return" in metrics
        assert "correlation" in metrics
