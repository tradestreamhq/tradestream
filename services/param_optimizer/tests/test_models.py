"""Tests for param_optimizer models."""

import unittest

# conftest stubs are loaded by the test runner script
from services.param_optimizer.models import (
    OptimizationResult,
    ParameterRange,
    ParameterSetResult,
)
from services.backtesting.vectorbt_runner import BacktestMetrics


class TestParameterRange(unittest.TestCase):
    def test_basic_creation(self):
        pr = ParameterRange(name="lookback", values=[10, 20, 50])
        self.assertEqual(pr.name, "lookback")
        self.assertEqual(pr.values, [10, 20, 50])

    def test_float_values(self):
        pr = ParameterRange(name="threshold", values=[0.5, 1.0, 1.5])
        self.assertEqual(pr.values, [0.5, 1.0, 1.5])

    def test_single_value(self):
        pr = ParameterRange(name="fixed", values=[42])
        self.assertEqual(len(pr.values), 1)

    def test_empty_values_raises(self):
        with self.assertRaises(ValueError):
            ParameterRange(name="bad", values=[])


class TestParameterSetResult(unittest.TestCase):
    def test_creation(self):
        metrics = BacktestMetrics(sharpe_ratio=1.5, max_drawdown=0.1)
        result = ParameterSetResult(parameters={"lookback": 20}, metrics=metrics)
        self.assertEqual(result.parameters, {"lookback": 20})
        self.assertEqual(result.metrics.sharpe_ratio, 1.5)


class TestOptimizationResult(unittest.TestCase):
    def test_creation(self):
        result = OptimizationResult(
            strategy_name="SMA_RSI",
            total_combinations=100,
            top_results=[],
            max_drawdown_limit=0.3,
        )
        self.assertEqual(result.strategy_name, "SMA_RSI")
        self.assertEqual(result.total_combinations, 100)
        self.assertEqual(result.max_drawdown_limit, 0.3)

    def test_defaults(self):
        result = OptimizationResult(
            strategy_name="TEST",
            total_combinations=1,
            top_results=[],
        )
        self.assertEqual(result.all_results, [])
        self.assertEqual(result.max_drawdown_limit, 1.0)


if __name__ == "__main__":
    unittest.main()
