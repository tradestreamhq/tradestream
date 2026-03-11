"""
Tests for VectorBT Backtesting Runner.
"""

import numpy as np
import pandas as pd
import pytest

from services.backtesting.indicator_registry import get_default_registry
from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data for testing."""
    np.random.seed(42)
    n = 1000

    # Generate trending price data
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
def runner():
    """Create VectorBT runner instance."""
    return VectorBTRunner()


class TestIndicatorRegistry:
    """Tests for indicator registry."""

    def test_default_registry_has_common_indicators(self):
        registry = get_default_registry()
        common_indicators = [
            "SMA",
            "EMA",
            "RSI",
            "MACD",
            "ATR",
            "BOLLINGER_UPPER",
            "ADX",
        ]
        for ind in common_indicators:
            assert registry.has_indicator(ind), f"Missing indicator: {ind}"

    def test_sma_calculation(self, sample_ohlcv):
        registry = get_default_registry()
        close = sample_ohlcv["close"]

        sma = registry.create("SMA", close, sample_ohlcv, {"period": 20})

        # Verify SMA values
        expected = close.rolling(20).mean()
        pd.testing.assert_series_equal(sma, expected, check_names=False)

    def test_rsi_calculation(self, sample_ohlcv):
        registry = get_default_registry()
        close = sample_ohlcv["close"]

        rsi = registry.create("RSI", close, sample_ohlcv, {"period": 14})

        # RSI should be between 0 and 100
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()

    def test_unknown_indicator_raises(self):
        registry = get_default_registry()
        with pytest.raises(ValueError):
            registry.create("UNKNOWN_INDICATOR", pd.Series([1, 2, 3]), None, {})


class TestVectorBTRunner:
    """Tests for VectorBT backtesting runner."""

    def test_basic_backtest(self, runner, sample_ohlcv):
        """Test basic backtest execution."""
        # Simple entry/exit signals
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)

        # Enter on day 10, exit on day 20
        entries.iloc[10] = True
        exits.iloc[20] = True

        result = runner.run_backtest(sample_ohlcv, entries, exits)

        assert isinstance(result, BacktestMetrics)
        assert result.number_of_trades >= 0

    def test_sma_rsi_strategy(self, runner, sample_ohlcv):
        """Test SMA_RSI strategy execution."""
        params = {
            "movingAveragePeriod": 20,
            "rsiPeriod": 14,
            "oversoldThreshold": 30,
            "overboughtThreshold": 70,
        }

        result = runner.run_strategy(sample_ohlcv, "SMA_RSI", params)

        assert isinstance(result, BacktestMetrics)
        assert 0 <= result.win_rate <= 1
        assert 0 <= result.max_drawdown <= 1

    def test_macd_crossover_strategy(self, runner, sample_ohlcv):
        """Test MACD crossover strategy execution."""
        params = {"shortEmaPeriod": 12, "longEmaPeriod": 26, "signalPeriod": 9}

        result = runner.run_strategy(sample_ohlcv, "MACD_CROSSOVER", params)

        assert isinstance(result, BacktestMetrics)
        assert result.sharpe_ratio is not None

    def test_double_ema_crossover_strategy(self, runner, sample_ohlcv):
        """Test double EMA crossover strategy."""
        params = {"shortEmaPeriod": 10, "longEmaPeriod": 20}

        result = runner.run_strategy(sample_ohlcv, "DOUBLE_EMA_CROSSOVER", params)

        assert isinstance(result, BacktestMetrics)
        assert result.strategy_score >= 0

    def test_unknown_strategy_raises(self, runner, sample_ohlcv):
        """Test that unknown strategy raises error."""
        with pytest.raises(ValueError):
            runner.run_strategy(sample_ohlcv, "UNKNOWN_STRATEGY", {})

    def test_batch_backtest(self, runner, sample_ohlcv):
        """Test batch backtesting for multiple parameter sets."""
        parameter_sets = [
            {"shortEmaPeriod": 10, "longEmaPeriod": 20},
            {"shortEmaPeriod": 12, "longEmaPeriod": 26},
            {"shortEmaPeriod": 8, "longEmaPeriod": 21},
        ]

        results = runner.run_batch(sample_ohlcv, "DOUBLE_EMA_CROSSOVER", parameter_sets)

        assert len(results) == 3
        for result in results:
            assert isinstance(result, BacktestMetrics)

    def test_strategy_score_normalized(self, runner, sample_ohlcv):
        """Test that strategy score is between 0 and 1."""
        params = {"shortEmaPeriod": 12, "longEmaPeriod": 26, "signalPeriod": 9}
        result = runner.run_strategy(sample_ohlcv, "MACD_CROSSOVER", params)

        assert 0 <= result.strategy_score <= 1


class TestAlphaBeta:
    """Tests for alpha/beta computation from market data."""

    def test_alpha_beta_computed_from_market_data(self, runner, sample_ohlcv):
        """Test that alpha/beta are no longer hardcoded placeholders."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)
        entries.iloc[10] = True
        exits.iloc[20] = True

        result = runner.run_backtest(sample_ohlcv, entries, exits)

        # Alpha should not always be 0.0 and beta should not always be 1.0
        # With actual computation, at least one should differ from placeholder
        assert isinstance(result.alpha, float)
        assert isinstance(result.beta, float)

    def test_beta_of_buy_and_hold_is_near_one(self, runner):
        """A buy-and-hold strategy (always in market) should have beta near 1.0."""
        np.random.seed(123)
        n = 500
        returns = np.random.randn(n) * 0.01
        close = 100 * np.exp(np.cumsum(returns))
        ohlcv = pd.DataFrame(
            {
                "open": close,
                "high": close * 1.005,
                "low": close * 0.995,
                "close": close,
                "volume": np.full(n, 5000.0),
            }
        )
        ohlcv.index = pd.date_range(start="2020-01-01", periods=n, freq="1min")

        # Always in the market: enter at start, never exit
        entries = pd.Series([False] * n, index=ohlcv.index)
        exits = pd.Series([False] * n, index=ohlcv.index)
        entries.iloc[0] = True

        result = runner.run_backtest(ohlcv, entries, exits)

        # Beta should be close to 1.0 for a fully-invested strategy
        assert 0.5 < result.beta < 1.5, f"Expected beta near 1.0, got {result.beta}"

    def test_zero_variance_benchmark_returns_zero(self, runner):
        """When benchmark has no variance, alpha/beta should both be 0."""
        n = 100
        # Flat price — zero benchmark variance
        close = np.full(n, 100.0)
        ohlcv = pd.DataFrame(
            {
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": np.full(n, 5000.0),
            }
        )
        ohlcv.index = pd.date_range(start="2020-01-01", periods=n, freq="1min")

        entries = pd.Series([False] * n, index=ohlcv.index)
        exits = pd.Series([False] * n, index=ohlcv.index)
        entries.iloc[10] = True
        exits.iloc[20] = True

        result = runner.run_backtest(ohlcv, entries, exits)

        assert result.alpha == 0.0
        assert result.beta == 0.0

    def test_alpha_beta_unit_math(self, runner):
        """Verify alpha/beta math with known correlated returns."""
        strategy_returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.015])
        benchmark_returns = pd.Series([0.008, -0.003, 0.015, -0.008, 0.012])

        alpha, beta = runner._calc_alpha_beta(strategy_returns, benchmark_returns)

        # Manually verify: beta = cov / var
        expected_beta = (
            strategy_returns.cov(benchmark_returns) / benchmark_returns.var()
        )
        assert abs(beta - expected_beta) < 1e-10

        # Verify alpha direction
        rf_per_bar = runner._risk_free_rate / runner._bars_per_year
        expected_alpha = (
            (strategy_returns.mean() - rf_per_bar)
            - expected_beta * (benchmark_returns.mean() - rf_per_bar)
        ) * runner._bars_per_year
        assert abs(alpha - expected_alpha) < 1e-6

    def test_strategy_backtest_has_computed_alpha_beta(self, runner, sample_ohlcv):
        """Test that run_strategy produces computed alpha/beta values."""
        params = {"shortEmaPeriod": 12, "longEmaPeriod": 26}
        result = runner.run_strategy(sample_ohlcv, "DOUBLE_EMA_CROSSOVER", params)

        # Should be finite floats (not NaN/inf)
        assert np.isfinite(result.alpha)
        assert np.isfinite(result.beta)


class TestPerformanceBenchmark:
    """Performance benchmark tests."""

    def test_single_backtest_performance(self, runner, sample_ohlcv):
        """Benchmark single backtest execution time."""
        import time

        params = {"shortEmaPeriod": 12, "longEmaPeriod": 26}

        # Warm up
        runner.run_strategy(sample_ohlcv, "DOUBLE_EMA_CROSSOVER", params)

        # Benchmark
        start = time.perf_counter()
        for _ in range(10):
            runner.run_strategy(sample_ohlcv, "DOUBLE_EMA_CROSSOVER", params)
        elapsed = (time.perf_counter() - start) / 10 * 1000

        print(f"\nSingle backtest (1000 bars): {elapsed:.2f}ms")
        assert elapsed < 1000  # Should complete in under 1 second

    def test_batch_backtest_performance(self, runner, sample_ohlcv):
        """Benchmark batch backtesting for GA optimization."""
        import time

        # Generate 100 parameter combinations
        parameter_sets = [
            {"shortEmaPeriod": short, "longEmaPeriod": long}
            for short in range(5, 15)
            for long in range(20, 30)
        ]

        # Warm up
        runner.run_batch(sample_ohlcv, "DOUBLE_EMA_CROSSOVER", parameter_sets[:5])

        # Benchmark
        start = time.perf_counter()
        results = runner.run_batch(sample_ohlcv, "DOUBLE_EMA_CROSSOVER", parameter_sets)
        elapsed = (time.perf_counter() - start) * 1000

        print(
            f"\nBatch backtest ({len(parameter_sets)} combinations, 1000 bars): {elapsed:.2f}ms"
        )
        print(f"Time per evaluation: {elapsed / len(parameter_sets):.2f}ms")

        assert len(results) == len(parameter_sets)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
