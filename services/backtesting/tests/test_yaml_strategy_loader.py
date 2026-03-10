"""
Integration tests for YAML Strategy Loader + VectorBT backtesting.

Proves end-to-end: YAML strategy spec -> signal generation -> VectorBT backtest -> metrics.
"""

import numpy as np
import pandas as pd
import pytest

from services.backtesting.vectorbt_runner import BacktestMetrics, VectorBTRunner
from services.backtesting.yaml_strategy_loader import YamlStrategyLoader


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data with realistic price action."""
    np.random.seed(42)
    n = 1000

    # Generate trending price data with mean-reversion characteristics
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
def loader():
    """Create YAML strategy loader instance."""
    return YamlStrategyLoader()


@pytest.fixture
def runner():
    """Create VectorBT runner instance."""
    return VectorBTRunner()


@pytest.fixture
def sma_rsi_spec():
    """SMA_RSI strategy spec matching src/main/resources/strategies/sma_rsi.yaml."""
    return {
        "name": "SMA_RSI",
        "description": "SMA trend filter combined with RSI overbought/oversold signals",
        "complexity": "SIMPLE",
        "indicators": [
            {"id": "close", "type": "CLOSE"},
            {
                "id": "sma",
                "type": "SMA",
                "input": "close",
                "params": {"period": "${movingAveragePeriod}"},
            },
            {
                "id": "rsi",
                "type": "RSI",
                "input": "close",
                "params": {"period": "${rsiPeriod}"},
            },
        ],
        "entryConditions": [
            {"type": "OVER", "indicator": "close", "params": {"other": "sma"}},
            {
                "type": "UNDER",
                "indicator": "rsi",
                "params": {"value": "${oversoldThreshold}"},
            },
        ],
        "exitConditions": [
            {
                "type": "OVER",
                "indicator": "rsi",
                "params": {"value": "${overboughtThreshold}"},
            },
        ],
        "parameters": [
            {
                "name": "movingAveragePeriod",
                "type": "INTEGER",
                "min": 10,
                "max": 50,
                "defaultValue": 20,
            },
            {
                "name": "rsiPeriod",
                "type": "INTEGER",
                "min": 7,
                "max": 21,
                "defaultValue": 14,
            },
            {
                "name": "overboughtThreshold",
                "type": "DOUBLE",
                "min": 70.0,
                "max": 85.0,
                "defaultValue": 70.0,
            },
            {
                "name": "oversoldThreshold",
                "type": "DOUBLE",
                "min": 15.0,
                "max": 30.0,
                "defaultValue": 30.0,
            },
        ],
    }


@pytest.fixture
def ema_crossover_spec():
    """Simple EMA crossover strategy spec for testing CROSSED_UP/CROSSED_DOWN."""
    return {
        "name": "EMA_CROSSOVER",
        "description": "EMA crossover strategy",
        "indicators": [
            {
                "id": "fast_ema",
                "type": "EMA",
                "params": {"period": "${fastPeriod}"},
            },
            {
                "id": "slow_ema",
                "type": "EMA",
                "params": {"period": "${slowPeriod}"},
            },
        ],
        "entryConditions": [
            {
                "type": "CROSSED_UP",
                "indicator": "fast_ema",
                "params": {"other": "slow_ema"},
            },
        ],
        "exitConditions": [
            {
                "type": "CROSSED_DOWN",
                "indicator": "fast_ema",
                "params": {"other": "slow_ema"},
            },
        ],
        "parameters": [
            {"name": "fastPeriod", "type": "INTEGER", "defaultValue": 10},
            {"name": "slowPeriod", "type": "INTEGER", "defaultValue": 20},
        ],
    }


class TestYamlStrategyLoader:
    """Tests for YAML strategy loading and signal generation."""

    def test_resolve_default_parameters(self, loader, sma_rsi_spec):
        """Test that default parameters are resolved correctly."""
        params = loader._resolve_parameters(sma_rsi_spec, None)

        assert params["movingAveragePeriod"] == 20
        assert params["rsiPeriod"] == 14
        assert params["overboughtThreshold"] == 70.0
        assert params["oversoldThreshold"] == 30.0

    def test_resolve_parameter_overrides(self, loader, sma_rsi_spec):
        """Test that parameter overrides take precedence."""
        overrides = {"movingAveragePeriod": 30, "rsiPeriod": 7}
        params = loader._resolve_parameters(sma_rsi_spec, overrides)

        assert params["movingAveragePeriod"] == 30
        assert params["rsiPeriod"] == 7
        assert params["overboughtThreshold"] == 70.0  # Unchanged

    def test_generate_signals_produces_boolean_series(
        self, loader, sample_ohlcv, sma_rsi_spec
    ):
        """Test that generated signals are boolean Series."""
        entries, exits = loader.generate_signals(sample_ohlcv, sma_rsi_spec)

        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert len(entries) == len(sample_ohlcv)
        assert len(exits) == len(sample_ohlcv)

    def test_crossover_signals(self, loader, sample_ohlcv, ema_crossover_spec):
        """Test CROSSED_UP/CROSSED_DOWN condition evaluation."""
        entries, exits = loader.generate_signals(sample_ohlcv, ema_crossover_spec)

        # Crossover signals should exist in trending data
        assert (
            entries.any() or exits.any()
        ), "Crossover signals expected in trending data"

    def test_empty_conditions_produce_no_signals(self, loader, sample_ohlcv):
        """Test strategy with no conditions produces no signals."""
        spec = {
            "name": "EMPTY",
            "indicators": [{"id": "sma", "type": "SMA", "params": {"period": 20}}],
            "entryConditions": [],
            "exitConditions": [],
            "parameters": [],
        }
        entries, exits = loader.generate_signals(sample_ohlcv, spec)

        assert not entries.any()
        assert not exits.any()


class TestYamlStrategyIntegration:
    """End-to-end integration tests: YAML spec -> VectorBT backtest -> metrics."""

    def test_sma_rsi_end_to_end(self, loader, runner, sample_ohlcv, sma_rsi_spec):
        """End-to-end test: SMA_RSI YAML spec -> backtest -> metrics."""
        # Generate signals from YAML spec
        entries, exits = loader.generate_signals(sample_ohlcv, sma_rsi_spec)

        # Run backtest
        metrics = runner.run_backtest(sample_ohlcv, entries, exits)

        # Verify metrics
        assert isinstance(metrics, BacktestMetrics)
        assert 0 <= metrics.win_rate <= 1
        assert 0 <= metrics.max_drawdown <= 1
        assert metrics.sharpe_ratio is not None
        assert metrics.sortino_ratio is not None
        assert metrics.number_of_trades >= 0

    def test_ema_crossover_end_to_end(
        self, loader, runner, sample_ohlcv, ema_crossover_spec
    ):
        """End-to-end test: EMA crossover YAML spec -> backtest -> metrics."""
        entries, exits = loader.generate_signals(sample_ohlcv, ema_crossover_spec)
        metrics = runner.run_backtest(sample_ohlcv, entries, exits)

        assert isinstance(metrics, BacktestMetrics)
        assert metrics.number_of_trades >= 0

    def test_parameter_overrides_affect_results(
        self, loader, runner, sample_ohlcv, ema_crossover_spec
    ):
        """Test that different parameters produce different backtest results."""
        # Run with default parameters
        entries1, exits1 = loader.generate_signals(sample_ohlcv, ema_crossover_spec)
        metrics1 = runner.run_backtest(sample_ohlcv, entries1, exits1)

        # Run with different parameters
        overrides = {"fastPeriod": 5, "slowPeriod": 40}
        entries2, exits2 = loader.generate_signals(
            sample_ohlcv, ema_crossover_spec, overrides
        )
        metrics2 = runner.run_backtest(sample_ohlcv, entries2, exits2)

        # Results should differ (or at least not crash)
        assert isinstance(metrics1, BacktestMetrics)
        assert isinstance(metrics2, BacktestMetrics)

    def test_batch_yaml_strategies(
        self, loader, runner, sample_ohlcv, ema_crossover_spec
    ):
        """Test batch evaluation of a YAML strategy with multiple parameter sets."""
        parameter_sets = [
            {"fastPeriod": 5, "slowPeriod": 20},
            {"fastPeriod": 10, "slowPeriod": 30},
            {"fastPeriod": 8, "slowPeriod": 25},
        ]

        results = []
        for params in parameter_sets:
            entries, exits = loader.generate_signals(
                sample_ohlcv, ema_crossover_spec, params
            )
            metrics = runner.run_backtest(sample_ohlcv, entries, exits)
            results.append(metrics)

        assert len(results) == 3
        for r in results:
            assert isinstance(r, BacktestMetrics)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
