"""Tests for the Strategy Performance Tracker."""

import math
from datetime import datetime, timezone
from unittest import mock

import pytest

from services.learning_engine.performance_tracker import PerformanceTracker


class TestCalculateMetrics:
    def setup_method(self):
        self.tracker = PerformanceTracker()

    def test_empty_trades(self):
        metrics = self.tracker.calculate_metrics([])
        assert metrics["trade_count"] == 0
        assert metrics["sharpe_ratio"] is None

    def test_all_winners(self):
        trades = [{"pnl_percent": 2.0}, {"pnl_percent": 3.0}, {"pnl_percent": 1.5}]
        metrics = self.tracker.calculate_metrics(trades)
        assert metrics["trade_count"] == 3
        assert metrics["win_count"] == 3
        assert metrics["win_rate"] == 1.0
        assert metrics["avg_pnl_percent"] > 0
        assert metrics["total_pnl"] == 6.5

    def test_mixed_trades(self):
        trades = [
            {"pnl_percent": 5.0},
            {"pnl_percent": -3.0},
            {"pnl_percent": 2.0},
            {"pnl_percent": -1.0},
            {"pnl_percent": 4.0},
        ]
        metrics = self.tracker.calculate_metrics(trades)
        assert metrics["trade_count"] == 5
        assert metrics["win_count"] == 3
        assert metrics["win_rate"] == 0.6
        assert metrics["total_pnl"] == 7.0
        assert metrics["sharpe_ratio"] is not None
        assert metrics["max_drawdown"] is not None

    def test_all_losers(self):
        trades = [{"pnl_percent": -2.0}, {"pnl_percent": -3.0}]
        metrics = self.tracker.calculate_metrics(trades)
        assert metrics["win_count"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["total_pnl"] < 0

    def test_trades_with_none_pnl(self):
        trades = [{"pnl_percent": 5.0}, {"pnl_percent": None}, {"pnl_percent": -2.0}]
        metrics = self.tracker.calculate_metrics(trades)
        assert metrics["trade_count"] == 2

    def test_all_none_pnl(self):
        trades = [{"pnl_percent": None}, {"other_key": "val"}]
        metrics = self.tracker.calculate_metrics(trades)
        assert metrics["trade_count"] == 2
        assert metrics["sharpe_ratio"] is None


class TestSharpeRatio:
    def setup_method(self):
        self.tracker = PerformanceTracker()

    def test_positive_sharpe(self):
        pnls = [1.0, 2.0, 1.5, 2.5, 1.0]
        sharpe = self.tracker._calculate_sharpe(pnls)
        assert sharpe is not None
        assert sharpe > 0

    def test_negative_sharpe(self):
        pnls = [-1.0, -2.0, -1.5, -2.5, -1.0]
        sharpe = self.tracker._calculate_sharpe(pnls)
        assert sharpe is not None
        assert sharpe < 0

    def test_single_trade(self):
        sharpe = self.tracker._calculate_sharpe([5.0])
        assert sharpe is None

    def test_zero_std(self):
        pnls = [2.0, 2.0, 2.0]
        sharpe = self.tracker._calculate_sharpe(pnls)
        assert sharpe is None


class TestMaxDrawdown:
    def setup_method(self):
        self.tracker = PerformanceTracker()

    def test_no_drawdown(self):
        pnls = [1.0, 2.0, 3.0]
        dd = self.tracker._calculate_max_drawdown(pnls)
        assert dd == 0.0

    def test_drawdown(self):
        pnls = [5.0, -3.0, -2.0, 4.0]
        dd = self.tracker._calculate_max_drawdown(pnls)
        assert dd < 0  # negative value indicates drawdown

    def test_empty_pnls(self):
        dd = self.tracker._calculate_max_drawdown([])
        assert dd is None

    def test_single_loss(self):
        pnls = [5.0, -10.0]
        dd = self.tracker._calculate_max_drawdown(pnls)
        assert dd < 0


class TestTrackPerformance:
    def test_track_with_db(self):
        conn = mock.Mock()
        cur = mock.Mock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        tracker = PerformanceTracker(db_connection=conn)
        trades = [{"pnl_percent": 2.0}, {"pnl_percent": -1.0}]
        now = datetime.now(timezone.utc)

        metrics = tracker.track_strategy_performance(
            strategy_spec_id="spec-1",
            regime_type="trending_up",
            instrument="BTC-USD",
            trades=trades,
            window_start=now,
            window_end=now,
        )

        assert metrics["trade_count"] == 2
        assert metrics["strategy_spec_id"] == "spec-1"
        cur.execute.assert_called_once()
        conn.commit.assert_called_once()

    def test_track_without_db(self):
        tracker = PerformanceTracker()
        trades = [{"pnl_percent": 3.0}]
        now = datetime.now(timezone.utc)

        metrics = tracker.track_strategy_performance(
            strategy_spec_id="spec-1",
            regime_type="quiet",
            instrument="ETH-USD",
            trades=trades,
            window_start=now,
            window_end=now,
        )

        assert metrics["trade_count"] == 1
        assert metrics["regime_type"] == "quiet"


class TestQueryMethods:
    def test_get_performance_no_conn(self):
        tracker = PerformanceTracker()
        assert tracker.get_strategy_performance("spec-1") == []

    def test_get_best_strategies_no_conn(self):
        tracker = PerformanceTracker()
        assert tracker.get_best_strategies_for_regime("trending_up", "BTC-USD") == []

    def test_get_heatmap_no_conn(self):
        tracker = PerformanceTracker()
        assert tracker.get_performance_heatmap("BTC-USD") == []
