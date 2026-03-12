"""
Tests for Strategy Parameter Optimization Service.
"""

import numpy as np
import pandas as pd
import pytest

from services.backtesting.parameter_optimizer import (
    OptimizationResult,
    ParameterOptimizer,
    ParameterSpace,
    WalkForwardWindow,
)
from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data for testing."""
    np.random.seed(42)
    n = 1000

    returns = np.random.randn(n) * 0.02
    close = 100 * np.exp(np.cumsum(returns))

    high = close * (1 + np.abs(np.random.randn(n) * 0.01))
    low = close * (1 - np.abs(np.random.randn(n) * 0.01))
    open_price = np.roll(close, 1)
    open_price[0] = close[0]

    high = np.maximum(high, np.maximum(open_price, close))
    low = np.minimum(low, np.minimum(open_price, close))

    volume = np.random.randint(1000, 10000, n).astype(float)

    df = pd.DataFrame(
        {"open": open_price, "high": high, "low": low, "close": close, "volume": volume}
    )
    df.index = pd.date_range(start="2020-01-01", periods=n, freq="1min")
    return df


@pytest.fixture
def optimizer():
    return ParameterOptimizer()


@pytest.fixture
def sma_rsi_spaces():
    """Parameter spaces for SMA_RSI strategy."""
    return [
        ParameterSpace(name="movingAveragePeriod", param_type="INTEGER", min_value=10, max_value=30, step=10),
        ParameterSpace(name="rsiPeriod", param_type="INTEGER", min_value=7, max_value=21, step=7),
        ParameterSpace(name="overboughtThreshold", param_type="DOUBLE", min_value=70.0, max_value=80.0, step=10.0),
        ParameterSpace(name="oversoldThreshold", param_type="DOUBLE", min_value=20.0, max_value=30.0, step=10.0),
    ]


class TestParameterSpace:
    """Tests for ParameterSpace."""

    def test_integer_grid_values(self):
        space = ParameterSpace(name="period", param_type="INTEGER", min_value=10, max_value=14, step=2)
        assert space.grid_values == [10, 12, 14]

    def test_double_grid_values(self):
        space = ParameterSpace(name="threshold", param_type="DOUBLE", min_value=0.0, max_value=1.0, step=0.5)
        assert space.grid_values == [0.0, 0.5, 1.0]

    def test_default_integer_step(self):
        space = ParameterSpace(name="period", param_type="INTEGER", min_value=10, max_value=12)
        assert space.grid_values == [10, 11, 12]

    def test_default_double_step(self):
        space = ParameterSpace(name="threshold", param_type="DOUBLE", min_value=0.0, max_value=1.0)
        # Default step = (1.0 - 0.0) / 10 = 0.1
        assert len(space.grid_values) == 11

    def test_grid_size(self):
        space = ParameterSpace(name="period", param_type="INTEGER", min_value=10, max_value=14, step=2)
        assert space.grid_size == 3

    def test_sample_integer(self):
        space = ParameterSpace(name="period", param_type="INTEGER", min_value=10, max_value=20)
        for _ in range(50):
            val = space.sample()
            assert isinstance(val, int)
            assert 10 <= val <= 20

    def test_sample_double(self):
        space = ParameterSpace(name="threshold", param_type="DOUBLE", min_value=0.0, max_value=1.0)
        for _ in range(50):
            val = space.sample()
            assert isinstance(val, float)
            assert 0.0 <= val <= 1.0


class TestParameterOptimizerHelpers:
    """Tests for optimizer helper methods."""

    def test_total_grid_size(self):
        spaces = [
            ParameterSpace(name="a", param_type="INTEGER", min_value=1, max_value=3, step=1),
            ParameterSpace(name="b", param_type="INTEGER", min_value=1, max_value=2, step=1),
        ]
        assert ParameterOptimizer.total_grid_size(spaces) == 6  # 3 * 2

    def test_total_grid_size_empty(self):
        assert ParameterOptimizer.total_grid_size([]) == 0

    def test_spaces_from_yaml(self):
        spec = {
            "parameters": [
                {"name": "period", "type": "INTEGER", "min": 10, "max": 50, "defaultValue": 20},
                {"name": "threshold", "type": "DOUBLE", "min": 0.5, "max": 1.0, "defaultValue": 0.7},
                {"name": "noRange", "type": "INTEGER", "defaultValue": 5},  # No min/max
            ]
        }
        spaces = ParameterOptimizer.spaces_from_yaml(spec)
        assert len(spaces) == 2
        assert spaces[0].name == "period"
        assert spaces[0].param_type == "INTEGER"
        assert spaces[0].min_value == 10
        assert spaces[0].max_value == 50
        assert spaces[1].name == "threshold"

    def test_create_windows(self):
        windows = ParameterOptimizer._create_windows(
            total_bars=1000, train_bars=400, test_bars=200, step_bars=200
        )
        assert len(windows) == 3
        assert windows[0].train_start == 0
        assert windows[0].train_end == 400
        assert windows[0].test_start == 400
        assert windows[0].test_end == 600
        assert windows[1].train_start == 200
        assert windows[2].train_start == 400

    def test_create_windows_insufficient_data(self):
        windows = ParameterOptimizer._create_windows(
            total_bars=100, train_bars=400, test_bars=200, step_bars=200
        )
        assert len(windows) == 0

    def test_unknown_metric_raises(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        with pytest.raises(ValueError, match="Unknown metric"):
            optimizer.grid_search(
                sample_ohlcv, "SMA_RSI", sma_rsi_spaces, metric="invalid_metric"
            )

    def test_unknown_metric_raises_random(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        with pytest.raises(ValueError, match="Unknown metric"):
            optimizer.random_search(
                sample_ohlcv, "SMA_RSI", sma_rsi_spaces, metric="invalid_metric"
            )


class TestGridSearch:
    """Tests for grid search optimization."""

    def test_grid_search_returns_results(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        results = optimizer.grid_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces, metric="sharpe_ratio", top_n=5
        )
        assert len(results) > 0
        assert len(results) <= 5

    def test_grid_search_results_are_ranked(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        results = optimizer.grid_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces, metric="sharpe_ratio", top_n=5
        )
        for i, r in enumerate(results):
            assert r.rank == i + 1

    def test_grid_search_results_sorted_descending(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        results = optimizer.grid_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces, metric="sharpe_ratio", top_n=10
        )
        sharpes = [r.metrics.sharpe_ratio for r in results]
        assert sharpes == sorted(sharpes, reverse=True)

    def test_grid_search_all_combinations_evaluated(self, sample_ohlcv, optimizer):
        """With small spaces, grid search should evaluate all combos."""
        spaces = [
            ParameterSpace(name="movingAveragePeriod", param_type="INTEGER", min_value=15, max_value=25, step=10),
            ParameterSpace(name="rsiPeriod", param_type="INTEGER", min_value=14, max_value=14, step=1),
            ParameterSpace(name="overboughtThreshold", param_type="DOUBLE", min_value=70.0, max_value=70.0, step=1.0),
            ParameterSpace(name="oversoldThreshold", param_type="DOUBLE", min_value=30.0, max_value=30.0, step=1.0),
        ]
        total = ParameterOptimizer.total_grid_size(spaces)
        results = optimizer.grid_search(
            sample_ohlcv, "SMA_RSI", spaces, top_n=100
        )
        assert len(results) == total

    def test_grid_search_with_different_metrics(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        for metric in ["sharpe_ratio", "cumulative_return", "win_rate"]:
            results = optimizer.grid_search(
                sample_ohlcv, "SMA_RSI", sma_rsi_spaces, metric=metric, top_n=3
            )
            assert len(results) > 0

    def test_grid_search_result_has_parameters(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        results = optimizer.grid_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces, top_n=1
        )
        assert "movingAveragePeriod" in results[0].parameters
        assert "rsiPeriod" in results[0].parameters

    def test_grid_search_result_has_metrics(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        results = optimizer.grid_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces, top_n=1
        )
        m = results[0].metrics
        assert isinstance(m, BacktestMetrics)
        assert isinstance(m.sharpe_ratio, float)
        assert isinstance(m.number_of_trades, int)


class TestRandomSearch:
    """Tests for random search optimization."""

    def test_random_search_returns_results(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        results = optimizer.random_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces,
            n_iterations=10, top_n=5,
        )
        assert len(results) > 0
        assert len(results) <= 5

    def test_random_search_reproducible_with_seed(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        results1 = optimizer.random_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces,
            n_iterations=5, seed=42, top_n=3,
        )
        results2 = optimizer.random_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces,
            n_iterations=5, seed=42, top_n=3,
        )
        for r1, r2 in zip(results1, results2):
            assert r1.parameters == r2.parameters

    def test_random_search_respects_n_iterations(self, sample_ohlcv, optimizer):
        spaces = [
            ParameterSpace(name="movingAveragePeriod", param_type="INTEGER", min_value=10, max_value=50),
            ParameterSpace(name="rsiPeriod", param_type="INTEGER", min_value=7, max_value=21),
            ParameterSpace(name="overboughtThreshold", param_type="DOUBLE", min_value=70.0, max_value=85.0),
            ParameterSpace(name="oversoldThreshold", param_type="DOUBLE", min_value=15.0, max_value=30.0),
        ]
        results = optimizer.random_search(
            sample_ohlcv, "SMA_RSI", spaces,
            n_iterations=7, top_n=100,
        )
        assert len(results) == 7

    def test_random_search_sorted(self, sample_ohlcv, optimizer, sma_rsi_spaces):
        results = optimizer.random_search(
            sample_ohlcv, "SMA_RSI", sma_rsi_spaces,
            n_iterations=10, metric="sharpe_ratio", top_n=10,
        )
        sharpes = [r.metrics.sharpe_ratio for r in results]
        assert sharpes == sorted(sharpes, reverse=True)

    def test_random_search_parameters_in_range(self, sample_ohlcv, optimizer):
        spaces = [
            ParameterSpace(name="movingAveragePeriod", param_type="INTEGER", min_value=10, max_value=50),
            ParameterSpace(name="rsiPeriod", param_type="INTEGER", min_value=7, max_value=21),
            ParameterSpace(name="overboughtThreshold", param_type="DOUBLE", min_value=70.0, max_value=85.0),
            ParameterSpace(name="oversoldThreshold", param_type="DOUBLE", min_value=15.0, max_value=30.0),
        ]
        results = optimizer.random_search(
            sample_ohlcv, "SMA_RSI", spaces,
            n_iterations=20, top_n=20, seed=99,
        )
        for r in results:
            assert 10 <= r.parameters["movingAveragePeriod"] <= 50
            assert 7 <= r.parameters["rsiPeriod"] <= 21
            assert 70.0 <= r.parameters["overboughtThreshold"] <= 85.0
            assert 15.0 <= r.parameters["oversoldThreshold"] <= 30.0


class TestWalkForwardValidation:
    """Tests for walk-forward validation."""

    def test_walk_forward_returns_results(self, sample_ohlcv, optimizer):
        spaces = [
            ParameterSpace(name="movingAveragePeriod", param_type="INTEGER", min_value=15, max_value=25, step=10),
            ParameterSpace(name="rsiPeriod", param_type="INTEGER", min_value=14, max_value=14, step=1),
            ParameterSpace(name="overboughtThreshold", param_type="DOUBLE", min_value=70.0, max_value=70.0, step=1.0),
            ParameterSpace(name="oversoldThreshold", param_type="DOUBLE", min_value=30.0, max_value=30.0, step=1.0),
        ]
        results = optimizer.walk_forward_validate(
            sample_ohlcv, "SMA_RSI", spaces,
            train_bars=400, test_bars=200,
            search_method="grid", metric="sharpe_ratio",
        )
        assert len(results) > 0

    def test_walk_forward_has_train_and_test_metrics(self, sample_ohlcv, optimizer):
        spaces = [
            ParameterSpace(name="movingAveragePeriod", param_type="INTEGER", min_value=20, max_value=20, step=1),
            ParameterSpace(name="rsiPeriod", param_type="INTEGER", min_value=14, max_value=14, step=1),
            ParameterSpace(name="overboughtThreshold", param_type="DOUBLE", min_value=70.0, max_value=70.0, step=1.0),
            ParameterSpace(name="oversoldThreshold", param_type="DOUBLE", min_value=30.0, max_value=30.0, step=1.0),
        ]
        results = optimizer.walk_forward_validate(
            sample_ohlcv, "SMA_RSI", spaces,
            train_bars=400, test_bars=200,
            search_method="grid",
        )
        for r in results:
            assert len(r.train_metrics) > 0
            assert len(r.test_metrics) > 0
            assert isinstance(r.mean_train_sharpe, float)
            assert isinstance(r.mean_test_sharpe, float)
            assert isinstance(r.overfitting_ratio, float)

    def test_walk_forward_insufficient_data(self, sample_ohlcv, optimizer):
        spaces = [
            ParameterSpace(name="movingAveragePeriod", param_type="INTEGER", min_value=20, max_value=20, step=1),
            ParameterSpace(name="rsiPeriod", param_type="INTEGER", min_value=14, max_value=14, step=1),
            ParameterSpace(name="overboughtThreshold", param_type="DOUBLE", min_value=70.0, max_value=70.0, step=1.0),
            ParameterSpace(name="oversoldThreshold", param_type="DOUBLE", min_value=30.0, max_value=30.0, step=1.0),
        ]
        with pytest.raises(ValueError, match="Not enough data"):
            optimizer.walk_forward_validate(
                sample_ohlcv, "SMA_RSI", spaces,
                train_bars=5000, test_bars=5000,
            )

    def test_walk_forward_random_search(self, sample_ohlcv, optimizer):
        spaces = [
            ParameterSpace(name="movingAveragePeriod", param_type="INTEGER", min_value=10, max_value=30),
            ParameterSpace(name="rsiPeriod", param_type="INTEGER", min_value=7, max_value=21),
            ParameterSpace(name="overboughtThreshold", param_type="DOUBLE", min_value=70.0, max_value=80.0),
            ParameterSpace(name="oversoldThreshold", param_type="DOUBLE", min_value=20.0, max_value=30.0),
        ]
        results = optimizer.walk_forward_validate(
            sample_ohlcv, "SMA_RSI", spaces,
            train_bars=400, test_bars=200,
            search_method="random", n_iterations=5,
        )
        assert len(results) > 0


class TestYamlStrategyOptimization:
    """Tests for YAML-based strategy optimization."""

    @pytest.fixture
    def sma_rsi_spec(self):
        return {
            "name": "SMA_RSI",
            "indicators": [
                {"id": "close", "type": "CLOSE"},
                {"id": "sma", "type": "SMA", "input": "close", "params": {"period": "${movingAveragePeriod}"}},
                {"id": "rsi", "type": "RSI", "input": "close", "params": {"period": "${rsiPeriod}"}},
            ],
            "entryConditions": [
                {"type": "OVER", "indicator": "close", "params": {"other": "sma"}},
                {"type": "UNDER", "indicator": "rsi", "params": {"value": "${oversoldThreshold}"}},
            ],
            "exitConditions": [
                {"type": "OVER", "indicator": "rsi", "params": {"value": "${overboughtThreshold}"}},
            ],
            "parameters": [
                {"name": "movingAveragePeriod", "type": "INTEGER", "min": 10, "max": 30, "defaultValue": 20},
                {"name": "rsiPeriod", "type": "INTEGER", "min": 7, "max": 21, "defaultValue": 14},
                {"name": "overboughtThreshold", "type": "DOUBLE", "min": 70.0, "max": 80.0, "defaultValue": 70.0},
                {"name": "oversoldThreshold", "type": "DOUBLE", "min": 20.0, "max": 30.0, "defaultValue": 30.0},
            ],
        }

    def test_grid_search_with_yaml_spec(self, sample_ohlcv, optimizer, sma_rsi_spec):
        spaces = ParameterOptimizer.spaces_from_yaml(sma_rsi_spec)
        # Use small step to limit combos
        for s in spaces:
            if s.param_type == "INTEGER":
                s.step = max(1, (s.max_value - s.min_value))
            else:
                s.step = max(0.1, (s.max_value - s.min_value))

        results = optimizer.grid_search(
            sample_ohlcv, "SMA_RSI", spaces,
            strategy_spec=sma_rsi_spec, top_n=3,
        )
        assert len(results) > 0
        assert results[0].metrics.sharpe_ratio >= results[-1].metrics.sharpe_ratio

    def test_random_search_with_yaml_spec(self, sample_ohlcv, optimizer, sma_rsi_spec):
        spaces = ParameterOptimizer.spaces_from_yaml(sma_rsi_spec)
        results = optimizer.random_search(
            sample_ohlcv, "SMA_RSI", spaces,
            n_iterations=5, strategy_spec=sma_rsi_spec, top_n=3,
        )
        assert len(results) > 0
