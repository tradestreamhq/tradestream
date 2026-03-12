"""Tests for core attribution calculation functions."""

from datetime import datetime, timezone

import pytest

from services.performance_attribution.attribution import (
    compute_daily_returns,
    compute_max_drawdown,
    compute_sharpe_ratio,
    compute_win_rate,
)


class TestComputeWinRate:
    def test_empty(self):
        assert compute_win_rate([]) is None

    def test_all_winners(self):
        assert compute_win_rate([100, 50, 25]) == 1.0

    def test_all_losers(self):
        assert compute_win_rate([-10, -20, -30]) == 0.0

    def test_mixed(self):
        assert compute_win_rate([100, -50, 25, -10]) == 0.5

    def test_zero_is_not_win(self):
        assert compute_win_rate([0, 0, 100]) == pytest.approx(0.3333, abs=0.001)


class TestComputeMaxDrawdown:
    def test_empty(self):
        assert compute_max_drawdown([]) is None

    def test_no_drawdown(self):
        assert compute_max_drawdown([10, 20, 30]) == 0.0

    def test_simple_drawdown(self):
        # cumulative: 100, 50, 80 -> peak=100, dd at step2 = 50-100=-50
        assert compute_max_drawdown([100, -50, 30]) == -50

    def test_full_drawdown(self):
        assert compute_max_drawdown([100, -150]) == -50

    def test_multiple_drawdowns(self):
        # cumulative: 10, -10, 90, -10
        # peaks: 10, 10, 90, 90
        # drawdowns: 0, -20, 0, -100
        pnls = [10, -20, 100, -100]
        assert compute_max_drawdown(pnls) == -100


class TestComputeDailyReturns:
    def test_empty(self):
        assert compute_daily_returns([]) == []

    def test_single_trade(self):
        trades = [
            {"pnl": 100, "closed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        ]
        result = compute_daily_returns(trades)
        assert result == [100.0]

    def test_aggregates_same_day(self):
        trades = [
            {"pnl": 50, "closed_at": datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)},
            {"pnl": 30, "closed_at": datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc)},
        ]
        result = compute_daily_returns(trades)
        assert result == [80.0]

    def test_multiple_days_sorted(self):
        trades = [
            {"pnl": 10, "closed_at": datetime(2026, 1, 3, tzinfo=timezone.utc)},
            {"pnl": 20, "closed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        ]
        result = compute_daily_returns(trades)
        assert result == [20.0, 10.0]

    def test_skips_none_closed_at(self):
        trades = [
            {"pnl": 100, "closed_at": None},
            {"pnl": 50, "closed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)},
        ]
        result = compute_daily_returns(trades)
        assert result == [50.0]


class TestComputeSharpeRatio:
    def test_empty(self):
        assert compute_sharpe_ratio([]) is None

    def test_single_return(self):
        assert compute_sharpe_ratio([100]) is None

    def test_zero_std(self):
        assert compute_sharpe_ratio([10, 10, 10]) is None

    def test_positive_sharpe(self):
        # All positive returns -> positive Sharpe
        result = compute_sharpe_ratio([100, 200, 150, 300])
        assert result is not None
        assert result > 0

    def test_negative_sharpe(self):
        # All negative returns -> negative Sharpe
        result = compute_sharpe_ratio([-100, -200, -150, -300])
        assert result is not None
        assert result < 0

    def test_with_risk_free_rate(self):
        returns = [10, 20, 15, 25]
        sharpe_no_rf = compute_sharpe_ratio(returns, risk_free_rate=0.0)
        sharpe_with_rf = compute_sharpe_ratio(returns, risk_free_rate=5.0)
        assert sharpe_no_rf is not None
        assert sharpe_with_rf is not None
        assert sharpe_with_rf < sharpe_no_rf
