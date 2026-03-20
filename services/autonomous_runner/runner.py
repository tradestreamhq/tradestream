"""Autonomous signal generation runner.

Background service that continuously generates trading signals
by polling all signal sources on configurable intervals.
"""

import logging
import signal
import threading
import time
import uuid

from services.autonomous_runner.config import Config
from services.autonomous_runner.coordinator import SignalCoordinator
from services.autonomous_runner.dashboard import record_cycle, set_dashboard_state
from services.autonomous_runner.kill_switch import KillSwitch
from services.autonomous_runner.metrics import pipeline_metrics
from services.autonomous_runner.outcome_tracker import OutcomeTracker
from services.autonomous_runner.retention_job import RetentionJob
from services.shared.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class AutonomousRunner:
    """Main runner that schedules signal generation cycles."""

    def __init__(self, config: Config, redis_client=None, db_url: str = ""):
        self.config = config
        self.instance_id = config.instance_id or str(uuid.uuid4())[:8]
        self.coordinator = SignalCoordinator(config, self.instance_id, db_url=db_url)
        self._shutdown = threading.Event()
        self._redis = redis_client
        self._kill_switch = None
        self._consecutive_overruns = 0
        self._cooldown_remaining = 0
        self._outcome_cycle_counter = 0

        if redis_client:
            self._kill_switch = KillSwitch(redis_client, config.kill_switch)

        # Outcome tracker for recording signal results (with entry price lookup)
        self._outcome_tracker = OutcomeTracker(
            db=self.coordinator._db,
            entry_price_fn=self.coordinator.get_entry_price,
        )

        # Retention job for automated cleanup (runs every 24h by default)
        self._retention_job = RetentionJob(
            db_pool=(
                self.coordinator._db._pool
                if self.coordinator._db.is_available
                else None
            ),
        )

        # Validate model configuration at startup
        validation = self.coordinator.model_validator.validate_all()
        if not validation.get("all_valid", True):
            logger.warning(
                "Model validation warnings at startup: %s",
                validation.get("errors", []),
            )

        set_dashboard_state(
            coordinator=self.coordinator,
            kill_switch=self._kill_switch,
            runner_started_at=time.time(),
        )

    def start(self):
        """Start the autonomous runner loop."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        logger.info(
            "Autonomous runner %s started. Schedule: %s, Symbols: %d",
            self.instance_id,
            self.config.schedule,
            len(self.config.symbols),
        )

        interval = 60  # default 1 minute
        parts = self.config.schedule.split()
        if parts and parts[0].startswith("*/"):
            try:
                interval = int(parts[0][2:]) * 60
            except ValueError:
                pass

        while not self._shutdown.is_set():
            try:
                self._run_cycle()
            except Exception as e:
                logger.error("Cycle failed: %s", e)

            # Sleep in 1-second increments so we can respond to shutdown
            for _ in range(interval):
                if self._shutdown.is_set():
                    break
                time.sleep(1)

        logger.info("Autonomous runner %s shut down.", self.instance_id)

    def _run_cycle(self):
        """Execute one signal generation cycle."""
        # Check kill switch
        if self._kill_switch and self._kill_switch.is_active():
            logger.info("Kill switch active, skipping cycle")
            pipeline_metrics.set_kill_switch(True)
            pipeline_metrics.record_signal_skipped("kill_switch")
            return
        pipeline_metrics.set_kill_switch(False)

        # Check cooldown (backpressure)
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1
            logger.info(
                "Backpressure cooldown: %d cycles remaining",
                self._cooldown_remaining,
            )
            pipeline_metrics.record_signal_skipped("backpressure")
            return

        # Check circuit breaker
        if not self.coordinator.llm_circuit_breaker.allow_request():
            logger.warning("Circuit breaker open, skipping cycle")
            pipeline_metrics.record_signal_skipped("circuit_breaker")
            return

        cycle_start = time.time()
        logger.info("Starting signal generation cycle")

        try:
            batch_size = self.config.parallel.max_concurrent
            timeout = self.config.timeouts.symbol_timeout_seconds

            signals = self.coordinator.process_all_symbols(
                self.config.symbols,
                batch_size=batch_size,
                symbol_timeout=timeout,
            )

            duration_ms = int((time.time() - cycle_start) * 1000)
            emitted = sum(
                1 for s in signals if s and s.risk_approved and s.action != "HOLD"
            )

            record_cycle(duration_ms, emitted)
            pipeline_metrics.record_cycle_duration(duration_ms / 1000.0, "success")
            pipeline_metrics.set_active_signals(
                self.coordinator.risk_manager._active_signals
            )
            self._consecutive_overruns = 0

            # Check outcomes every 5 cycles
            self._outcome_cycle_counter += 1
            if self._outcome_cycle_counter >= 5:
                self._outcome_cycle_counter = 0
                try:
                    outcomes = self._outcome_tracker.check_pending_outcomes()
                    if outcomes:
                        logger.info("Recorded %d outcomes", len(outcomes))
                except Exception as oe:
                    logger.warning("Outcome tracking failed: %s", oe)

            # Run retention job if due (checks its own interval)
            if self._retention_job.is_available and self._retention_job.should_run():
                try:
                    result = self._retention_job.execute()
                    logger.info(
                        "Retention job: archived=%d deleted=%d",
                        result.archived_count,
                        result.deleted_decisions_count,
                    )
                except Exception as re:
                    logger.warning("Retention job failed: %s", re)

            logger.info(
                "Cycle complete: %d decisions, %d emitted in %dms",
                len(signals),
                emitted,
                duration_ms,
            )

        except Exception as e:
            logger.error("Signal generation cycle failed: %s", e)
            pipeline_metrics.record_cycle_duration((time.time() - cycle_start), "error")
            self._consecutive_overruns += 1
            if (
                self._consecutive_overruns
                >= self.config.adaptive.backpressure_max_overruns
            ):
                self._cooldown_remaining = self.config.adaptive.cooldown_cycles
                logger.warning(
                    "Backpressure triggered after %d overruns, cooling down for %d cycles",
                    self._consecutive_overruns,
                    self._cooldown_remaining,
                )
                self._consecutive_overruns = 0

    def _handle_shutdown(self, signum, frame):
        logger.info("Received signal %s, shutting down", signum)
        self._shutdown.set()

    def shutdown(self):
        """Programmatic shutdown."""
        self._shutdown.set()
