"""Tests for Walk-Forward Optimization."""

import numpy as np
import pandas as pd
import pytest

from services.backtesting.vectorbt_runner import VectorBTRunner
from services.backtesting.walk_forward import (
    WalkForwardConfig,
    WalkForwardOptimizer,
    WalkForwardResult,
)


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data large enough for walk-forward."""
    np.random.seed(42)
    n = 20000  # Enough for multiple train/test windows

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
def small_ohlcv():
    """Create small OHLCV data insufficient for walk-forward."""
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame({
        "open": close, "high": close + 1, "low": close - 1,
        "close": close, "volume": np.full(n, 1000.0),
    })
    df.index = pd.date_range(start="2020-01-01", periods=n, freq="1min")
    return df


@pytest.fixture
def optimizer():
    return WalkForwardOptimizer()


class TestWalkForwardOptimizer:
    def test_insufficient_data(self, optimizer, small_ohlcv):
        """Test that insufficient data returns INSUFFICIENT_DATA status."""
        result = optimizer.run(
            small_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
        )
        assert result.status == "INSUFFICIENT_DATA"
        assert result.windows_count == 0

    def test_basic_walk_forward(self, optimizer, sample_ohlcv):
        """Test walk-forward runs and produces window results."""
        config = WalkForwardConfig(
            train_window_bars=4000,
            test_window_bars=2000,
            step_bars=2000,
            min_windows=2,
        )
        result = optimizer.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            config=config,
        )
        assert isinstance(result, WalkForwardResult)
        assert result.windows_count >= 2
        assert len(result.window_results) == result.windows_count
        assert result.status in ("APPROVED", "REJECTED")

    def test_window_results_have_metrics(self, optimizer, sample_ohlcv):
        """Test that each window result has valid metrics."""
        config = WalkForwardConfig(
            train_window_bars=4000,
            test_window_bars=2000,
            step_bars=2000,
            min_windows=2,
        )
        result = optimizer.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            config=config,
        )
        for wr in result.window_results:
            assert wr.in_sample_result is not None
            assert wr.out_of_sample_result is not None
            assert wr.train_start_bar < wr.train_end_bar
            assert wr.test_start_bar < wr.test_end_bar
            assert wr.train_end_bar == wr.test_start_bar

    def test_sharpe_degradation_computed(self, optimizer, sample_ohlcv):
        """Test that Sharpe degradation is computed."""
        config = WalkForwardConfig(
            train_window_bars=4000,
            test_window_bars=2000,
            step_bars=2000,
            min_windows=2,
        )
        result = optimizer.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            config=config,
        )
        # Sharpe degradation should be a real number
        assert np.isfinite(result.sharpe_degradation)
        assert np.isfinite(result.oos_sharpe_std_dev)

    def test_min_windows_respected(self, optimizer, sample_ohlcv):
        """Test that min_windows threshold is respected."""
        config = WalkForwardConfig(
            train_window_bars=4000,
            test_window_bars=2000,
            step_bars=2000,
            min_windows=100,  # Impossible to satisfy
        )
        result = optimizer.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            config=config,
        )
        assert result.status == "INSUFFICIENT_DATA"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
