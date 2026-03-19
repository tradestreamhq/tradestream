"""Tests for the janitor scheduler."""

from datetime import datetime, timedelta, timezone

import pytest

from services.janitor_agent.scheduler import (
    ScheduledTask,
    Scheduler,
    SchedulerConfig,
    TaskFrequency,
)


class TestScheduledTask:
    def test_is_due_when_never_run(self):
        task = ScheduledTask(
            name="test", frequency=TaskFrequency.DAILY, run_fn=lambda: None
        )
        assert task.is_due() is True

    def test_is_not_due_when_recently_run(self):
        task = ScheduledTask(
            name="test",
            frequency=TaskFrequency.DAILY,
            run_fn=lambda: None,
            last_run=datetime.now(timezone.utc),
        )
        assert task.is_due() is False

    def test_is_due_after_interval(self):
        task = ScheduledTask(
            name="test",
            frequency=TaskFrequency.HOURLY,
            run_fn=lambda: None,
            last_run=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        assert task.is_due() is True

    def test_disabled_task_not_due(self):
        task = ScheduledTask(
            name="test",
            frequency=TaskFrequency.DAILY,
            run_fn=lambda: None,
            enabled=False,
        )
        assert task.is_due() is False

    def test_interval_seconds(self):
        assert (
            ScheduledTask(
                name="h", frequency=TaskFrequency.HOURLY, run_fn=lambda: None
            ).interval_seconds
            == 3600
        )
        assert (
            ScheduledTask(
                name="d", frequency=TaskFrequency.DAILY, run_fn=lambda: None
            ).interval_seconds
            == 86400
        )
        assert (
            ScheduledTask(
                name="w", frequency=TaskFrequency.WEEKLY, run_fn=lambda: None
            ).interval_seconds
            == 604800
        )


class TestScheduler:
    def test_register_task(self):
        scheduler = Scheduler(SchedulerConfig())
        scheduler.register_task("test", TaskFrequency.DAILY, lambda: "result")
        assert len(scheduler.tasks) == 1
        assert scheduler.tasks[0].name == "test"

    def test_run_due_tasks_executes_due_tasks(self):
        scheduler = Scheduler(SchedulerConfig())
        results = []
        scheduler.register_task(
            "test", TaskFrequency.DAILY, lambda: results.append("ran")
        )
        scheduler.run_due_tasks()
        assert len(results) == 1

    def test_run_due_tasks_skips_not_due(self):
        scheduler = Scheduler(SchedulerConfig())
        results = []
        scheduler.register_task(
            "test", TaskFrequency.DAILY, lambda: results.append("ran")
        )
        # First run marks it as run
        scheduler.run_due_tasks()
        # Second run should skip (not enough time passed)
        scheduler.run_due_tasks()
        assert len(results) == 1

    def test_run_due_tasks_handles_errors(self):
        scheduler = Scheduler(SchedulerConfig())

        def failing_task():
            raise ValueError("test error")

        scheduler.register_task("failing", TaskFrequency.DAILY, failing_task)
        results = scheduler.run_due_tasks()
        assert len(results) == 1
        assert results[0]["success"] is False
        assert "test error" in results[0]["error"]

    def test_get_status(self):
        scheduler = Scheduler(SchedulerConfig())
        scheduler.register_task("task1", TaskFrequency.DAILY, lambda: None)
        scheduler.register_task("task2", TaskFrequency.HOURLY, lambda: None)
        status = scheduler.get_status()
        assert status["task_count"] == 2
        assert len(status["tasks"]) == 2
        assert status["tasks"][0]["name"] == "task1"
        assert status["tasks"][1]["frequency"] == "hourly"
