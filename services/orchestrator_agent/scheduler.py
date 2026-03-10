"""Cron-like scheduling logic for agent execution."""

import time

from absl import logging

from services.orchestrator_agent import config


class AgentSchedule:
    """Tracks when an agent should next run."""

    def __init__(self, agent_name, interval_seconds):
        self.agent_name = agent_name
        self.interval_seconds = interval_seconds
        self.last_run_time = 0.0

    def is_due(self):
        """Check if this agent is due to run."""
        return time.time() - self.last_run_time >= self.interval_seconds

    def mark_run(self):
        """Mark this agent as having just run."""
        self.last_run_time = time.time()

    def seconds_until_next(self):
        """Return seconds until next scheduled run."""
        elapsed = time.time() - self.last_run_time
        remaining = self.interval_seconds - elapsed
        return max(0.0, remaining)


class Scheduler:
    """Manages scheduling for all agent tasks."""

    def __init__(
        self,
        signal_interval=None,
        strategy_proposer_interval=None,
    ):
        signal_interval = signal_interval or config.SIGNAL_GENERATOR_INTERVAL_SECONDS
        strategy_proposer_interval = (
            strategy_proposer_interval or config.STRATEGY_PROPOSER_INTERVAL_SECONDS
        )

        self.signal_schedule = AgentSchedule(
            config.AGENT_SIGNAL_GENERATOR, signal_interval
        )
        self.strategy_proposer_schedule = AgentSchedule(
            config.AGENT_STRATEGY_PROPOSER, strategy_proposer_interval
        )

    def should_run_signal_generator(self):
        """Check if the signal generator pipeline should run."""
        return self.signal_schedule.is_due()

    def should_run_strategy_proposer(self):
        """Check if the strategy proposer should run."""
        return self.strategy_proposer_schedule.is_due()

    def mark_signal_generator_run(self):
        """Mark signal generator as having just run."""
        self.signal_schedule.mark_run()

    def mark_strategy_proposer_run(self):
        """Mark strategy proposer as having just run."""
        self.strategy_proposer_schedule.mark_run()

    def seconds_until_next_task(self):
        """Return the minimum seconds until any task is due."""
        return min(
            self.signal_schedule.seconds_until_next(),
            self.strategy_proposer_schedule.seconds_until_next(),
        )
