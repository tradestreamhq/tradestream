"""Tests for the Optimization API endpoints."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.optimization_api.app import create_app


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


@pytest.fixture
def client_with_backtest():
    """Client with a mock backtest function for end-to-end testing."""
    pool, conn = _make_pool()

    async def mock_backtest(strategy_name, parameters, instrument, start_date, end_date):
        # Return metrics that vary based on parameters for realistic testing
        period = parameters.get("period", 14)
        return {
            "sharpe_ratio": 1.0 + (period - 14) * 0.1,
            "cumulative_return": 0.1 + (period - 14) * 0.01,
            "max_drawdown": 0.1 + (period - 14) * 0.005,
            "number_of_trades": 50 - period,
            "win_rate": 0.55,
            "profit_factor": 1.3,
            "sortino_ratio": 1.2,
            "strategy_score": 0.6,
        }

    app = create_app(pool, backtest_fn=mock_backtest)
    app.dependency_overrides = {}
    return TestClient(app, raise_server_exceptions=False), conn


class TestHealthEndpoints:
    def test_health(self, client):
        tc, conn = client
        conn.fetchval.return_value = 1
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "optimization-api"


class TestSubmitOptimization:
    def test_submit_valid_job(self, client_with_backtest):
        tc, conn = client_with_backtest
        resp = tc.post(
            "/run",
            json={
                "strategy_id": "SMA_RSI",
                "parameter_space": {
                    "numeric": [
                        {"name": "period", "min": 10, "max": 20, "step": 5}
                    ],
                    "categorical": [],
                },
                "objective": "sharpe",
                "date_range": {"start": "2025-01-01", "end": "2025-06-30"},
                "search_method": "grid",
                "instrument": "BTC/USD",
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["attributes"]["status"] == "PENDING"
        assert "job_id" in body["data"]["attributes"]

    def test_submit_invalid_objective(self, client):
        tc, conn = client
        resp = tc.post(
            "/run",
            json={
                "strategy_id": "SMA_RSI",
                "parameter_space": {
                    "numeric": [{"name": "p", "min": 1, "max": 10, "step": 1}],
                },
                "objective": "invalid",
                "date_range": {"start": "2025-01-01", "end": "2025-06-30"},
            },
        )
        assert resp.status_code == 422
        assert "invalid" in resp.json()["error"]["message"].lower()

    def test_submit_invalid_search_method(self, client):
        tc, conn = client
        resp = tc.post(
            "/run",
            json={
                "strategy_id": "SMA_RSI",
                "parameter_space": {
                    "numeric": [{"name": "p", "min": 1, "max": 10, "step": 1}],
                },
                "objective": "sharpe",
                "search_method": "bayesian",
                "date_range": {"start": "2025-01-01", "end": "2025-06-30"},
            },
        )
        assert resp.status_code == 422

    def test_submit_empty_param_space(self, client):
        tc, conn = client
        resp = tc.post(
            "/run",
            json={
                "strategy_id": "SMA_RSI",
                "parameter_space": {"numeric": [], "categorical": []},
                "objective": "sharpe",
                "date_range": {"start": "2025-01-01", "end": "2025-06-30"},
            },
        )
        assert resp.status_code == 422

    def test_submit_min_greater_than_max(self, client):
        tc, conn = client
        resp = tc.post(
            "/run",
            json={
                "strategy_id": "SMA_RSI",
                "parameter_space": {
                    "numeric": [{"name": "p", "min": 20, "max": 10, "step": 1}],
                },
                "objective": "sharpe",
                "date_range": {"start": "2025-01-01", "end": "2025-06-30"},
            },
        )
        assert resp.status_code == 422

    def test_submit_zero_step(self, client):
        tc, conn = client
        resp = tc.post(
            "/run",
            json={
                "strategy_id": "SMA_RSI",
                "parameter_space": {
                    "numeric": [{"name": "p", "min": 1, "max": 10, "step": 0}],
                },
                "objective": "sharpe",
                "date_range": {"start": "2025-01-01", "end": "2025-06-30"},
            },
        )
        assert resp.status_code == 422

    def test_submit_random_search(self, client_with_backtest):
        tc, conn = client_with_backtest
        resp = tc.post(
            "/run",
            json={
                "strategy_id": "MACD_CROSSOVER",
                "parameter_space": {
                    "numeric": [
                        {"name": "fast", "min": 5, "max": 20, "step": 1},
                        {"name": "slow", "min": 20, "max": 50, "step": 1},
                    ],
                    "categorical": [
                        {"name": "type", "options": ["SMA", "EMA"]},
                    ],
                },
                "objective": "return",
                "search_method": "random",
                "max_combinations": 50,
                "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
            },
        )
        assert resp.status_code == 202

    def test_submit_with_categorical_params(self, client_with_backtest):
        tc, conn = client_with_backtest
        resp = tc.post(
            "/run",
            json={
                "strategy_id": "SMA_RSI",
                "parameter_space": {
                    "categorical": [
                        {"name": "indicator", "options": ["SMA", "EMA", "WMA"]},
                    ],
                },
                "objective": "drawdown",
                "date_range": {"start": "2025-01-01", "end": "2025-06-30"},
            },
        )
        assert resp.status_code == 202


class TestGetOptimizationStatus:
    def test_get_not_found(self, client):
        tc, conn = client
        conn.fetchrow.return_value = None
        job_id = str(uuid.uuid4())
        resp = tc.get(f"/{job_id}")
        assert resp.status_code == 404

    def test_get_from_database(self, client):
        tc, conn = client
        job_id = uuid.uuid4()
        conn.fetchrow.return_value = FakeRecord(
            id=job_id,
            strategy_id="SMA_RSI",
            status="COMPLETED",
            search_method="grid",
            objective="sharpe",
            total_combinations=10,
            completed_combinations=10,
            best_parameters={"period": 14},
            best_objective_value=1.8,
            ranked_results=[
                {
                    "parameters": {"period": 14},
                    "objective_value": 1.8,
                    "sharpe_ratio": 1.8,
                    "cumulative_return": 0.25,
                    "max_drawdown": 0.08,
                    "number_of_trades": 42,
                    "win_rate": 0.6,
                    "profit_factor": 1.5,
                    "sortino_ratio": 2.0,
                    "strategy_score": 0.7,
                }
            ],
            error=None,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        )

        resp = tc.get(f"/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert attrs["status"] == "COMPLETED"
        assert attrs["best_objective_value"] == 1.8
        assert attrs["best_parameters"] == {"period": 14}


class TestListOptimizationJobs:
    def test_list_empty(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 0

    def test_list_with_results(self, client):
        tc, conn = client
        job_id = uuid.uuid4()
        conn.fetch.return_value = [
            FakeRecord(
                id=job_id,
                strategy_id="SMA_RSI",
                status="COMPLETED",
                search_method="grid",
                objective="sharpe",
                total_combinations=10,
                completed_combinations=10,
                best_parameters={"period": 14},
                best_objective_value=1.8,
                error=None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                completed_at=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
            )
        ]
        conn.fetchval.return_value = 1

        resp = tc.get("")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["total"] == 1
        assert len(body["data"]) == 1

    def test_list_filter_by_strategy(self, client):
        tc, conn = client
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        resp = tc.get("?strategy_id=SMA_RSI")
        assert resp.status_code == 200
