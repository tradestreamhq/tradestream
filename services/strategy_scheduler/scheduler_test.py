"""Tests for the Strategy Scheduler logic."""

from datetime import datetime, timezone

import pytest

from services.strategy_scheduler.models import MarketPhase
from services.strategy_scheduler.scheduler import (
    cron_matches,
    current_market_phase,
    is_in_active_hours,
    should_strategy_run,
    validate_cron,
)


class TestCurrentMarketPhase:
    def test_pre_market(self):
        dt = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)
        assert current_market_phase(dt) == MarketPhase.PRE_MARKET

    def test_regular(self):
        dt = datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)
        assert current_market_phase(dt) == MarketPhase.REGULAR

    def test_post_market(self):
        dt = datetime(2026, 3, 10, 22, 0, tzinfo=timezone.utc)
        assert current_market_phase(dt) == MarketPhase.POST_MARKET

    def test_closed(self):
        dt = datetime(2026, 3, 10, 5, 0, tzinfo=timezone.utc)
        assert current_market_phase(dt) == MarketPhase.CLOSED


class TestIsInActiveHours:
    def test_no_bounds(self):
        now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
        assert is_in_active_hours(now, None, None) is True

    def test_within_window(self):
        now = datetime(2026, 3, 10, 15, 30, tzinfo=timezone.utc)
        assert is_in_active_hours(now, "14:00", "20:00") is True

    def test_outside_window(self):
        now = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)
        assert is_in_active_hours(now, "14:00", "20:00") is False

    def test_overnight_window_in(self):
        now = datetime(2026, 3, 10, 23, 0, tzinfo=timezone.utc)
        assert is_in_active_hours(now, "22:00", "06:00") is True

    def test_overnight_window_out(self):
        now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
        assert is_in_active_hours(now, "22:00", "06:00") is False


class TestValidateCron:
    def test_valid(self):
        assert validate_cron("*/5 * * * *") is True
        assert validate_cron("0 14 * * 1-5") is True

    def test_invalid(self):
        assert validate_cron("not a cron") is False
        assert validate_cron("* * *") is False


class TestCronMatches:
    def test_every_minute(self):
        dt = datetime(2026, 3, 10, 15, 30, tzinfo=timezone.utc)
        assert cron_matches("* * * * *", dt) is True

    def test_specific_minute(self):
        dt = datetime(2026, 3, 10, 15, 30, tzinfo=timezone.utc)
        assert cron_matches("30 * * * *", dt) is True
        assert cron_matches("15 * * * *", dt) is False

    def test_step(self):
        dt = datetime(2026, 3, 10, 15, 30, tzinfo=timezone.utc)
        assert cron_matches("*/5 * * * *", dt) is True
        dt2 = datetime(2026, 3, 10, 15, 31, tzinfo=timezone.utc)
        assert cron_matches("*/5 * * * *", dt2) is False

    def test_range(self):
        # 2026-03-10 is a Tuesday (weekday=1)
        dt = datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc)
        assert cron_matches("0 14 * * 0-4", dt) is True  # Mon-Fri
        assert cron_matches("0 14 * * 5-6", dt) is False  # Sat-Sun

    def test_weekday_match(self):
        # Wednesday = weekday 2
        dt = datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc)
        assert cron_matches("0 9 * * 2", dt) is True

    def test_comma_list(self):
        dt = datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)
        assert cron_matches("0,30 * * * *", dt) is True


class TestShouldStrategyRun:
    def test_disabled(self):
        dt = datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)
        run, phase, in_hours, cron_ok = should_strategy_run(
            enabled=False,
            market_phases=[MarketPhase.REGULAR],
            active_hours_start=None,
            active_hours_end=None,
            cron_expression=None,
            now=dt,
        )
        assert run is False

    def test_regular_hours_match(self):
        dt = datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)
        run, phase, in_hours, cron_ok = should_strategy_run(
            enabled=True,
            market_phases=[MarketPhase.REGULAR],
            active_hours_start="14:00",
            active_hours_end="20:00",
            cron_expression=None,
            now=dt,
        )
        assert run is True
        assert phase == MarketPhase.REGULAR
        assert in_hours is True
        assert cron_ok is True

    def test_wrong_phase(self):
        dt = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)  # pre-market
        run, phase, in_hours, cron_ok = should_strategy_run(
            enabled=True,
            market_phases=[MarketPhase.REGULAR],
            active_hours_start=None,
            active_hours_end=None,
            cron_expression=None,
            now=dt,
        )
        assert run is False
        assert phase == MarketPhase.PRE_MARKET

    def test_cron_mismatch(self):
        dt = datetime(2026, 3, 10, 15, 1, tzinfo=timezone.utc)
        run, phase, in_hours, cron_ok = should_strategy_run(
            enabled=True,
            market_phases=[MarketPhase.REGULAR],
            active_hours_start=None,
            active_hours_end=None,
            cron_expression="0 * * * *",  # only at minute 0
            now=dt,
        )
        assert run is False
        assert cron_ok is False

    def test_all_phases(self):
        dt = datetime(2026, 3, 10, 5, 0, tzinfo=timezone.utc)  # closed
        run, _, _, _ = should_strategy_run(
            enabled=True,
            market_phases=[
                MarketPhase.PRE_MARKET,
                MarketPhase.REGULAR,
                MarketPhase.POST_MARKET,
            ],
            active_hours_start=None,
            active_hours_end=None,
            cron_expression=None,
            now=dt,
        )
        assert run is False  # CLOSED phase not included
