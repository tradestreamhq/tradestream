"""Tests for scheduler."""

import time
from unittest import mock

from services.orchestrator_agent.scheduler import AgentSchedule, Scheduler


class TestAgentSchedule:
    def test_is_due_initially(self):
        s = AgentSchedule("test", 60)
        assert s.is_due()

    @mock.patch("time.time")
    def test_not_due_after_run(self, mock_time):
        mock_time.return_value = 1000.0
        s = AgentSchedule("test", 60)
        s.mark_run()
        mock_time.return_value = 1030.0
        assert not s.is_due()

    @mock.patch("time.time")
    def test_due_after_interval(self, mock_time):
        mock_time.return_value = 1000.0
        s = AgentSchedule("test", 60)
        s.mark_run()
        mock_time.return_value = 1060.0
        assert s.is_due()

    @mock.patch("time.time")
    def test_seconds_until_next(self, mock_time):
        mock_time.return_value = 1000.0
        s = AgentSchedule("test", 60)
        s.mark_run()
        mock_time.return_value = 1020.0
        assert s.seconds_until_next() == 40.0


class TestScheduler:
    def test_signal_generator_due_initially(self):
        s = Scheduler(signal_interval=60, strategy_proposer_interval=1800)
        assert s.should_run_signal_generator()

    def test_strategy_proposer_due_initially(self):
        s = Scheduler(signal_interval=60, strategy_proposer_interval=1800)
        assert s.should_run_strategy_proposer()

    @mock.patch("time.time")
    def test_mark_run_resets_schedule(self, mock_time):
        mock_time.return_value = 1000.0
        s = Scheduler(signal_interval=60, strategy_proposer_interval=1800)
        s.mark_signal_generator_run()
        mock_time.return_value = 1030.0
        assert not s.should_run_signal_generator()

    @mock.patch("time.time")
    def test_seconds_until_next_task(self, mock_time):
        mock_time.return_value = 1000.0
        s = Scheduler(signal_interval=60, strategy_proposer_interval=1800)
        s.mark_signal_generator_run()
        s.mark_strategy_proposer_run()
        mock_time.return_value = 1010.0
        # Signal is due in 50s, strategy in 1790s
        assert s.seconds_until_next_task() == 50.0
