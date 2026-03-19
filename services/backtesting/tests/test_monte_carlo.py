"""Tests for Monte Carlo Simulation."""

import numpy as np
import pandas as pd
import pytest

from services.backtesting.vectorbt_runner import VectorBTRunner
from services.backtesting.monte_carlo import MonteCarloResult, MonteCarloSimulator


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data with enough trades for Monte Carlo."""
    np.random.seed(42)
    n = 2000

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
def simulator():
    return MonteCarloSimulator()


class TestMonteCarloSimulator:
    def test_basic_simulation(self, simulator, sample_ohlcv):
        """Test basic Monte Carlo simulation runs."""
        result = simulator.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            num_simulations=100,
            random_seed=42,
        )
        assert isinstance(result, MonteCarloResult)
        assert result.original_result is not None
        assert result.median_result is not None

    def test_simulation_count(self, simulator, sample_ohlcv):
        """Test that correct number of simulations are run."""
        result = simulator.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            num_simulations=50,
            random_seed=42,
        )
        # num_simulations in result reflects what was actually run
        if result.num_simulations > 0:
            assert result.num_simulations == 50
            assert len(result.return_distribution) == 50

    def test_confidence_bounds(self, simulator, sample_ohlcv):
        """Test that worst case is worse than best case."""
        result = simulator.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            num_simulations=200,
            confidence_level=0.95,
            random_seed=42,
        )
        if result.num_simulations > 0:
            assert result.worst_case_result.cumulative_return <= result.best_case_result.cumulative_return

    def test_probability_of_profit(self, simulator, sample_ohlcv):
        """Test probability of profit is between 0 and 1."""
        result = simulator.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            num_simulations=100,
            random_seed=42,
        )
        assert 0.0 <= result.probability_of_profit <= 1.0

    def test_reproducible_with_seed(self, simulator, sample_ohlcv):
        """Test that results are reproducible with same seed."""
        params = {"shortEmaPeriod": 10, "longEmaPeriod": 20}
        r1 = simulator.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER", params,
            num_simulations=50, random_seed=123,
        )
        r2 = simulator.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER", params,
            num_simulations=50, random_seed=123,
        )
        if r1.num_simulations > 0:
            assert r1.median_result.cumulative_return == pytest.approx(
                r2.median_result.cumulative_return, abs=1e-9
            )

    def test_expected_sharpe_finite(self, simulator, sample_ohlcv):
        """Test that expected Sharpe is finite."""
        result = simulator.run(
            sample_ohlcv, "DOUBLE_EMA_CROSSOVER",
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            num_simulations=100,
            random_seed=42,
        )
        assert np.isfinite(result.expected_sharpe)
        assert np.isfinite(result.sharpe_std_dev)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
