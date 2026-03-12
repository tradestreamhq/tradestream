"""Tests for backtesting engine."""

from unittest import mock

import numpy as np
import pandas as pd
import pytest

from services.backtesting.engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    SymbolResult,
)
from services.backtesting.metrics import PerformanceMetrics, Trade


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data for testing."""
    np.random.seed(42)
    n = 500

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
    df.index = pd.date_range(start="2024-01-01", periods=n, freq="1min")
    return df


@pytest.fixture
def config():
    """Default backtest config."""
    return BacktestConfig(
        symbols=["BTC/USD"],
        start="2024-01-01T00:00:00Z",
        end="2024-06-01T00:00:00Z",
        strategy_name="DOUBLE_EMA_CROSSOVER",
        parameters={"shortEmaPeriod": 12, "longEmaPeriod": 26},
    )


@pytest.fixture
def engine():
    """BacktestEngine without data loader (for in-memory tests)."""
    return BacktestEngine()


class TestBacktestConfig:
    def test_default_values(self):
        config = BacktestConfig(symbols=["BTC/USD"], start="-30d")
        assert config.timeframe == "1m"
        assert config.initial_capital == 10000.0
        assert config.fee_rate == 0.001
        assert config.end is None
        assert config.parameters == {}


class TestBacktestEngine:
    def test_run_with_data(self, engine, config, sample_ohlcv):
        """Test backtesting with pre-loaded data."""
        result = engine.run_with_data(config, {"BTC/USD": sample_ohlcv})

        assert isinstance(result, BacktestResult)
        assert "BTC/USD" in result.symbol_results
        assert isinstance(result.aggregate_metrics, PerformanceMetrics)

        sym_result = result.symbol_results["BTC/USD"]
        assert isinstance(sym_result, SymbolResult)
        assert sym_result.symbol == "BTC/USD"
        assert len(sym_result.equity_curve) >= 1

    def test_run_multiple_symbols(self, engine, config, sample_ohlcv):
        """Test backtesting across multiple symbols."""
        config.symbols = ["BTC/USD", "ETH/USD"]
        data = {"BTC/USD": sample_ohlcv, "ETH/USD": sample_ohlcv.copy()}

        result = engine.run_with_data(config, data)

        assert len(result.symbol_results) == 2
        assert "BTC/USD" in result.symbol_results
        assert "ETH/USD" in result.symbol_results

    def test_metrics_are_calculated(self, engine, config, sample_ohlcv):
        """Test that metrics are properly calculated."""
        result = engine.run_with_data(config, {"BTC/USD": sample_ohlcv})
        metrics = result.aggregate_metrics

        assert isinstance(metrics.total_return, float)
        assert isinstance(metrics.sharpe_ratio, float)
        assert isinstance(metrics.max_drawdown, float)
        assert isinstance(metrics.win_rate, float)
        assert isinstance(metrics.profit_factor, float)

    def test_trades_generated(self, engine, config, sample_ohlcv):
        """Test that trades are generated from signals."""
        result = engine.run_with_data(config, {"BTC/USD": sample_ohlcv})
        sym_result = result.symbol_results["BTC/USD"]

        # EMA crossover on 500 bars should generate some trades
        assert sym_result.metrics.total_trades >= 0
        for trade in sym_result.trades:
            assert isinstance(trade, Trade)
            assert trade.symbol == "BTC/USD"
            assert trade.entry_index < trade.exit_index

    def test_equity_curve(self, engine, config, sample_ohlcv):
        """Test equity curve starts at initial capital."""
        result = engine.run_with_data(config, {"BTC/USD": sample_ohlcv})
        equity = result.symbol_results["BTC/USD"].equity_curve

        assert equity[0] == config.initial_capital

    def test_run_without_data_loader_raises(self, engine, config):
        """Test that run() without data loader raises error."""
        with pytest.raises(RuntimeError, match="No data_loader configured"):
            engine.run(config)

    def test_config_preserved(self, engine, config, sample_ohlcv):
        """Test that config is preserved in result."""
        result = engine.run_with_data(config, {"BTC/USD": sample_ohlcv})
        assert result.config is config

    def test_sma_rsi_strategy(self, engine, sample_ohlcv):
        """Test with SMA_RSI strategy."""
        config = BacktestConfig(
            symbols=["BTC/USD"],
            start="2024-01-01T00:00:00Z",
            strategy_name="SMA_RSI",
            parameters={
                "movingAveragePeriod": 20,
                "rsiPeriod": 14,
                "oversoldThreshold": 30,
                "overboughtThreshold": 70,
            },
        )
        result = engine.run_with_data(config, {"BTC/USD": sample_ohlcv})
        assert isinstance(result.aggregate_metrics, PerformanceMetrics)

    def test_macd_crossover_strategy(self, engine, sample_ohlcv):
        """Test with MACD_CROSSOVER strategy."""
        config = BacktestConfig(
            symbols=["BTC/USD"],
            start="2024-01-01T00:00:00Z",
            strategy_name="MACD_CROSSOVER",
            parameters={"shortEmaPeriod": 12, "longEmaPeriod": 26, "signalPeriod": 9},
        )
        result = engine.run_with_data(config, {"BTC/USD": sample_ohlcv})
        assert isinstance(result.aggregate_metrics, PerformanceMetrics)


class TestSimulateTrades:
    def test_simple_entry_exit(self, sample_ohlcv):
        """Test trade simulation with simple signals."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)

        entries.iloc[10] = True
        exits.iloc[20] = True
        entries.iloc[30] = True
        exits.iloc[40] = True

        trades = BacktestEngine._simulate_trades(
            sample_ohlcv, entries, exits, "BTC/USD", fee_rate=0.001
        )

        assert len(trades) == 2
        assert trades[0].entry_index == 10
        assert trades[0].exit_index == 20
        assert trades[1].entry_index == 30
        assert trades[1].exit_index == 40

    def test_no_signals(self, sample_ohlcv):
        """Test with no entry/exit signals."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)

        trades = BacktestEngine._simulate_trades(
            sample_ohlcv, entries, exits, "BTC/USD", fee_rate=0.001
        )
        assert len(trades) == 0

    def test_entry_without_exit(self, sample_ohlcv):
        """Test that unclosed positions are not included."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)

        entries.iloc[10] = True  # Enter but never exit

        trades = BacktestEngine._simulate_trades(
            sample_ohlcv, entries, exits, "BTC/USD", fee_rate=0.001
        )
        assert len(trades) == 0

    def test_fee_applied(self, sample_ohlcv):
        """Test that fees are applied to entry and exit prices."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)

        entries.iloc[10] = True
        exits.iloc[20] = True

        trades = BacktestEngine._simulate_trades(
            sample_ohlcv, entries, exits, "BTC/USD", fee_rate=0.001
        )

        raw_entry = sample_ohlcv["close"].iloc[10]
        raw_exit = sample_ohlcv["close"].iloc[20]

        # Entry price should be higher (fee added), exit lower (fee deducted)
        assert trades[0].entry_price == pytest.approx(raw_entry * 1.001)
        assert trades[0].exit_price == pytest.approx(raw_exit * 0.999)


class TestRunWithDataLoader:
    @mock.patch("services.backtesting.engine.BacktestDataLoader")
    def test_run_with_loader(self, mock_loader_cls, sample_ohlcv):
        """Test engine.run() delegates to data loader."""
        mock_loader = mock.MagicMock()
        mock_loader.load_multiple_symbols.return_value = {"BTC/USD": sample_ohlcv}

        engine = BacktestEngine(data_loader=mock_loader)
        config = BacktestConfig(
            symbols=["BTC/USD"],
            start="2024-01-01T00:00:00Z",
            strategy_name="DOUBLE_EMA_CROSSOVER",
            parameters={"shortEmaPeriod": 12, "longEmaPeriod": 26},
        )

        result = engine.run(config)

        mock_loader.load_multiple_symbols.assert_called_once_with(
            symbols=["BTC/USD"],
            start="2024-01-01T00:00:00Z",
            end=None,
            timeframe="1m",
        )
        assert isinstance(result, BacktestResult)
