"""Tests for the strategy time filter service."""

from unittest import mock

import pytest

from absl import flags

from services.strategy_time_filter.main import StrategyTimeFilter

FLAGS = flags.FLAGS


@pytest.fixture(autouse=True)
def _reset_flags():
    """Ensure flag defaults for each test."""
    saved = {
        "max_strategy_age_days": FLAGS.max_strategy_age_days,
        "min_backtest_window_days": FLAGS.min_backtest_window_days,
        "max_backtest_window_days": FLAGS.max_backtest_window_days,
        "time_decay_factor": FLAGS.time_decay_factor,
        "require_recent_discovery": FLAGS.require_recent_discovery,
    }
    yield
    for k, v in saved.items():
        FLAGS[k].value = v


def _make_filter():
    f = StrategyTimeFilter.__new__(StrategyTimeFilter)
    f.db_config = {}
    f.pool = None
    return f


class TestApplyTimeFilters:
    def setup_method(self):
        self.tf = _make_filter()

    def test_recent_strategy_passes(self):
        result = self.tf._apply_time_filters(
            days_since_discovery=10.0,
            backtest_window_days=60.0,
            current_score=0.9,
        )
        assert result["is_valid"] is True
        assert result["is_recent"] is True
        assert result["is_valid_window"] is True

    def test_old_strategy_rejected_when_require_recent(self):
        FLAGS.require_recent_discovery = True
        FLAGS.max_strategy_age_days = 90
        result = self.tf._apply_time_filters(
            days_since_discovery=100.0,
            backtest_window_days=60.0,
            current_score=0.9,
        )
        assert result["is_valid"] is False
        assert result["is_recent"] is False

    def test_old_strategy_allowed_when_not_require_recent(self):
        FLAGS.require_recent_discovery = False
        FLAGS.max_strategy_age_days = 90
        result = self.tf._apply_time_filters(
            days_since_discovery=100.0,
            backtest_window_days=60.0,
            current_score=0.9,
        )
        assert result["is_valid"] is True

    def test_backtest_window_too_short(self):
        FLAGS.min_backtest_window_days = 30
        result = self.tf._apply_time_filters(
            days_since_discovery=10.0,
            backtest_window_days=15.0,
            current_score=0.9,
        )
        assert result["is_valid"] is False
        assert result["is_valid_window"] is False

    def test_backtest_window_too_long(self):
        FLAGS.max_backtest_window_days = 365
        result = self.tf._apply_time_filters(
            days_since_discovery=10.0,
            backtest_window_days=400.0,
            current_score=0.9,
        )
        assert result["is_valid"] is False
        assert result["is_valid_window"] is False

    def test_null_backtest_window_is_valid(self):
        result = self.tf._apply_time_filters(
            days_since_discovery=10.0,
            backtest_window_days=None,
            current_score=0.9,
        )
        assert result["is_valid_window"] is True

    def test_time_decay_calculation(self):
        FLAGS.time_decay_factor = 0.1
        result = self.tf._apply_time_filters(
            days_since_discovery=60.0,  # 2 months
            backtest_window_days=60.0,
            current_score=0.9,
        )
        # decay = (60/30) * 0.1 = 0.2
        # adjusted = 0.9 - 0.2 = 0.7
        assert result["adjusted_score"] == pytest.approx(0.7)

    def test_time_decay_floors_at_zero(self):
        FLAGS.time_decay_factor = 0.5
        result = self.tf._apply_time_filters(
            days_since_discovery=300.0,  # 10 months
            backtest_window_days=60.0,
            current_score=0.5,
        )
        # decay = (300/30) * 0.5 = 5.0, score would be -4.5
        assert result["adjusted_score"] == 0.0

    def test_zero_days_no_decay(self):
        result = self.tf._apply_time_filters(
            days_since_discovery=0.0,
            backtest_window_days=60.0,
            current_score=0.9,
        )
        assert result["adjusted_score"] == pytest.approx(0.9)
        assert result["time_decay"] == pytest.approx(0.0)

    def test_boundary_max_age(self):
        FLAGS.max_strategy_age_days = 90
        result = self.tf._apply_time_filters(
            days_since_discovery=90.0,
            backtest_window_days=60.0,
            current_score=0.9,
        )
        assert result["is_recent"] is True  # exactly at boundary

    def test_boundary_min_backtest(self):
        FLAGS.min_backtest_window_days = 30
        result = self.tf._apply_time_filters(
            days_since_discovery=10.0,
            backtest_window_days=30.0,
            current_score=0.9,
        )
        assert result["is_valid_window"] is True  # exactly at boundary
