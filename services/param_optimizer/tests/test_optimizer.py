"""Tests for the StrategyOptimizer."""

import sys
import unittest
from unittest.mock import MagicMock
from dataclasses import dataclass


@dataclass
class BacktestMetrics:
    cumulative_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    number_of_trades: int = 0
    average_trade_duration: float = 0.0
    alpha: float = 0.0
    beta: float = 1.0
    strategy_score: float = 0.0


# Stub external deps
_backtesting_mod = MagicMock()
_backtesting_mod.BacktestMetrics = BacktestMetrics
_backtesting_mod.VectorBTRunner = MagicMock
sys.modules.setdefault("services", MagicMock())
sys.modules.setdefault("services.backtesting", MagicMock())
sys.modules["services.backtesting.vectorbt_runner"] = _backtesting_mod
# Stub pandas — only used for type hints in optimizer, we pass mocks
try:
    import pandas  # noqa: F401
except ImportError:
    sys.modules.setdefault("pandas", MagicMock())

from services.param_optimizer.models import ParameterRange
from services.param_optimizer.optimizer import StrategyOptimizer


class TestStrategyOptimizer(unittest.TestCase):
    def setUp(self):
        self.mock_runner = MagicMock()
        self.sample_ohlcv = MagicMock()  # DataFrame not needed — runner is mocked

    def test_basic_optimization(self):
        self.mock_runner.run_batch.return_value = [
            BacktestMetrics(sharpe_ratio=1.0, max_drawdown=0.1),
            BacktestMetrics(sharpe_ratio=2.0, max_drawdown=0.2),
            BacktestMetrics(sharpe_ratio=0.5, max_drawdown=0.05),
        ]

        optimizer = StrategyOptimizer(runner=self.mock_runner, top_n=3)
        result = optimizer.optimize(
            ohlcv=self.sample_ohlcv,
            strategy_name="SMA_RSI",
            param_ranges=[ParameterRange("movingAveragePeriod", [10, 20, 50])],
        )

        self.assertEqual(result.strategy_name, "SMA_RSI")
        self.assertEqual(result.total_combinations, 3)
        self.assertEqual(len(result.top_results), 3)
        # Ranked by sharpe_ratio descending
        self.assertEqual(result.top_results[0].metrics.sharpe_ratio, 2.0)
        self.assertEqual(result.top_results[1].metrics.sharpe_ratio, 1.0)
        self.assertEqual(result.top_results[2].metrics.sharpe_ratio, 0.5)

    def test_drawdown_constraint(self):
        self.mock_runner.run_batch.return_value = [
            BacktestMetrics(sharpe_ratio=3.0, max_drawdown=0.6),  # over limit
            BacktestMetrics(sharpe_ratio=1.5, max_drawdown=0.2),  # passes
            BacktestMetrics(sharpe_ratio=2.0, max_drawdown=0.4),  # passes
        ]

        optimizer = StrategyOptimizer(
            runner=self.mock_runner, max_drawdown_limit=0.5, top_n=10
        )
        result = optimizer.optimize(
            ohlcv=self.sample_ohlcv,
            strategy_name="SMA_RSI",
            param_ranges=[ParameterRange("movingAveragePeriod", [10, 20, 50])],
        )

        self.assertEqual(result.max_drawdown_limit, 0.5)
        self.assertEqual(len(result.top_results), 2)
        self.assertEqual(result.top_results[0].metrics.sharpe_ratio, 2.0)
        self.assertEqual(result.top_results[1].metrics.sharpe_ratio, 1.5)
        # All results still available
        self.assertEqual(len(result.all_results), 3)

    def test_top_n_limit(self):
        self.mock_runner.run_batch.return_value = [
            BacktestMetrics(sharpe_ratio=float(i)) for i in range(5)
        ]

        optimizer = StrategyOptimizer(runner=self.mock_runner, top_n=2)
        result = optimizer.optimize(
            ohlcv=self.sample_ohlcv,
            strategy_name="SMA_RSI",
            param_ranges=[ParameterRange("p", [1, 2, 3, 4, 5])],
        )

        self.assertEqual(len(result.top_results), 2)
        self.assertEqual(result.top_results[0].metrics.sharpe_ratio, 4.0)
        self.assertEqual(result.top_results[1].metrics.sharpe_ratio, 3.0)

    def test_parameters_passed_to_runner(self):
        self.mock_runner.run_batch.return_value = [BacktestMetrics() for _ in range(4)]

        optimizer = StrategyOptimizer(runner=self.mock_runner)
        optimizer.optimize(
            ohlcv=self.sample_ohlcv,
            strategy_name="DOUBLE_EMA_CROSSOVER",
            param_ranges=[
                ParameterRange("shortEmaPeriod", [5, 10]),
                ParameterRange("longEmaPeriod", [20, 50]),
            ],
        )

        self.mock_runner.run_batch.assert_called_once()
        call_args = self.mock_runner.run_batch.call_args
        param_sets = call_args[0][2]  # third positional arg
        self.assertEqual(len(param_sets), 4)
        self.assertIn({"shortEmaPeriod": 5, "longEmaPeriod": 20}, param_sets)
        self.assertIn({"shortEmaPeriod": 10, "longEmaPeriod": 50}, param_sets)

    def test_progress_callback(self):
        self.mock_runner.run_batch.return_value = [BacktestMetrics() for _ in range(3)]

        progress_calls = []
        optimizer = StrategyOptimizer(runner=self.mock_runner)
        optimizer.optimize(
            ohlcv=self.sample_ohlcv,
            strategy_name="SMA_RSI",
            param_ranges=[ParameterRange("p", [1, 2, 3])],
            progress_callback=lambda done, total: progress_calls.append((done, total)),
        )

        self.assertEqual(progress_calls, [(1, 3), (2, 3), (3, 3)])

    def test_custom_rank_key(self):
        self.mock_runner.run_batch.return_value = [
            BacktestMetrics(sharpe_ratio=2.0, strategy_score=0.3),
            BacktestMetrics(sharpe_ratio=1.0, strategy_score=0.9),
        ]

        optimizer = StrategyOptimizer(
            runner=self.mock_runner, rank_key="strategy_score"
        )
        result = optimizer.optimize(
            ohlcv=self.sample_ohlcv,
            strategy_name="SMA_RSI",
            param_ranges=[ParameterRange("p", [1, 2])],
        )

        self.assertEqual(result.top_results[0].metrics.strategy_score, 0.9)

    def test_all_filtered_by_drawdown(self):
        self.mock_runner.run_batch.return_value = [
            BacktestMetrics(max_drawdown=0.8),
            BacktestMetrics(max_drawdown=0.9),
        ]

        optimizer = StrategyOptimizer(runner=self.mock_runner, max_drawdown_limit=0.5)
        result = optimizer.optimize(
            ohlcv=self.sample_ohlcv,
            strategy_name="SMA_RSI",
            param_ranges=[ParameterRange("p", [1, 2])],
        )

        self.assertEqual(len(result.top_results), 0)
        self.assertEqual(result.total_combinations, 2)

    def test_result_parameters_preserved(self):
        self.mock_runner.run_batch.return_value = [
            BacktestMetrics(sharpe_ratio=2.0),
            BacktestMetrics(sharpe_ratio=1.0),
        ]

        optimizer = StrategyOptimizer(runner=self.mock_runner)
        result = optimizer.optimize(
            ohlcv=self.sample_ohlcv,
            strategy_name="SMA_RSI",
            param_ranges=[ParameterRange("lookback", [10, 20])],
        )

        # Best result (sharpe=2.0) corresponds to first combo (lookback=10)
        self.assertEqual(result.top_results[0].parameters, {"lookback": 10})
        self.assertEqual(result.top_results[1].parameters, {"lookback": 20})


if __name__ == "__main__":
    unittest.main()
