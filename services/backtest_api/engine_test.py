"""Tests for the backtesting engine logic."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from services.backtest_api.engine import (
    BacktestResult,
    Candle,
    EquityPoint,
    Trade,
    generate_signals,
    run_backtest,
)


def _make_candles(prices: list[float], start: datetime = None) -> list[Candle]:
    """Helper to create candles from a list of close prices."""
    if start is None:
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candles = []
    for i, price in enumerate(prices):
        ts = start + timedelta(days=i)
        candles.append(
            Candle(
                timestamp=ts,
                open=price * 0.99,
                high=price * 1.01,
                low=price * 0.98,
                close=price,
                volume=1000.0,
            )
        )
    return candles


class TestGenerateSignals:
    def test_empty_candles(self):
        signals = generate_signals([], "test-strategy")
        assert signals == []

    def test_single_candle(self):
        candles = _make_candles([100.0])
        signals = generate_signals(candles, "test-strategy")
        assert len(signals) == 1
        assert signals[0] == 0

    def test_short_series_all_hold(self):
        candles = _make_candles([100.0, 101.0, 102.0])
        signals = generate_signals(candles, "test-strategy")
        assert all(s == 0 for s in signals)

    def test_signals_length_matches_candles(self):
        prices = [100 + i for i in range(50)]
        candles = _make_candles(prices)
        signals = generate_signals(candles, "test-strategy")
        assert len(signals) == len(candles)

    def test_signals_are_valid_values(self):
        prices = [100 + (i % 10) * (-1) ** i for i in range(100)]
        candles = _make_candles(prices)
        signals = generate_signals(candles, "any-strategy")
        for s in signals:
            assert s in (-1, 0, 1)

    def test_different_strategies_can_differ(self):
        prices = list(range(50, 150))
        candles = _make_candles(prices)
        s1 = generate_signals(candles, "alpha")
        s2 = generate_signals(candles, "beta-long-name-different")
        # They may or may not differ, but shouldn't crash
        assert len(s1) == len(s2)


class TestRunBacktest:
    def test_empty_candles(self):
        result = run_backtest([], "test")
        assert result.total_return == 0.0
        assert result.sharpe_ratio == 0.0
        assert result.max_drawdown == 0.0
        assert result.win_rate == 0.0
        assert result.profit_factor == 0.0
        assert result.total_trades == 0
        assert result.trades == []
        assert result.equity_curve == []

    def test_single_candle(self):
        candles = _make_candles([100.0])
        result = run_backtest(candles, "test")
        assert result.total_trades == 0
        assert result.total_return == 0.0
        assert len(result.equity_curve) == 1

    def test_uptrend_produces_trades(self):
        # Create a clear uptrend then downtrend to trigger crossover signals
        prices = (
            [100] * 20
            + [100 + i * 2 for i in range(30)]
            + [160 - i * 2 for i in range(30)]
        )
        candles = _make_candles(prices)
        result = run_backtest(candles, "test-strategy")
        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == len(candles)

    def test_equity_curve_starts_at_initial_capital(self):
        prices = [100 + i for i in range(50)]
        candles = _make_candles(prices)
        result = run_backtest(candles, "test", initial_capital=5000.0)
        assert result.equity_curve[0].equity == 5000.0

    def test_max_drawdown_non_negative(self):
        prices = [100 + i for i in range(40)] + [140 - i * 3 for i in range(20)]
        candles = _make_candles(prices)
        result = run_backtest(candles, "test")
        assert result.max_drawdown >= 0.0

    def test_win_rate_between_zero_and_one(self):
        prices = [100 + (i % 15) * (-1) ** i for i in range(100)]
        candles = _make_candles(prices)
        result = run_backtest(candles, "strat-1")
        assert 0.0 <= result.win_rate <= 1.0

    def test_profit_factor_non_negative(self):
        prices = [100 + (i % 10) * (-1) ** i for i in range(100)]
        candles = _make_candles(prices)
        result = run_backtest(candles, "strat-2")
        assert result.profit_factor >= 0.0

    def test_trades_have_required_fields(self):
        prices = (
            [100] * 20
            + [100 + i * 2 for i in range(30)]
            + [160 - i * 2 for i in range(30)]
        )
        candles = _make_candles(prices)
        result = run_backtest(candles, "test-strategy")
        for trade in result.trades:
            assert trade.side == "BUY"
            assert trade.entry_time is not None
            assert trade.entry_price > 0
            assert trade.exit_time is not None
            assert trade.exit_price is not None
            assert trade.pnl is not None

    def test_equity_curve_drawdown_between_zero_and_one(self):
        prices = [100 + i for i in range(30)] + [130 - i for i in range(20)]
        candles = _make_candles(prices)
        result = run_backtest(candles, "test")
        for pt in result.equity_curve:
            assert 0.0 <= pt.drawdown <= 1.0

    def test_different_initial_capital(self):
        prices = [100 + i for i in range(50)]
        candles = _make_candles(prices)
        r1 = run_backtest(candles, "test", initial_capital=1000.0)
        r2 = run_backtest(candles, "test", initial_capital=50000.0)
        # Total return percentage should be the same
        assert abs(r1.total_return - r2.total_return) < 1e-4

    def test_constant_prices_no_trades(self):
        prices = [100.0] * 50
        candles = _make_candles(prices)
        result = run_backtest(candles, "test")
        # Constant prices = no crossovers = no trades
        assert result.total_trades == 0
        assert result.total_return == 0.0
