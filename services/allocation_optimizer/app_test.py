"""Tests for the Allocation Optimizer API."""

import pytest
from fastapi.testclient import TestClient

from services.allocation_optimizer.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


# --- Sample data ---

SAMPLE_STRATEGIES = [
    {"strategy_id": "momentum", "returns": [0.02, 0.01, -0.005, 0.03, 0.015, -0.01, 0.025, 0.005, 0.02, -0.008]},
    {"strategy_id": "mean_reversion", "returns": [-0.01, 0.02, 0.015, -0.005, 0.01, 0.025, -0.008, 0.03, -0.01, 0.02]},
    {"strategy_id": "trend_follow", "returns": [0.03, -0.01, 0.02, 0.01, -0.005, 0.015, 0.02, -0.008, 0.025, 0.01]},
]


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


class TestOptimize:
    def test_max_sharpe(self, client):
        resp = client.post("/optimize", json={"strategies": SAMPLE_STRATEGIES, "objective": "max_sharpe"})
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        weights = attrs["weights"]
        assert len(weights) == 3
        # Weights must sum to ~1
        assert abs(sum(weights.values()) - 1.0) < 1e-4
        # All weights non-negative (no short selling)
        assert all(w >= -1e-6 for w in weights.values())
        assert attrs["sharpe_ratio"] > 0

    def test_min_variance(self, client):
        resp = client.post("/optimize", json={"strategies": SAMPLE_STRATEGIES, "objective": "min_variance"})
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert abs(sum(attrs["weights"].values()) - 1.0) < 1e-4
        assert attrs["volatility"] > 0

    def test_target_return(self, client):
        resp = client.post("/optimize", json={
            "strategies": SAMPLE_STRATEGIES,
            "objective": "target_return",
            "target_return": 0.01,
        })
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert abs(sum(attrs["weights"].values()) - 1.0) < 1e-4
        # Return should be close to target
        assert abs(attrs["expected_return"] - 0.01) < 0.005

    def test_target_return_missing(self, client):
        resp = client.post("/optimize", json={
            "strategies": SAMPLE_STRATEGIES,
            "objective": "target_return",
        })
        assert resp.status_code == 422

    def test_min_weight_constraint(self, client):
        resp = client.post("/optimize", json={
            "strategies": SAMPLE_STRATEGIES,
            "objective": "max_sharpe",
            "min_weight": 0.1,
            "max_weight": 0.6,
        })
        assert resp.status_code == 200
        body = resp.json()
        weights = body["data"]["attributes"]["weights"]
        for w in weights.values():
            assert w >= 0.1 - 1e-4
            assert w <= 0.6 + 1e-4

    def test_infeasible_min_weight(self, client):
        resp = client.post("/optimize", json={
            "strategies": SAMPLE_STRATEGIES,
            "objective": "max_sharpe",
            "min_weight": 0.5,  # 0.5 * 3 = 1.5 > 1.0
        })
        assert resp.status_code == 422

    def test_too_few_returns(self, client):
        resp = client.post("/optimize", json={
            "strategies": [
                {"strategy_id": "a", "returns": [0.01]},
                {"strategy_id": "b", "returns": [0.02]},
            ],
            "objective": "max_sharpe",
        })
        assert resp.status_code == 422

    def test_too_few_strategies(self, client):
        resp = client.post("/optimize", json={
            "strategies": [{"strategy_id": "a", "returns": [0.01, 0.02]}],
            "objective": "max_sharpe",
        })
        assert resp.status_code == 422  # pydantic min_length=2


class TestEfficientFrontier:
    def test_frontier(self, client):
        resp = client.post("/efficient-frontier", json={"strategies": SAMPLE_STRATEGIES})
        assert resp.status_code == 200
        body = resp.json()
        attrs = body["data"]["attributes"]
        assert len(attrs["points"]) > 0
        assert "optimal" in attrs
        # Frontier should be sorted by increasing return
        returns = [p["expected_return"] for p in attrs["points"]]
        assert returns == sorted(returns)


class TestCovarianceModule:
    """Unit tests for covariance computation."""

    def test_covariance_matrix_shape(self):
        import numpy as np
        from services.allocation_optimizer.covariance import compute_covariance_matrix
        data = np.array([[0.01, 0.02], [0.03, -0.01], [-0.01, 0.015]])
        cov = compute_covariance_matrix(data)
        assert cov.shape == (2, 2)

    def test_shrinkage(self):
        import numpy as np
        from services.allocation_optimizer.covariance import shrink_covariance
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        shrunk = shrink_covariance(cov, shrinkage=0.5)
        # Diagonal should move toward average variance
        avg_var = (0.04 + 0.09) / 2
        assert abs(shrunk[0, 0] - (0.5 * 0.04 + 0.5 * avg_var)) < 1e-10
        # Off-diagonal should shrink toward zero
        assert abs(shrunk[0, 1]) < abs(cov[0, 1])


class TestOptimizerModule:
    """Unit tests for optimizer functions directly."""

    def test_two_strategy_optimization(self):
        import numpy as np
        from services.allocation_optimizer.optimizer import optimize_max_sharpe
        # One high-return strategy, one low-vol strategy
        returns = np.array([
            [0.05, 0.01],
            [0.03, 0.015],
            [0.04, 0.012],
            [0.06, 0.008],
            [0.02, 0.011],
        ])
        result = optimize_max_sharpe(["high_ret", "low_vol"], returns)
        assert abs(sum(result.weights.values()) - 1.0) < 1e-4
        assert result.sharpe_ratio > 0
