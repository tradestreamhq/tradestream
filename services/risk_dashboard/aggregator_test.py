"""Tests for the risk dashboard aggregator."""

import math

import pytest

from services.risk_dashboard.aggregator import (
    _pearson_correlation,
    aggregate_risk_dashboard,
    calculate_concentration,
    calculate_portfolio_beta,
    calculate_var,
    find_top_correlations,
)


class TestPearsonCorrelation:
    def test_perfect_positive(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        assert _pearson_correlation(x, y) == pytest.approx(1.0, abs=1e-6)

    def test_perfect_negative(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 8.0, 6.0, 4.0, 2.0]
        assert _pearson_correlation(x, y) == pytest.approx(-1.0, abs=1e-6)

    def test_zero_std(self):
        x = [1.0, 1.0, 1.0]
        y = [2.0, 4.0, 6.0]
        assert _pearson_correlation(x, y) == 0.0

    def test_too_few_points(self):
        assert _pearson_correlation([1.0], [2.0]) == 0.0

    def test_unequal_lengths(self):
        x = [1.0, 2.0, 3.0, 4.0]
        y = [1.0, 2.0, 3.0]
        # Should use min length
        result = _pearson_correlation(x, y)
        assert -1.0 <= result <= 1.0


class TestCalculateVar:
    def test_empty_positions(self):
        result = calculate_var([], [], 0.95, 10000.0)
        assert result.var_absolute == 0.0
        assert result.var_percent == 0.0
        assert result.confidence_level == 0.95

    def test_zero_equity(self):
        result = calculate_var([1000.0], [[0.01, -0.01]], 0.95, 0.0)
        assert result.var_absolute == 0.0

    def test_single_position(self):
        # Position worth 5000 in a 10000 portfolio, with known volatility
        returns = [0.02, -0.01, 0.03, -0.02, 0.01, -0.01, 0.02, -0.03, 0.01, 0.0]
        result = calculate_var([5000.0], [returns], 0.95, 10000.0)
        assert result.var_absolute > 0
        assert result.var_percent > 0
        assert result.confidence_level == 0.95

    def test_higher_confidence_means_higher_var(self):
        returns = [0.02, -0.01, 0.03, -0.02, 0.01, -0.01, 0.02, -0.03, 0.01, 0.0]
        var_95 = calculate_var([5000.0], [returns], 0.95, 10000.0)
        var_99 = calculate_var([5000.0], [returns], 0.99, 10000.0)
        assert var_99.var_absolute > var_95.var_absolute

    def test_multiple_positions_with_correlation(self):
        # Two correlated positions
        returns_a = [0.02, -0.01, 0.03, -0.02, 0.01, 0.02, -0.01, 0.0, 0.01, -0.01]
        returns_b = [0.01, -0.005, 0.02, -0.01, 0.005, 0.01, -0.005, 0.0, 0.005, -0.005]
        result = calculate_var(
            [3000.0, 2000.0], [returns_a, returns_b], 0.95, 10000.0
        )
        assert result.var_absolute > 0


class TestCalculatePortfolioBeta:
    def test_identical_returns(self):
        returns = [0.01, -0.02, 0.03, -0.01, 0.02]
        result = calculate_portfolio_beta(returns, returns)
        assert result.beta == pytest.approx(1.0, abs=1e-3)
        assert result.r_squared == pytest.approx(1.0, abs=1e-3)

    def test_double_returns(self):
        benchmark = [0.01, -0.02, 0.03, -0.01, 0.02]
        portfolio = [0.02, -0.04, 0.06, -0.02, 0.04]
        result = calculate_portfolio_beta(portfolio, benchmark)
        assert result.beta == pytest.approx(2.0, abs=1e-3)

    def test_insufficient_data(self):
        result = calculate_portfolio_beta([0.01], [0.02])
        assert result.beta == 1.0
        assert result.r_squared == 0.0

    def test_zero_variance_benchmark(self):
        portfolio = [0.01, -0.02, 0.03]
        benchmark = [0.0, 0.0, 0.0]
        result = calculate_portfolio_beta(portfolio, benchmark)
        assert result.beta == 0.0

    def test_benchmark_name(self):
        result = calculate_portfolio_beta(
            [0.01, -0.02, 0.03], [0.01, -0.02, 0.03], "ETH/USD"
        )
        assert result.benchmark == "ETH/USD"


class TestCalculateConcentration:
    def test_empty_positions(self):
        result = calculate_concentration([], 0.0)
        assert result.herfindahl_index == 0.0
        assert result.top_holding_pct == 0.0
        assert result.top_holding_symbol == ""

    def test_single_position(self):
        positions = [{"symbol": "BTC/USD", "quantity": 1.0, "avg_entry_price": 60000.0}]
        result = calculate_concentration(positions, 60000.0)
        assert result.herfindahl_index == pytest.approx(1.0, abs=1e-4)
        assert result.top_holding_pct == 100.0
        assert result.top_holding_symbol == "BTC/USD"

    def test_equal_positions(self):
        positions = [
            {"symbol": "BTC/USD", "quantity": 1.0, "avg_entry_price": 100.0},
            {"symbol": "ETH/USD", "quantity": 1.0, "avg_entry_price": 100.0},
            {"symbol": "SOL/USD", "quantity": 1.0, "avg_entry_price": 100.0},
            {"symbol": "ADA/USD", "quantity": 1.0, "avg_entry_price": 100.0},
        ]
        result = calculate_concentration(positions, 400.0)
        # HHI for 4 equal positions = 4 * (0.25)^2 = 0.25
        assert result.herfindahl_index == pytest.approx(0.25, abs=1e-4)
        assert result.top_holding_pct == 25.0

    def test_sector_classification(self):
        positions = [
            {"symbol": "BTC/USD", "quantity": 1.0, "avg_entry_price": 100.0},
            {"symbol": "ETH/USD", "quantity": 1.0, "avg_entry_price": 100.0},
            {"symbol": "UNI/USD", "quantity": 1.0, "avg_entry_price": 100.0},
        ]
        result = calculate_concentration(positions, 300.0)
        assert "L1" in result.sector_weights
        assert "DeFi" in result.sector_weights
        # BTC + ETH = L1 should be ~66.67%
        assert result.sector_weights["L1"] == pytest.approx(66.67, abs=0.01)


class TestFindTopCorrelations:
    def test_no_data(self):
        result = find_top_correlations([], [])
        assert result == []

    def test_insufficient_returns(self):
        result = find_top_correlations(
            ["BTC", "ETH"], [[0.01, 0.02], [0.01]]
        )
        assert result == []

    def test_finds_correlated_pairs(self):
        returns_a = [0.02, -0.01, 0.03, -0.02, 0.01, 0.02, -0.01]
        returns_b = [0.01, -0.005, 0.02, -0.01, 0.005, 0.01, -0.005]
        returns_c = [-0.02, 0.01, -0.03, 0.02, -0.01, -0.02, 0.01]

        result = find_top_correlations(
            ["A", "B", "C"], [returns_a, returns_b, returns_c]
        )
        assert len(result) == 3
        # A and B should be highly positively correlated
        # A and C should be highly negatively correlated
        ab_pair = next(
            p for p in result if {p.symbol_a, p.symbol_b} == {"A", "B"}
        )
        assert ab_pair.correlation > 0.9

    def test_top_n_limit(self):
        returns = [[0.01 * i for i in range(10)] for _ in range(5)]
        result = find_top_correlations(
            ["A", "B", "C", "D", "E"], returns, top_n=3
        )
        assert len(result) <= 3


class TestAggregateDashboard:
    def test_empty_portfolio(self):
        result = aggregate_risk_dashboard(
            positions=[],
            daily_returns_by_symbol={},
            benchmark_returns=[],
            total_equity=10000.0,
            active_strategy_count=5,
        )
        assert result.position_count == 0
        assert result.var_95.var_absolute == 0.0
        assert result.active_strategy_count == 5
        assert result.total_exposure == 0.0

    def test_full_dashboard(self):
        positions = [
            {"symbol": "BTC/USD", "quantity": 0.5, "avg_entry_price": 60000.0},
            {"symbol": "ETH/USD", "quantity": 10.0, "avg_entry_price": 3000.0},
        ]
        btc_returns = [0.02, -0.01, 0.03, -0.02, 0.01, 0.015, -0.005, 0.01, -0.01, 0.005]
        eth_returns = [0.03, -0.015, 0.04, -0.025, 0.015, 0.02, -0.01, 0.015, -0.015, 0.01]

        result = aggregate_risk_dashboard(
            positions=positions,
            daily_returns_by_symbol={"BTC/USD": btc_returns, "ETH/USD": eth_returns},
            benchmark_returns=btc_returns,
            total_equity=50000.0,
            active_strategy_count=3,
        )

        assert result.position_count == 2
        assert result.total_exposure == 60000.0  # 30000 + 30000
        assert result.active_strategy_count == 3
        assert result.var_95.var_absolute > 0
        assert result.var_99.var_absolute > result.var_95.var_absolute
        assert result.concentration.herfindahl_index > 0
        assert len(result.top_correlations) >= 1
        assert result.timestamp  # Not empty
