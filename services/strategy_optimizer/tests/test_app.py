"""Tests for the Strategy Optimizer REST API."""

import time
import uuid
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.backtesting.vectorbt_runner import BacktestMetrics
from services.strategy_optimizer.app import OptimizationStatus, create_app
from services.strategy_optimizer.grid_search import GridSearchResult


def _make_metrics(sharpe: float = 1.0) -> BacktestMetrics:
    return BacktestMetrics(
        cumulative_return=0.1,
        annualized_return=0.05,
        sharpe_ratio=sharpe,
        sortino_ratio=0.8,
        max_drawdown=0.1,
        volatility=0.02,
        win_rate=0.6,
        profit_factor=1.5,
        number_of_trades=10,
        average_trade_duration=5.0,
        alpha=0.0,
        beta=1.0,
        strategy_score=0.5,
    )


def _valid_request():
    return {
        "strategy_name": "SMA_RSI",
        "parameter_ranges": [
            {
                "name": "movingAveragePeriod",
                "min_value": 10,
                "max_value": 20,
                "step": 10,
            },
            {"name": "rsiPeriod", "min_value": 10, "max_value": 14, "step": 4},
        ],
        "instrument": "BTC/USD",
        "start_date": "2025-01-01",
        "end_date": "2025-06-01",
        "top_n": 5,
    }


@pytest.fixture
def client():
    """Create test client with mocked runner."""
    runner = MagicMock()
    runner.run_strategy.return_value = _make_metrics(sharpe=1.5)
    app = create_app(runner=runner)
    return TestClient(app, raise_server_exceptions=False), runner


class TestHealthEndpoints:
    def test_health(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "strategy-optimizer"


class TestRunEndpoint:
    def test_submit_optimization(self, client):
        tc, _ = client
        resp = tc.post("/run", json=_valid_request())
        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["type"] == "optimization_job"
        assert body["data"]["attributes"]["status"] == "PENDING"
        assert body["data"]["attributes"]["total_combinations"] == 4
        assert "job_id" in body["data"]["attributes"]

    def test_submit_validation_error_min_gt_max(self, client):
        tc, _ = client
        req = _valid_request()
        req["parameter_ranges"][0]["min_value"] = 50
        req["parameter_ranges"][0]["max_value"] = 10
        resp = tc.post("/run", json=req)
        assert resp.status_code == 422

    def test_submit_validation_error_step_zero(self, client):
        tc, _ = client
        req = _valid_request()
        req["parameter_ranges"][0]["step"] = 0
        resp = tc.post("/run", json=req)
        assert resp.status_code == 422

    def test_submit_missing_fields(self, client):
        tc, _ = client
        resp = tc.post("/run", json={"strategy_name": "SMA_RSI"})
        assert resp.status_code == 422


class TestStatusEndpoint:
    def test_status_not_found(self, client):
        tc, _ = client
        resp = tc.get(f"/{uuid.uuid4()}/status")
        assert resp.status_code == 404

    def test_status_after_submit(self, client):
        tc, _ = client
        resp = tc.post("/run", json=_valid_request())
        job_id = resp.json()["data"]["attributes"]["job_id"]

        resp = tc.get(f"/{job_id}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["job_id"] == job_id
        assert body["data"]["attributes"]["status"] in [
            "PENDING",
            "RUNNING",
            "COMPLETED",
        ]

    def test_status_completed(self, client):
        tc, runner = client
        runner.run_strategy.return_value = _make_metrics(sharpe=1.5)

        resp = tc.post("/run", json=_valid_request())
        job_id = resp.json()["data"]["attributes"]["job_id"]

        # Wait for background task
        for _ in range(50):
            resp = tc.get(f"/{job_id}/status")
            if resp.json()["data"]["attributes"]["status"] == "COMPLETED":
                break
            time.sleep(0.1)

        body = resp.json()
        assert body["data"]["attributes"]["status"] == "COMPLETED"
        assert "completed_at" in body["data"]["attributes"]
        assert body["data"]["attributes"]["result_count"] > 0


class TestResultsEndpoint:
    def test_results_not_found(self, client):
        tc, _ = client
        resp = tc.get(f"/{uuid.uuid4()}/results")
        assert resp.status_code == 404

    def test_results_completed(self, client):
        tc, runner = client
        runner.run_strategy.return_value = _make_metrics(sharpe=2.0)

        resp = tc.post("/run", json=_valid_request())
        job_id = resp.json()["data"]["attributes"]["job_id"]

        # Wait for completion
        for _ in range(50):
            resp = tc.get(f"/{job_id}/status")
            if resp.json()["data"]["attributes"]["status"] == "COMPLETED":
                break
            time.sleep(0.1)

        resp = tc.get(f"/{job_id}/results")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) > 0
        assert body["data"][0]["attributes"]["rank"] == 1
        assert "parameters" in body["data"][0]["attributes"]
        assert "metrics" in body["data"][0]["attributes"]
        assert body["data"][0]["attributes"]["metrics"]["sharpe_ratio"] == 2.0

    def test_results_pending(self, client):
        tc, runner = client
        # Make runner block so job stays pending/running
        import threading

        block = threading.Event()
        original = runner.run_strategy.return_value

        def slow_run(*args, **kwargs):
            block.wait(timeout=5)
            return original

        runner.run_strategy.side_effect = slow_run

        resp = tc.post("/run", json=_valid_request())
        job_id = resp.json()["data"]["attributes"]["job_id"]

        # Check results while still running
        resp = tc.get(f"/{job_id}/results")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["status"] in ["PENDING", "RUNNING"]

        block.set()  # Unblock

    def test_results_respects_top_n_query(self, client):
        tc, runner = client
        runner.run_strategy.return_value = _make_metrics(sharpe=1.0)

        resp = tc.post("/run", json=_valid_request())
        job_id = resp.json()["data"]["attributes"]["job_id"]

        for _ in range(50):
            resp = tc.get(f"/{job_id}/status")
            if resp.json()["data"]["attributes"]["status"] == "COMPLETED":
                break
            time.sleep(0.1)

        resp = tc.get(f"/{job_id}/results?top_n=2")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 2


class TestOptimizationFailure:
    def test_failed_optimization(self, client):
        tc, runner = client
        runner.run_strategy.side_effect = RuntimeError("Backtest engine error")

        resp = tc.post("/run", json=_valid_request())
        job_id = resp.json()["data"]["attributes"]["job_id"]

        # Wait for failure
        for _ in range(50):
            resp = tc.get(f"/{job_id}/status")
            status = resp.json()["data"]["attributes"]["status"]
            if status in ["COMPLETED", "FAILED"]:
                break
            time.sleep(0.1)

        # All backtests fail, but the job still completes (with empty results)
        # since individual failures are caught
        body = resp.json()
        assert body["data"]["attributes"]["status"] in ["COMPLETED", "FAILED"]
