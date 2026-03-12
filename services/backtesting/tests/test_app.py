"""
Tests for the backtesting REST API endpoints.
"""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.backtesting.app import create_app


@pytest.fixture
def mock_db_pool():
    """Create a mock asyncpg connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    conn.fetchval.return_value = 1
    conn.execute.return_value = None
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    return pool


@pytest.fixture
def client(mock_db_pool):
    """Create a test client with mocked auth and DB."""
    with patch("services.backtesting.app.fastapi_auth_middleware"):
        app = create_app(mock_db_pool)
        return TestClient(app)


@pytest.fixture
def sample_candles():
    """Generate sample OHLCV candle data for API requests."""
    np.random.seed(42)
    n = 200
    returns = np.random.randn(n) * 0.005 + 0.0002
    close = 100 * np.exp(np.cumsum(returns))

    candles = []
    for i in range(n):
        c = close[i]
        candles.append(
            {
                "open": float(c * 0.999),
                "high": float(c * 1.005),
                "low": float(c * 0.995),
                "close": float(c),
                "volume": 1000.0,
            }
        )
    return candles


class TestHealthEndpoints:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_ready(self, client):
        response = client.get("/ready")
        assert response.status_code == 200


class TestRunBacktest:
    def test_run_backtest_success(self, client, sample_candles):
        body = {
            "strategy_name": "DOUBLE_EMA_CROSSOVER",
            "strategy_params": {
                "shortEmaPeriod": 10,
                "longEmaPeriod": 20,
            },
            "initial_capital": 10000.0,
            "candles": sample_candles,
        }
        response = client.post("/backtests", json=body)
        assert response.status_code == 201

        data = response.json()
        assert data["data"]["type"] == "backtest_result"
        attrs = data["data"]["attributes"]
        assert attrs["strategy_name"] == "DOUBLE_EMA_CROSSOVER"
        assert attrs["initial_capital"] == 10000.0
        assert "total_return" in attrs
        assert "sharpe_ratio" in attrs
        assert "max_drawdown" in attrs
        assert "number_of_trades" in attrs
        assert "avg_holding_period_bars" in attrs
        assert "trades" in attrs

    def test_run_backtest_with_custom_commission(
        self, client, sample_candles
    ):
        body = {
            "strategy_name": "DOUBLE_EMA_CROSSOVER",
            "strategy_params": {
                "shortEmaPeriod": 10,
                "longEmaPeriod": 20,
            },
            "initial_capital": 50000.0,
            "commission": {
                "flat_fee": 5.0,
                "percentage": 0.002,
                "min_commission": 1.0,
            },
            "candles": sample_candles,
        }
        response = client.post("/backtests", json=body)
        assert response.status_code == 201

        attrs = response.json()["data"]["attributes"]
        assert attrs["total_commission"] > 0

    def test_run_backtest_with_date_range(self, client, sample_candles):
        body = {
            "strategy_name": "DOUBLE_EMA_CROSSOVER",
            "strategy_params": {
                "shortEmaPeriod": 10,
                "longEmaPeriod": 20,
            },
            "candles": sample_candles,
            "start_date": "2020-01-01 00:30:00",
            "end_date": "2020-01-01 02:00:00",
        }
        response = client.post("/backtests", json=body)
        assert response.status_code == 201

    def test_run_backtest_too_few_candles(self, client):
        body = {
            "strategy_name": "DOUBLE_EMA_CROSSOVER",
            "strategy_params": {},
            "candles": [
                {
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100,
                    "volume": 1000,
                }
            ],
        }
        response = client.post("/backtests", json=body)
        assert response.status_code == 422
        assert "error" in response.json()

    def test_run_backtest_missing_columns(self, client):
        body = {
            "strategy_name": "DOUBLE_EMA_CROSSOVER",
            "strategy_params": {},
            "candles": [{"close": 100}, {"close": 101}],
        }
        response = client.post("/backtests", json=body)
        assert response.status_code == 422

    def test_run_backtest_unknown_strategy(self, client, sample_candles):
        body = {
            "strategy_name": "NONEXISTENT_STRATEGY",
            "strategy_params": {},
            "candles": sample_candles,
        }
        response = client.post("/backtests", json=body)
        assert response.status_code == 422

    def test_run_backtest_position_size(self, client, sample_candles):
        body = {
            "strategy_name": "DOUBLE_EMA_CROSSOVER",
            "strategy_params": {
                "shortEmaPeriod": 10,
                "longEmaPeriod": 20,
            },
            "position_size_pct": 0.5,
            "candles": sample_candles,
        }
        response = client.post("/backtests", json=body)
        assert response.status_code == 201


class TestListBacktests:
    def test_list_empty(self, client, mock_db_pool):
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        response = client.get("/backtests")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["total"] == 0

    def test_list_with_strategy_filter(self, client, mock_db_pool):
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetch.return_value = []
        conn.fetchval.return_value = 0

        response = client.get("/backtests?strategy_name=SMA_RSI")
        assert response.status_code == 200


class TestGetBacktest:
    def test_get_not_found(self, client, mock_db_pool):
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow.return_value = None

        response = client.get("/backtests/nonexistent-id")
        assert response.status_code == 404


class TestDeleteBacktest:
    def test_delete_not_found(self, client, mock_db_pool):
        conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        conn.fetchrow.return_value = None

        response = client.delete("/backtests/nonexistent-id")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
