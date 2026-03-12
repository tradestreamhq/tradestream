"""Tests for the rebalancing scheduler."""

import time
from unittest.mock import patch

import pytest

from services.portfolio_rebalancing.scheduler import (
    RebalanceFrequency,
    RebalanceSchedule,
    FREQUENCY_SECONDS,
)


class TestRebalanceSchedule:
    def test_is_due_initially(self):
        schedule = RebalanceSchedule(RebalanceFrequency.DAILY)
        assert schedule.is_due() is True

    def test_not_due_after_mark_run(self):
        schedule = RebalanceSchedule(RebalanceFrequency.DAILY)
        schedule.mark_run()
        assert schedule.is_due() is False

    def test_due_after_interval_elapses(self):
        schedule = RebalanceSchedule(RebalanceFrequency.HOURLY)
        schedule.last_run_time = time.time() - 3601
        assert schedule.is_due() is True

    def test_seconds_until_next_initially_zero(self):
        schedule = RebalanceSchedule(RebalanceFrequency.DAILY)
        assert schedule.seconds_until_next() == 0.0

    def test_seconds_until_next_after_run(self):
        schedule = RebalanceSchedule(RebalanceFrequency.HOURLY)
        schedule.mark_run()
        remaining = schedule.seconds_until_next()
        assert 3590 < remaining <= 3600

    def test_frequency_intervals(self):
        assert FREQUENCY_SECONDS[RebalanceFrequency.HOURLY] == 3600
        assert FREQUENCY_SECONDS[RebalanceFrequency.DAILY] == 86400
        assert FREQUENCY_SECONDS[RebalanceFrequency.WEEKLY] == 604800

    def test_weekly_schedule(self):
        schedule = RebalanceSchedule(RebalanceFrequency.WEEKLY)
        assert schedule.interval_seconds == 604800
        schedule.last_run_time = time.time() - 604801
        assert schedule.is_due() is True
