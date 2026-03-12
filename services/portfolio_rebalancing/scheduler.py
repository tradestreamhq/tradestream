"""Scheduled rebalancing trigger.

Provides a simple interval-based scheduler that periodically
runs the rebalancing engine.
"""

import time
from enum import Enum


class RebalanceFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


# Interval in seconds for each frequency
FREQUENCY_SECONDS = {
    RebalanceFrequency.HOURLY: 3600,
    RebalanceFrequency.DAILY: 86400,
    RebalanceFrequency.WEEKLY: 604800,
}


class RebalanceSchedule:
    """Tracks when the next rebalance is due."""

    def __init__(self, frequency: RebalanceFrequency):
        self.frequency = frequency
        self.interval_seconds = FREQUENCY_SECONDS[frequency]
        self.last_run_time = 0.0

    def is_due(self) -> bool:
        """Check if a rebalance is due."""
        return time.time() - self.last_run_time >= self.interval_seconds

    def mark_run(self) -> None:
        """Record that a rebalance just ran."""
        self.last_run_time = time.time()

    def seconds_until_next(self) -> float:
        """Return seconds until the next scheduled rebalance."""
        elapsed = time.time() - self.last_run_time
        remaining = self.interval_seconds - elapsed
        return max(0.0, remaining)
