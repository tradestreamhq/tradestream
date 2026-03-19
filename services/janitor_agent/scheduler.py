"""Scheduler for running janitor maintenance tasks on configurable intervals.

Supports cron-like scheduling with configurable task intervals.
Each task type can have its own schedule.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

from absl import logging


class TaskFrequency(Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class ScheduledTask:
    """A task to be run on a schedule."""

    name: str
    frequency: TaskFrequency
    run_fn: Callable
    last_run: Optional[datetime] = None
    enabled: bool = True

    @property
    def interval_seconds(self) -> int:
        if self.frequency == TaskFrequency.HOURLY:
            return 3600
        elif self.frequency == TaskFrequency.DAILY:
            return 86400
        elif self.frequency == TaskFrequency.WEEKLY:
            return 604800
        return 86400

    def is_due(self) -> bool:
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_run).total_seconds()
        return elapsed >= self.interval_seconds


@dataclass
class SchedulerConfig:
    """Configuration for the janitor scheduler."""

    # How often to check if tasks are due (seconds)
    check_interval_seconds: int = 60
    # Schedule for each task type
    retirement_frequency: TaskFrequency = TaskFrequency.DAILY
    db_maintenance_frequency: TaskFrequency = TaskFrequency.DAILY
    health_check_frequency: TaskFrequency = TaskFrequency.HOURLY
    state_repair_frequency: TaskFrequency = TaskFrequency.DAILY
    # Run all tasks immediately on startup
    run_on_startup: bool = True


class Scheduler:
    """Manages scheduled execution of janitor tasks."""

    def __init__(self, config: SchedulerConfig):
        self._config = config
        self._tasks: list[ScheduledTask] = []
        self._running = False

    def register_task(
        self,
        name: str,
        frequency: TaskFrequency,
        run_fn: Callable,
        enabled: bool = True,
    ) -> None:
        """Register a task to be scheduled."""
        task = ScheduledTask(
            name=name,
            frequency=frequency,
            run_fn=run_fn,
            enabled=enabled,
        )
        self._tasks.append(task)
        logging.info(
            "Registered task: %s (frequency=%s, enabled=%s)",
            name,
            frequency.value,
            enabled,
        )

    def run_due_tasks(self) -> list[dict]:
        """Run all tasks that are due. Returns list of results."""
        results = []
        for task in self._tasks:
            if task.is_due():
                logging.info("Running scheduled task: %s", task.name)
                start = time.time()
                try:
                    result = task.run_fn()
                    elapsed = time.time() - start
                    task.last_run = datetime.now(timezone.utc)
                    results.append({
                        "task": task.name,
                        "success": True,
                        "duration_seconds": round(elapsed, 2),
                        "result": result,
                    })
                    logging.info(
                        "Task %s completed in %.2fs", task.name, elapsed
                    )
                except Exception as e:
                    elapsed = time.time() - start
                    results.append({
                        "task": task.name,
                        "success": False,
                        "duration_seconds": round(elapsed, 2),
                        "error": str(e),
                    })
                    logging.error(
                        "Task %s failed after %.2fs: %s", task.name, elapsed, e
                    )
        return results

    def run_loop(self, shutdown_flag: Callable[[], bool]) -> None:
        """Run the scheduler loop until shutdown is requested."""
        self._running = True
        logging.info("Scheduler starting with %d tasks", len(self._tasks))

        if self._config.run_on_startup:
            logging.info("Running all tasks on startup")
            self.run_due_tasks()

        while not shutdown_flag():
            self.run_due_tasks()
            # Sleep in 1-second increments to check shutdown flag
            for _ in range(self._config.check_interval_seconds):
                if shutdown_flag():
                    break
                time.sleep(1)

        self._running = False
        logging.info("Scheduler stopped")

    @property
    def tasks(self) -> list[ScheduledTask]:
        return list(self._tasks)

    def get_status(self) -> dict:
        """Get current scheduler status."""
        return {
            "running": self._running,
            "task_count": len(self._tasks),
            "tasks": [
                {
                    "name": t.name,
                    "frequency": t.frequency.value,
                    "enabled": t.enabled,
                    "last_run": t.last_run.isoformat() if t.last_run else None,
                    "is_due": t.is_due(),
                }
                for t in self._tasks
            ],
        }
