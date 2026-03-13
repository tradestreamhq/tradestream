"""Tests for the Grid Search Strategy Optimizer."""

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from services.backtesting.vectorbt_runner import BacktestMetrics
from services.strategy_optimizer.grid_search import (
    GridSearchConfig,
    GridSearchOptimizer,
    GridSearchResult,
    ParameterRange,
)


def _make_metrics(sharpe: float = 1.0, **kwargs) -> BacktestMetrics:
    """Create a BacktestMetrics with the given Sharpe ratio."""
    defaults = dict(
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
    defaults.update(kwargs)
    return BacktestMetrics(**defaults)


def _make_ohlcv(bars: int = 200) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=bars, freq="1min")
    close = 100 + np.cumsum(np.random.randn(bars) * 0.5)
    close = np.maximum(close, 10)
    return pd.DataFrame(
        {
            "open": close + np.random.randn(bars) * 0.1,
            "high": close + abs(np.random.randn(bars) * 0.5),
            "low": close - abs(np.random.randn(bars) * 0.5),
            "close": close,
            "volume": np.random.randint(100, 10000, bars).astype(float),
        },
        index=dates,
    )


class TestParameterRange:
    def test_values_integer_steps(self):
        pr = ParameterRange(name="period", min_value=10, max_value=30, step=10)
        assert pr.values() == [10, 20, 30]

    def test_values_single_value(self):
        pr = ParameterRange(name="x", min_value=5, max_value=5, step=1)
        assert pr.values() == [5]

    def test_values_fractional_step(self):
        pr = ParameterRange(name="mult", min_value=1.0, max_value=2.0, step=0.5)
        vals = pr.values()
        assert len(vals) == 3
        assert abs(vals[0] - 1.0) < 1e-9
        assert abs(vals[1] - 1.5) < 1e-9
        assert abs(vals[2] - 2.0) < 1e-9


class TestGridSearchConfig:
    def test_total_combinations(self):
        config = GridSearchConfig(
            strategy_name="SMA_RSI",
            parameter_ranges=[
                ParameterRange(name="a", min_value=10, max_value=50, step=10),  # 5 values
                ParameterRange(name="b", min_value=20, max_value=40, step=10),  # 3 values
            ],
        )
        assert config.total_combinations == 15

    def test_total_combinations_empty(self):
        config = GridSearchConfig(strategy_name="SMA_RSI", parameter_ranges=[])
        assert config.total_combinations == 1


class TestGridSearchOptimizer:
    def test_generate_parameter_grid(self):
        optimizer = GridSearchOptimizer()
        ranges = [
            ParameterRange(name="period", min_value=10, max_value=20, step=5),
            ParameterRange(name="threshold", min_value=30, max_value=40, step=10),
        ]
        grid = optimizer.generate_parameter_grid(ranges)
        # 3 * 2 = 6 combinations
        assert len(grid) == 6
        assert {"period": 10, "threshold": 30} in grid
        assert {"period": 20, "threshold": 40} in grid

    def test_generate_parameter_grid_empty(self):
        optimizer = GridSearchOptimizer()
        grid = optimizer.generate_parameter_grid([])
        assert grid == [{}]

    def test_generate_parameter_grid_converts_to_int(self):
        optimizer = GridSearchOptimizer()
        ranges = [ParameterRange(name="period", min_value=10, max_value=10, step=1)]
        grid = optimizer.generate_parameter_grid(ranges)
        assert grid == [{"period": 10}]
        assert isinstance(grid[0]["period"], int)

    def test_run_returns_ranked_results(self):
        runner = MagicMock()
        # Return different Sharpe ratios for different params
        runner.run_strategy.side_effect = [
            _make_metrics(sharpe=0.5),
            _make_metrics(sharpe=1.5),
            _make_metrics(sharpe=1.0),
        ]

        optimizer = GridSearchOptimizer(runner=runner)
        ohlcv = _make_ohlcv()
        config = GridSearchConfig(
            strategy_name="SMA_RSI",
            parameter_ranges=[
                ParameterRange(name="period", min_value=10, max_value=30, step=10),
            ],
            top_n=10,
        )

        results = optimizer.run(ohlcv, config)

        assert len(results) == 3
        # Best Sharpe first
        assert results[0].metrics["sharpe_ratio"] == 1.5
        assert results[0].rank == 1
        assert results[1].metrics["sharpe_ratio"] == 1.0
        assert results[1].rank == 2
        assert results[2].metrics["sharpe_ratio"] == 0.5
        assert results[2].rank == 3

    def test_run_top_n_limits_results(self):
        runner = MagicMock()
        runner.run_strategy.side_effect = [
            _make_metrics(sharpe=i) for i in range(5)
        ]

        optimizer = GridSearchOptimizer(runner=runner)
        config = GridSearchConfig(
            strategy_name="SMA_RSI",
            parameter_ranges=[
                ParameterRange(name="period", min_value=10, max_value=50, step=10),
            ],
            top_n=3,
        )

        results = optimizer.run(_make_ohlcv(), config)
        assert len(results) == 3
        assert results[0].rank == 1

    def test_run_handles_backtest_failures(self):
        runner = MagicMock()
        runner.run_strategy.side_effect = [
            _make_metrics(sharpe=1.0),
            ValueError("bad params"),
            _make_metrics(sharpe=2.0),
        ]

        optimizer = GridSearchOptimizer(runner=runner)
        config = GridSearchConfig(
            strategy_name="SMA_RSI",
            parameter_ranges=[
                ParameterRange(name="period", min_value=10, max_value=30, step=10),
            ],
        )

        results = optimizer.run(_make_ohlcv(), config)
        # One failed, so only 2 results
        assert len(results) == 2
        assert results[0].metrics["sharpe_ratio"] == 2.0

    def test_run_empty_grid(self):
        runner = MagicMock()
        runner.run_strategy.return_value = _make_metrics(sharpe=1.0)

        optimizer = GridSearchOptimizer(runner=runner)
        config = GridSearchConfig(
            strategy_name="SMA_RSI",
            parameter_ranges=[],
            top_n=5,
        )

        results = optimizer.run(_make_ohlcv(), config)
        assert len(results) == 1
        runner.run_strategy.assert_called_once()

    def test_result_contains_parameters(self):
        runner = MagicMock()
        runner.run_strategy.return_value = _make_metrics(sharpe=1.5)

        optimizer = GridSearchOptimizer(runner=runner)
        config = GridSearchConfig(
            strategy_name="SMA_RSI",
            parameter_ranges=[
                ParameterRange(name="movingAveragePeriod", min_value=20, max_value=20, step=1),
            ],
        )

        results = optimizer.run(_make_ohlcv(), config)
        assert results[0].parameters == {"movingAveragePeriod": 20}
