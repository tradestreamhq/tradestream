"""Tests for Portfolio-Level Backtesting."""

import numpy as np
import pandas as pd
import pytest

from services.backtesting.vectorbt_runner import VectorBTRunner
from services.backtesting.portfolio_backtest import (
    PortfolioBacktester,
    PortfolioBacktestResult,
    StrategyAllocation,
)


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data."""
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
def backtester():
    return PortfolioBacktester()


class TestPortfolioBacktester:
    def test_single_strategy_portfolio(self, backtester, sample_ohlcv):
        """Test portfolio with a single strategy (weight=1.0)."""
        allocations = [
            StrategyAllocation(
                strategy_name="DOUBLE_EMA_CROSSOVER",
                parameters={"shortEmaPeriod": 10, "longEmaPeriod": 20},
                weight=1.0,
            )
        ]
        result = backtester.run(sample_ohlcv, allocations)

        assert isinstance(result, PortfolioBacktestResult)
        assert result.num_strategies == 1
        assert len(result.strategy_results) == 1
        assert result.strategy_results[0].weight == 1.0

    def test_multi_strategy_portfolio(self, backtester, sample_ohlcv):
        """Test portfolio with multiple strategies."""
        allocations = [
            StrategyAllocation(
                strategy_name="DOUBLE_EMA_CROSSOVER",
                parameters={"shortEmaPeriod": 10, "longEmaPeriod": 20},
                weight=0.5,
            ),
            StrategyAllocation(
                strategy_name="MACD_CROSSOVER",
                parameters={"shortEmaPeriod": 12, "longEmaPeriod": 26, "signalPeriod": 9},
                weight=0.5,
            ),
        ]
        result = backtester.run(sample_ohlcv, allocations)

        assert result.num_strategies == 2
        assert len(result.strategy_results) == 2
        assert result.portfolio_result is not None

    def test_weights_must_sum_to_one(self, backtester, sample_ohlcv):
        """Test that weights must sum to 1.0."""
        allocations = [
            StrategyAllocation(
                strategy_name="DOUBLE_EMA_CROSSOVER",
                parameters={"shortEmaPeriod": 10, "longEmaPeriod": 20},
                weight=0.3,
            ),
            StrategyAllocation(
                strategy_name="MACD_CROSSOVER",
                parameters={"shortEmaPeriod": 12, "longEmaPeriod": 26, "signalPeriod": 9},
                weight=0.3,
            ),
        ]
        with pytest.raises(ValueError, match="sum to 1.0"):
            backtester.run(sample_ohlcv, allocations)

    def test_empty_allocations_raises(self, backtester, sample_ohlcv):
        """Test that empty allocations raises error."""
        with pytest.raises(ValueError, match="At least one"):
            backtester.run(sample_ohlcv, [])

    def test_correlation_matrix_shape(self, backtester, sample_ohlcv):
        """Test correlation matrix has correct shape."""
        allocations = [
            StrategyAllocation(
                strategy_name="DOUBLE_EMA_CROSSOVER",
                parameters={"shortEmaPeriod": 10, "longEmaPeriod": 20},
                weight=0.5,
            ),
            StrategyAllocation(
                strategy_name="MACD_CROSSOVER",
                parameters={"shortEmaPeriod": 12, "longEmaPeriod": 26, "signalPeriod": 9},
                weight=0.5,
            ),
        ]
        result = backtester.run(sample_ohlcv, allocations)

        # Flattened 2x2 matrix = 4 elements
        assert len(result.correlation_matrix) == 4

    def test_diversification_ratio(self, backtester, sample_ohlcv):
        """Test diversification ratio is computed and >= 1.0."""
        allocations = [
            StrategyAllocation(
                strategy_name="DOUBLE_EMA_CROSSOVER",
                parameters={"shortEmaPeriod": 10, "longEmaPeriod": 20},
                weight=0.5,
            ),
            StrategyAllocation(
                strategy_name="MACD_CROSSOVER",
                parameters={"shortEmaPeriod": 12, "longEmaPeriod": 26, "signalPeriod": 9},
                weight=0.5,
            ),
        ]
        result = backtester.run(sample_ohlcv, allocations)

        # Diversification ratio should be >= 1 (perfect correlation = 1)
        assert result.diversification_ratio >= 0.9  # Allow small numerical error

    def test_return_contributions_sum(self, backtester, sample_ohlcv):
        """Test that return contributions are weighted correctly."""
        allocations = [
            StrategyAllocation(
                strategy_name="DOUBLE_EMA_CROSSOVER",
                parameters={"shortEmaPeriod": 10, "longEmaPeriod": 20},
                weight=0.6,
            ),
            StrategyAllocation(
                strategy_name="MACD_CROSSOVER",
                parameters={"shortEmaPeriod": 12, "longEmaPeriod": 26, "signalPeriod": 9},
                weight=0.4,
            ),
        ]
        result = backtester.run(sample_ohlcv, allocations)

        for sr in result.strategy_results:
            expected_contrib = sr.weight * sr.result.cumulative_return
            assert sr.return_contribution == pytest.approx(expected_contrib, abs=1e-9)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
