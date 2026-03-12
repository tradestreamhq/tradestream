"""Tests for risk calculation utilities."""

import pytest

from services.risk_monitoring_api.risk_calculator import (
    compute_concentration_alerts,
    compute_correlation_matrix,
    compute_exposure_by_asset,
    compute_portfolio_beta,
    compute_returns,
    compute_var,
    _pearson,
)


class TestExposureByAsset:
    def test_single_position(self):
        positions = [{"symbol": "BTC/USD", "quantity": 0.5, "avg_entry_price": 60000}]
        result = compute_exposure_by_asset(positions)
        assert result == {"BTC/USD": 30000.0}

    def test_multiple_positions(self):
        positions = [
            {"symbol": "BTC/USD", "quantity": 1.0, "avg_entry_price": 60000},
            {"symbol": "ETH/USD", "quantity": 10.0, "avg_entry_price": 3000},
        ]
        result = compute_exposure_by_asset(positions)
        assert result["BTC/USD"] == 60000.0
        assert result["ETH/USD"] == 30000.0

    def test_negative_quantity_uses_absolute(self):
        positions = [{"symbol": "BTC/USD", "quantity": -0.5, "avg_entry_price": 60000}]
        result = compute_exposure_by_asset(positions)
        assert result["BTC/USD"] == 30000.0

    def test_empty_positions(self):
        result = compute_exposure_by_asset([])
        assert result == {}


class TestConcentrationAlerts:
    def test_no_alert_under_threshold(self):
        exposure = {"BTC/USD": 5000, "ETH/USD": 5000, "SOL/USD": 5000, "AVAX/USD": 5000, "LINK/USD": 5000}
        alerts = compute_concentration_alerts(exposure, threshold=0.20)
        assert alerts == []

    def test_alert_over_threshold(self):
        exposure = {"BTC/USD": 80000, "ETH/USD": 10000, "SOL/USD": 10000}
        alerts = compute_concentration_alerts(exposure, threshold=0.20)
        assert len(alerts) == 1
        assert alerts[0]["symbol"] == "BTC/USD"
        assert alerts[0]["weight"] == 0.8

    def test_multiple_alerts(self):
        exposure = {"BTC/USD": 50000, "ETH/USD": 50000}
        alerts = compute_concentration_alerts(exposure, threshold=0.20)
        assert len(alerts) == 2

    def test_empty_exposure(self):
        alerts = compute_concentration_alerts({})
        assert alerts == []

    def test_zero_total_exposure(self):
        exposure = {"BTC/USD": 0}
        alerts = compute_concentration_alerts(exposure)
        assert alerts == []

    def test_custom_threshold(self):
        exposure = {"BTC/USD": 3000, "ETH/USD": 7000}
        alerts = compute_concentration_alerts(exposure, threshold=0.50)
        assert len(alerts) == 1
        assert alerts[0]["symbol"] == "ETH/USD"


class TestComputeReturns:
    def test_basic_returns(self):
        pnl = [100.0, -50.0, 200.0]
        exposures = [1000.0, 1000.0, 1000.0]
        result = compute_returns(pnl, exposures)
        assert result == [0.1, -0.05, 0.2]

    def test_zero_exposure(self):
        pnl = [100.0]
        exposures = [0.0]
        result = compute_returns(pnl, exposures)
        assert result == [0.0]


class TestComputeVar:
    def test_basic_var(self):
        # 20 returns, 5th percentile at 95% confidence
        returns = [-0.05, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05,
                   0.01, 0.02, 0.03, 0.04, 0.05, 0.01, 0.02, 0.03, 0.04, 0.05]
        var = compute_var(returns, confidence=0.95, current_exposure=100000)
        assert var is not None
        assert var > 0

    def test_insufficient_data(self):
        var = compute_var([0.01], confidence=0.95)
        assert var is None

    def test_empty_returns(self):
        var = compute_var([], confidence=0.95)
        assert var is None

    def test_all_positive_returns(self):
        returns = [0.01, 0.02, 0.03, 0.04, 0.05] * 4
        var = compute_var(returns, confidence=0.95, current_exposure=10000)
        assert var is not None
        # Even with all positive returns, VaR is the worst-case percentile
        assert var >= 0


class TestPortfolioBeta:
    def test_perfect_correlation(self):
        # Identical series -> beta = 1.0
        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        beta = compute_portfolio_beta(returns, returns)
        assert beta == 1.0

    def test_insufficient_data(self):
        beta = compute_portfolio_beta([0.01], [0.01])
        assert beta is None

    def test_zero_variance_benchmark(self):
        strategy = [0.01, 0.02, 0.03]
        benchmark = [0.0, 0.0, 0.0]
        beta = compute_portfolio_beta(strategy, benchmark)
        assert beta is None

    def test_negative_beta(self):
        strategy = [0.01, -0.02, 0.03, -0.01, 0.02]
        benchmark = [-0.01, 0.02, -0.03, 0.01, -0.02]
        beta = compute_portfolio_beta(strategy, benchmark)
        assert beta is not None
        assert beta < 0


class TestCorrelationMatrix:
    def test_self_correlation(self):
        data = {"strat_a": [0.01, -0.02, 0.03, 0.01, -0.01]}
        matrix = compute_correlation_matrix(data)
        assert matrix["strat_a"]["strat_a"] == 1.0

    def test_two_strategies(self):
        data = {
            "strat_a": [0.01, -0.02, 0.03, 0.01, -0.01],
            "strat_b": [0.02, -0.01, 0.04, 0.02, -0.02],
        }
        matrix = compute_correlation_matrix(data)
        assert "strat_a" in matrix
        assert "strat_b" in matrix
        # Symmetric
        assert matrix["strat_a"]["strat_b"] == matrix["strat_b"]["strat_a"]

    def test_empty_strategies(self):
        matrix = compute_correlation_matrix({})
        assert matrix == {}

    def test_perfectly_correlated(self):
        data = {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [2.0, 4.0, 6.0, 8.0, 10.0],
        }
        matrix = compute_correlation_matrix(data)
        assert matrix["a"]["b"] == 1.0

    def test_inversely_correlated(self):
        data = {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [-1.0, -2.0, -3.0, -4.0, -5.0],
        }
        matrix = compute_correlation_matrix(data)
        assert matrix["a"]["b"] == -1.0


class TestPearson:
    def test_insufficient_data(self):
        assert _pearson([1.0], [2.0]) == 0.0

    def test_constant_series(self):
        assert _pearson([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0
