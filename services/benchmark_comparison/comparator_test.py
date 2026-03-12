"""Tests for benchmark comparison calculations."""

import numpy as np
import pytest

from services.benchmark_comparison.comparator import compute_metrics, compare
from services.benchmark_comparison.models import TimePeriod


class TestComputeMetrics:
    def test_identical_returns_give_zero_alpha_and_unit_beta(self):
        returns = np.array([0.01, -0.005, 0.02, 0.003, -0.01, 0.015, 0.008])
        metrics = compute_metrics(returns, returns)
        assert abs(metrics.alpha) < 1e-4
        assert abs(metrics.beta - 1.0) < 1e-4
        assert abs(metrics.tracking_error) < 1e-4
        assert abs(metrics.excess_return) < 1e-4
        assert abs(metrics.correlation - 1.0) < 1e-4

    def test_strategy_outperforms_benchmark(self):
        np.random.seed(42)
        bench = np.random.normal(0.0005, 0.01, 100)
        strat = bench + 0.001  # consistent outperformance
        metrics = compute_metrics(strat, bench)
        assert metrics.alpha > 0
        assert metrics.strategy_return > metrics.benchmark_return
        assert metrics.excess_return > 0

    def test_uncorrelated_returns_have_low_beta(self):
        np.random.seed(42)
        strat = np.random.normal(0.001, 0.02, 200)
        bench = np.random.normal(0.0005, 0.01, 200)
        metrics = compute_metrics(strat, bench)
        assert abs(metrics.beta) < 0.5
        assert abs(metrics.correlation) < 0.3

    def test_empty_returns(self):
        metrics = compute_metrics(np.array([]), np.array([]))
        assert metrics.alpha == 0.0
        assert metrics.beta == 0.0
        assert metrics.information_ratio == 0.0

    def test_single_return(self):
        metrics = compute_metrics(np.array([0.01]), np.array([0.005]))
        assert metrics.alpha == 0.0  # need >= 2 data points

    def test_different_lengths_uses_shorter(self):
        strat = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        bench = np.array([0.005, 0.01, 0.015])
        metrics = compute_metrics(strat, bench)
        # Should not error — uses first 3 elements
        assert metrics.strategy_return != 0.0

    def test_zero_benchmark_variance(self):
        strat = np.array([0.01, 0.02, -0.01, 0.005])
        bench = np.array([0.0, 0.0, 0.0, 0.0])
        metrics = compute_metrics(strat, bench)
        assert metrics.beta == 0.0

    def test_negative_alpha_for_underperformance(self):
        np.random.seed(99)
        bench = np.random.normal(0.001, 0.01, 100)
        strat = bench - 0.002  # consistent underperformance
        metrics = compute_metrics(strat, bench)
        assert metrics.alpha < 0
        assert metrics.excess_return < 0


class TestCompare:
    def test_compare_builds_full_result(self):
        strat = np.array([0.01, -0.005, 0.02, 0.003, -0.01])
        bench = np.array([0.005, -0.002, 0.015, 0.001, -0.005])
        result = compare("strat-123", "SPY", TimePeriod.ONE_MONTH, strat, bench)
        assert result.strategy_id == "strat-123"
        assert result.benchmark == "SPY"
        assert result.period == TimePeriod.ONE_MONTH
        assert result.metrics.strategy_return != 0.0
        assert result.computed_at is not None
