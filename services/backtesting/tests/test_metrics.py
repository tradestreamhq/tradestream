"""Tests for backtesting performance metrics."""

import math

import pytest

from services.backtesting.metrics import (
    PerformanceMetrics,
    Trade,
    calculate_metrics,
    _max_drawdown,
    _profit_factor,
    _sharpe_ratio,
    _total_return,
)


@pytest.fixture
def winning_trades():
    """Create a list of winning trades."""
    return [
        Trade(entry_price=100, exit_price=110, entry_index=0, exit_index=10, symbol="BTC/USD"),
        Trade(entry_price=110, exit_price=120, entry_index=20, exit_index=30, symbol="BTC/USD"),
        Trade(entry_price=120, exit_price=135, entry_index=40, exit_index=55, symbol="BTC/USD"),
    ]


@pytest.fixture
def mixed_trades():
    """Create a list of mixed winning/losing trades."""
    return [
        Trade(entry_price=100, exit_price=110, entry_index=0, exit_index=10, symbol="BTC/USD"),
        Trade(entry_price=110, exit_price=105, entry_index=20, exit_index=25, symbol="BTC/USD"),
        Trade(entry_price=105, exit_price=115, entry_index=30, exit_index=40, symbol="BTC/USD"),
        Trade(entry_price=115, exit_price=108, entry_index=50, exit_index=55, symbol="BTC/USD"),
        Trade(entry_price=108, exit_price=120, entry_index=60, exit_index=75, symbol="BTC/USD"),
    ]


@pytest.fixture
def multi_symbol_trades():
    """Trades across multiple symbols."""
    return [
        Trade(entry_price=100, exit_price=110, entry_index=0, exit_index=10, symbol="BTC/USD"),
        Trade(entry_price=50, exit_price=55, entry_index=0, exit_index=10, symbol="ETH/USD"),
        Trade(entry_price=110, exit_price=105, entry_index=20, exit_index=30, symbol="BTC/USD"),
    ]


class TestTrade:
    def test_long_trade_pnl(self):
        t = Trade(entry_price=100, exit_price=110, entry_index=0, exit_index=5, symbol="X")
        assert t.pnl == 10
        assert t.return_pct == pytest.approx(0.1)
        assert t.is_winner is True
        assert t.duration == 5

    def test_losing_trade(self):
        t = Trade(entry_price=100, exit_price=95, entry_index=0, exit_index=3, symbol="X")
        assert t.pnl == -5
        assert t.return_pct == pytest.approx(-0.05)
        assert t.is_winner is False

    def test_short_trade_pnl(self):
        t = Trade(
            entry_price=100, exit_price=90, entry_index=0, exit_index=5,
            symbol="X", direction="short",
        )
        assert t.pnl == 10
        assert t.is_winner is True

    def test_zero_entry_price(self):
        t = Trade(entry_price=0, exit_price=10, entry_index=0, exit_index=1, symbol="X")
        assert t.return_pct == 0.0


class TestTotalReturn:
    def test_positive_returns(self):
        returns = [0.10, 0.05, 0.08]
        result = _total_return(returns)
        expected = (1.10 * 1.05 * 1.08) - 1
        assert result == pytest.approx(expected)

    def test_negative_returns(self):
        returns = [-0.05, -0.10]
        result = _total_return(returns)
        expected = (0.95 * 0.90) - 1
        assert result == pytest.approx(expected)

    def test_empty_returns(self):
        assert _total_return([]) == 0.0

    def test_zero_return(self):
        assert _total_return([0.0, 0.0]) == pytest.approx(0.0)


class TestSharpeRatio:
    def test_positive_sharpe(self):
        returns = [0.01, 0.02, 0.015, 0.01, 0.025, 0.005, 0.02, 0.01]
        sharpe = _sharpe_ratio(returns, risk_free_rate=0.02, periods_per_year=252)
        assert sharpe > 0

    def test_zero_variance(self):
        returns = [0.01, 0.01, 0.01]
        sharpe = _sharpe_ratio(returns, risk_free_rate=0.02, periods_per_year=252)
        assert sharpe == 0.0

    def test_single_return(self):
        assert _sharpe_ratio([0.05], risk_free_rate=0.02, periods_per_year=252) == 0.0

    def test_empty_returns(self):
        assert _sharpe_ratio([], risk_free_rate=0.02, periods_per_year=252) == 0.0


class TestMaxDrawdown:
    def test_no_drawdown(self):
        returns = [0.01, 0.02, 0.03]
        assert _max_drawdown(returns) == pytest.approx(0.0)

    def test_simple_drawdown(self):
        returns = [0.10, -0.20, 0.05]
        dd = _max_drawdown(returns)
        # Peak at 1.10, then drops to 1.10 * 0.80 = 0.88
        # DD = (1.10 - 0.88) / 1.10 = 0.2
        assert dd == pytest.approx(0.2)

    def test_empty_returns(self):
        assert _max_drawdown([]) == 0.0


class TestProfitFactor:
    def test_all_winners(self, winning_trades):
        pf = _profit_factor(winning_trades)
        assert pf == float("inf")

    def test_all_losers(self):
        losers = [
            Trade(entry_price=100, exit_price=95, entry_index=0, exit_index=5, symbol="X"),
            Trade(entry_price=95, exit_price=90, entry_index=10, exit_index=15, symbol="X"),
        ]
        assert _profit_factor(losers) == 0.0

    def test_mixed_trades(self, mixed_trades):
        pf = _profit_factor(mixed_trades)
        assert pf > 0


class TestCalculateMetrics:
    def test_empty_trades(self):
        result = calculate_metrics([])
        assert isinstance(result, PerformanceMetrics)
        assert result.total_trades == 0
        assert result.total_return == 0.0

    def test_winning_trades(self, winning_trades):
        result = calculate_metrics(winning_trades)
        assert result.total_return > 0
        assert result.win_rate == 1.0
        assert result.winning_trades == 3
        assert result.losing_trades == 0
        assert result.total_trades == 3
        assert result.profit_factor == float("inf")
        assert result.max_consecutive_wins == 3
        assert result.max_consecutive_losses == 0

    def test_mixed_trades(self, mixed_trades):
        result = calculate_metrics(mixed_trades)
        assert result.total_trades == 5
        assert result.winning_trades == 3
        assert result.losing_trades == 2
        assert 0 < result.win_rate < 1
        assert result.max_drawdown >= 0
        assert result.profit_factor > 0
        assert result.avg_trade_duration > 0

    def test_multi_symbol(self, multi_symbol_trades):
        result = calculate_metrics(multi_symbol_trades)
        assert set(result.symbols) == {"BTC/USD", "ETH/USD"}
        assert result.total_trades == 3

    def test_consecutive_streaks(self):
        trades = [
            Trade(entry_price=100, exit_price=110, entry_index=0, exit_index=5, symbol="X"),
            Trade(entry_price=110, exit_price=120, entry_index=10, exit_index=15, symbol="X"),
            Trade(entry_price=120, exit_price=130, entry_index=20, exit_index=25, symbol="X"),
            Trade(entry_price=130, exit_price=125, entry_index=30, exit_index=35, symbol="X"),
            Trade(entry_price=125, exit_price=120, entry_index=40, exit_index=45, symbol="X"),
        ]
        result = calculate_metrics(trades)
        assert result.max_consecutive_wins == 3
        assert result.max_consecutive_losses == 2
