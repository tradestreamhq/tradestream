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


class TestRiskMetricCalculations:
    """Tests for alpha, beta, and other risk metric calculations."""

    def test_beta_calculation(self, runner):
        """Test beta calculation with known correlated returns."""
        np.random.seed(42)
        n = 1000
        benchmark = pd.Series(np.random.randn(n) * 0.01)
        # Strategy returns = 1.5 * benchmark + noise (beta ~1.5)
        strategy = 1.5 * benchmark + pd.Series(np.random.randn(n) * 0.002)

        beta = runner._calc_beta(strategy, benchmark)
        assert 1.3 < beta < 1.7, f"Expected beta near 1.5, got {beta}"

    def test_beta_zero_variance_benchmark(self, runner):
        """Test beta returns 0 when benchmark has zero variance."""
        strategy = pd.Series([0.01, -0.02, 0.03])
        benchmark = pd.Series([0.0, 0.0, 0.0])

        beta = runner._calc_beta(strategy, benchmark)
        assert beta == 0.0

    def test_beta_identical_returns(self, runner):
        """Test beta is 1.0 when strategy equals benchmark."""
        returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        beta = runner._calc_beta(returns, returns)
        assert abs(beta - 1.0) < 0.01

    def test_alpha_outperforming_strategy(self, runner):
        """Test alpha is positive when strategy outperforms."""
        np.random.seed(42)
        n = 1000
        benchmark = pd.Series(np.random.randn(n) * 0.001)
        # Strategy has consistent positive excess returns
        strategy = benchmark + 0.001

        beta = runner._calc_beta(strategy, benchmark)
        alpha = runner._calc_alpha(strategy, benchmark, beta, n)
        assert alpha > 0, f"Expected positive alpha, got {alpha}"

    def test_alpha_underperforming_strategy(self, runner):
        """Test alpha is negative when strategy underperforms."""
        np.random.seed(42)
        n = 1000
        benchmark = pd.Series(np.random.randn(n) * 0.001 + 0.001)
        # Strategy consistently underperforms
        strategy = benchmark - 0.002

        beta = runner._calc_beta(strategy, benchmark)
        alpha = runner._calc_alpha(strategy, benchmark, beta, n)
        assert alpha < 0, f"Expected negative alpha, got {alpha}"

    def test_alpha_zero_bars(self, runner):
        """Test alpha returns 0 with zero-length data."""
        strategy = pd.Series([], dtype=float)
        benchmark = pd.Series([], dtype=float)
        alpha = runner._calc_alpha(strategy, benchmark, 1.0, 0)
        assert alpha == 0.0

    def test_backtest_computes_alpha_beta(self, runner, sample_ohlcv):
        """Test that run_backtest returns computed (non-placeholder) alpha and beta."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)
        entries.iloc[10] = True
        exits.iloc[20] = True

        result = runner.run_backtest(sample_ohlcv, entries, exits)

        # Alpha and beta should be real numbers, not the old placeholders
        assert isinstance(result.alpha, float)
        assert isinstance(result.beta, float)
        # Beta should not be exactly 1.0 (the old placeholder) for a strategy
        # that only trades once vs buy-and-hold
        assert result.beta != 1.0 or result.alpha != 0.0

    def test_backtest_with_custom_benchmark(self, runner, sample_ohlcv):
        """Test run_backtest accepts custom benchmark returns."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)
        entries.iloc[10] = True
        exits.iloc[20] = True

        # Use flat benchmark (zero returns)
        flat_benchmark = pd.Series(0.0, index=sample_ohlcv.index)
        result = runner.run_backtest(
            sample_ohlcv, entries, exits, benchmark_returns=flat_benchmark
        )

        assert isinstance(result.alpha, float)
        # With zero-variance benchmark, beta should be 0
        assert result.beta == 0.0


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
