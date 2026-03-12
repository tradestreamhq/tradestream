"""
Tests for the backtesting engine.
"""

import numpy as np
import pandas as pd
import pytest

from services.backtesting.engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestSummary,
    CommissionModel,
)


@pytest.fixture
def sample_ohlcv():
    """Create sample OHLCV data with a clear uptrend for predictable tests."""
    np.random.seed(42)
    n = 500

    # Generate trending price data
    returns = np.random.randn(n) * 0.005 + 0.0002  # slight upward drift
    close = 100 * np.exp(np.cumsum(returns))

    high = close * (1 + np.abs(np.random.randn(n) * 0.005))
    low = close * (1 - np.abs(np.random.randn(n) * 0.005))
    open_price = np.roll(close, 1)
    open_price[0] = close[0]

    high = np.maximum(high, np.maximum(open_price, close))
    low = np.minimum(low, np.minimum(open_price, close))

    volume = np.random.randint(1000, 10000, n).astype(float)

    df = pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )
    df.index = pd.date_range(start="2020-01-01", periods=n, freq="1min")
    return df


@pytest.fixture
def simple_signals(sample_ohlcv):
    """Entry at bar 10, exit at bar 50; entry at bar 100, exit at bar 150."""
    n = len(sample_ohlcv)
    entries = pd.Series([False] * n, index=sample_ohlcv.index)
    exits = pd.Series([False] * n, index=sample_ohlcv.index)

    entries.iloc[10] = True
    exits.iloc[50] = True
    entries.iloc[100] = True
    exits.iloc[150] = True

    return entries, exits


class TestCommissionModel:
    def test_percentage_commission(self):
        model = CommissionModel(percentage=0.001)
        assert model.calculate(10000) == pytest.approx(10.0)

    def test_flat_fee_commission(self):
        model = CommissionModel(flat_fee=5.0, percentage=0.0)
        assert model.calculate(10000) == pytest.approx(5.0)

    def test_combined_commission(self):
        model = CommissionModel(flat_fee=1.0, percentage=0.001)
        assert model.calculate(10000) == pytest.approx(11.0)

    def test_min_commission(self):
        model = CommissionModel(percentage=0.0001, min_commission=1.0)
        # 0.0001 * 100 = 0.01, but min is 1.0
        assert model.calculate(100) == pytest.approx(1.0)

    def test_zero_commission(self):
        model = CommissionModel(flat_fee=0, percentage=0, min_commission=0)
        assert model.calculate(10000) == pytest.approx(0.0)


class TestBacktestEngine:
    def test_basic_backtest_returns_summary(
        self, sample_ohlcv, simple_signals
    ):
        entries, exits = simple_signals
        engine = BacktestEngine()
        result = engine.run(
            sample_ohlcv, entries, exits, strategy_name="test"
        )

        assert isinstance(result, BacktestSummary)
        assert result.strategy_name == "test"
        assert result.number_of_trades == 2
        assert result.initial_capital == 10000.0
        assert result.backtest_id is not None
        assert result.created_at is not None

    def test_custom_initial_capital(self, sample_ohlcv, simple_signals):
        entries, exits = simple_signals
        config = BacktestConfig(initial_capital=50000.0)
        engine = BacktestEngine(config)
        result = engine.run(sample_ohlcv, entries, exits)

        assert result.initial_capital == 50000.0

    def test_commission_reduces_returns(self, sample_ohlcv, simple_signals):
        entries, exits = simple_signals

        # No commission
        config_no_comm = BacktestConfig(
            commission=CommissionModel(
                flat_fee=0, percentage=0, min_commission=0
            )
        )
        result_no_comm = BacktestEngine(config_no_comm).run(
            sample_ohlcv, entries, exits
        )

        # High commission
        config_high_comm = BacktestConfig(
            commission=CommissionModel(percentage=0.01)  # 1%
        )
        result_high_comm = BacktestEngine(config_high_comm).run(
            sample_ohlcv, entries, exits
        )

        assert result_high_comm.total_commission > 0
        assert result_high_comm.final_capital < result_no_comm.final_capital

    def test_no_signals_no_trades(self, sample_ohlcv):
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)

        engine = BacktestEngine()
        result = engine.run(sample_ohlcv, entries, exits)

        assert result.number_of_trades == 0
        assert result.final_capital == result.initial_capital
        assert result.total_return == pytest.approx(0.0)

    def test_open_position_closed_at_end(self, sample_ohlcv):
        """An open position at the end of data should be force-closed."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)
        entries.iloc[10] = True  # Enter but never exit

        engine = BacktestEngine()
        result = engine.run(sample_ohlcv, entries, exits)

        assert result.number_of_trades == 1
        # The trade should have been closed at the last bar
        trade = result.trades[0]
        assert trade["exit_price"] == pytest.approx(
            sample_ohlcv["close"].iloc[-1]
        )

    def test_date_range_filtering(self, sample_ohlcv):
        """Only data within the configured date range should be used."""
        config = BacktestConfig(
            start_date="2020-01-01 00:30:00",
            end_date="2020-01-01 03:00:00",
        )
        engine = BacktestEngine(config)

        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)

        result = engine.run(sample_ohlcv, entries, exits)

        # Should have used only a subset of data
        assert result.start_date >= "2020-01-01 00:30:00"
        assert result.end_date <= "2020-01-01 03:00:00"

    def test_equity_curve_length(self, sample_ohlcv, simple_signals):
        entries, exits = simple_signals
        engine = BacktestEngine()
        result = engine.run(sample_ohlcv, entries, exits)

        assert len(result.equity_curve) == len(sample_ohlcv)

    def test_trade_pnl_consistency(self, sample_ohlcv, simple_signals):
        """Sum of trade PnLs should approximately equal total PnL."""
        entries, exits = simple_signals
        config = BacktestConfig(
            commission=CommissionModel(
                flat_fee=0, percentage=0, min_commission=0
            )
        )
        engine = BacktestEngine(config)
        result = engine.run(sample_ohlcv, entries, exits)

        total_trade_pnl = sum(t["pnl"] for t in result.trades)
        total_pnl = result.final_capital - result.initial_capital
        assert total_trade_pnl == pytest.approx(total_pnl, abs=0.01)

    def test_win_rate_calculation(self, sample_ohlcv):
        """With known winning and losing trades, verify win rate."""
        n = len(sample_ohlcv)
        entries = pd.Series([False] * n, index=sample_ohlcv.index)
        exits = pd.Series([False] * n, index=sample_ohlcv.index)

        # Create multiple trades
        entries.iloc[10] = True
        exits.iloc[50] = True
        entries.iloc[100] = True
        exits.iloc[150] = True
        entries.iloc[200] = True
        exits.iloc[250] = True

        config = BacktestConfig(
            commission=CommissionModel(
                flat_fee=0, percentage=0, min_commission=0
            )
        )
        engine = BacktestEngine(config)
        result = engine.run(sample_ohlcv, entries, exits)

        assert result.number_of_trades == 3
        assert 0 <= result.win_rate <= 1.0

    def test_max_drawdown_range(self, sample_ohlcv, simple_signals):
        entries, exits = simple_signals
        engine = BacktestEngine()
        result = engine.run(sample_ohlcv, entries, exits)

        assert 0 <= result.max_drawdown <= 1.0
        assert result.max_drawdown_duration_bars >= 0

    def test_sharpe_ratio_computed(self, sample_ohlcv, simple_signals):
        entries, exits = simple_signals
        engine = BacktestEngine()
        result = engine.run(sample_ohlcv, entries, exits)

        # Should be a finite number
        assert np.isfinite(result.sharpe_ratio)

    def test_avg_holding_period(self, sample_ohlcv, simple_signals):
        entries, exits = simple_signals
        engine = BacktestEngine()
        result = engine.run(sample_ohlcv, entries, exits)

        # First trade: bar 10 to 50 = 40 bars
        # Second trade: bar 100 to 150 = 50 bars
        # Average = 45
        assert result.avg_holding_period_bars == pytest.approx(45.0)

    def test_position_size_pct(self, sample_ohlcv, simple_signals):
        """Using half position size should use less capital per trade."""
        entries, exits = simple_signals

        full_result = BacktestEngine(
            BacktestConfig(position_size_pct=1.0)
        ).run(sample_ohlcv, entries, exits)
        half_result = BacktestEngine(
            BacktestConfig(position_size_pct=0.5)
        ).run(sample_ohlcv, entries, exits)

        # Half-size trades should have smaller absolute PnL
        full_pnl = abs(full_result.trades[0]["pnl"])
        half_pnl = abs(half_result.trades[0]["pnl"])
        assert half_pnl < full_pnl

    def test_summary_to_dict(self, sample_ohlcv, simple_signals):
        entries, exits = simple_signals
        engine = BacktestEngine()
        result = engine.run(sample_ohlcv, entries, exits)

        d = result.to_dict()
        assert isinstance(d, dict)
        assert "backtest_id" in d
        assert "total_return" in d
        assert "trades" in d
        assert "equity_curve" in d

    def test_strategy_params_in_config(self, sample_ohlcv, simple_signals):
        entries, exits = simple_signals
        engine = BacktestEngine()
        params = {"fast_period": 10, "slow_period": 20}
        result = engine.run(
            sample_ohlcv,
            entries,
            exits,
            strategy_name="ema_cross",
            strategy_params=params,
        )

        assert result.config["fast_period"] == 10
        assert result.config["slow_period"] == 20


class TestBacktestEngineEdgeCases:
    def test_single_bar(self):
        """Engine handles single-bar data gracefully."""
        df = pd.DataFrame(
            {
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.0],
                "volume": [1000.0],
            }
        )
        df.index = pd.date_range(start="2020-01-01", periods=1, freq="1min")

        entries = pd.Series([True], index=df.index)
        exits = pd.Series([False], index=df.index)

        engine = BacktestEngine()
        result = engine.run(df, entries, exits)

        assert result.number_of_trades == 1

    def test_empty_data_after_filter(self):
        """If date range filters out all data, handle gracefully."""
        df = pd.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [1000.0, 1100.0],
            }
        )
        df.index = pd.date_range(start="2020-01-01", periods=2, freq="1min")

        config = BacktestConfig(
            start_date="2025-01-01"
        )  # No data in range
        engine = BacktestEngine(config)

        entries = pd.Series([True, False], index=df.index)
        exits = pd.Series([False, True], index=df.index)

        result = engine.run(df, entries, exits)
        assert result.number_of_trades == 0

    def test_rapid_entry_exit(self):
        """Entry and exit on adjacent bars."""
        n = 10
        close = np.linspace(100, 110, n)
        df = pd.DataFrame(
            {
                "open": close - 0.5,
                "high": close + 0.5,
                "low": close - 1.0,
                "close": close,
                "volume": np.ones(n) * 1000,
            }
        )
        df.index = pd.date_range(start="2020-01-01", periods=n, freq="1min")

        entries = pd.Series([False] * n, index=df.index)
        exits = pd.Series([False] * n, index=df.index)
        entries.iloc[2] = True
        exits.iloc[3] = True

        config = BacktestConfig(
            commission=CommissionModel(
                flat_fee=0, percentage=0, min_commission=0
            )
        )
        engine = BacktestEngine(config)
        result = engine.run(df, entries, exits)

        assert result.number_of_trades == 1
        assert result.trades[0]["holding_period_bars"] == 1


class TestMaxDrawdown:
    def test_no_drawdown_in_rising_equity(self):
        equity = np.array([100, 101, 102, 103, 104, 105])
        dd, duration = BacktestEngine._calc_max_drawdown(equity)
        assert dd == pytest.approx(0.0)
        assert duration == 0

    def test_known_drawdown(self):
        # Peak at 200, drops to 160 = 20% drawdown
        equity = np.array([100, 150, 200, 180, 160, 190, 210])
        dd, duration = BacktestEngine._calc_max_drawdown(equity)
        assert dd == pytest.approx(0.2)
        assert duration == 3  # bars 2->3->4->5 in drawdown

    def test_single_element(self):
        dd, duration = BacktestEngine._calc_max_drawdown(np.array([100]))
        assert dd == pytest.approx(0.0)
        assert duration == 0


class TestSharpeRatio:
    def test_zero_std_returns_zero(self):
        returns = np.zeros(100)
        assert BacktestEngine._calc_sharpe(returns, 252) == pytest.approx(0.0)

    def test_positive_returns_positive_sharpe(self):
        np.random.seed(42)
        returns = np.random.randn(1000) * 0.01 + 0.001  # positive drift
        sharpe = BacktestEngine._calc_sharpe(returns, 252)
        assert sharpe > 0

    def test_negative_returns_negative_sharpe(self):
        np.random.seed(42)
        returns = (
            np.random.randn(1000) * 0.01 - 0.01
        )  # strong negative drift
        sharpe = BacktestEngine._calc_sharpe(returns, 252)
        assert sharpe < 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
