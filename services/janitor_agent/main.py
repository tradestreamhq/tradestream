"""Entry point for the Janitor Agent service."""

import signal
import sys

from absl import app, flags, logging

from services.janitor_agent.agent import JanitorAgent, JanitorConfig
from services.janitor_agent.db_maintenance import MaintenanceConfig
from services.janitor_agent.health_checker import HealthCheckConfig
from services.janitor_agent.retirement_criteria import RetirementConfig
from services.janitor_agent.scheduler import Scheduler, SchedulerConfig, TaskFrequency

FLAGS = flags.FLAGS

# Database connection
flags.DEFINE_string("pg_connection_string", "", "PostgreSQL connection string")

# InfluxDB
flags.DEFINE_string("influx_url", "", "InfluxDB URL")
flags.DEFINE_string("influx_token", "", "InfluxDB token")
flags.DEFINE_string("influx_org", "tradestream", "InfluxDB organization")
flags.DEFINE_string("influx_bucket", "tradestream", "InfluxDB bucket")

# Retirement criteria
flags.DEFINE_integer(
    "min_signals", 100, "Minimum forward-test signals before evaluation"
)
flags.DEFINE_integer("min_age_days", 180, "Minimum age in days before evaluation")
flags.DEFINE_float("max_sharpe", 0.5, "Maximum Sharpe ratio threshold for retirement")
flags.DEFINE_float("max_accuracy", 0.45, "Maximum accuracy threshold for retirement")
flags.DEFINE_integer("max_retirements_per_run", 50, "Maximum retirements per run")

# Scheduler
flags.DEFINE_integer("check_interval_seconds", 60, "Scheduler check interval")
flags.DEFINE_boolean("run_on_startup", True, "Run all tasks immediately on startup")
flags.DEFINE_boolean("run_once", False, "Run one cycle and exit (for testing/cron)")

# Stale data cleanup
flags.DEFINE_integer(
    "stale_signal_days", 365, "Days before signals are considered stale"
)
flags.DEFINE_integer(
    "stale_backtest_days", 180, "Days before backtests are considered stale"
)

_shutdown = False


def _handle_shutdown(signum, frame):
    global _shutdown
    logging.info("Received signal %d, shutting down...", signum)
    _shutdown = True


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    if not FLAGS.pg_connection_string:
        logging.error("--pg_connection_string is required")
        sys.exit(1)

    # Build configuration
    retirement_config = RetirementConfig(
        min_signals=FLAGS.min_signals,
        min_age_days=FLAGS.min_age_days,
        max_sharpe=FLAGS.max_sharpe,
        max_accuracy=FLAGS.max_accuracy,
        max_retirements_per_run=FLAGS.max_retirements_per_run,
    )

    maintenance_config = MaintenanceConfig(
        pg_connection_string=FLAGS.pg_connection_string,
        influx_url=FLAGS.influx_url,
        influx_token=FLAGS.influx_token,
        influx_org=FLAGS.influx_org,
        influx_bucket=FLAGS.influx_bucket,
        stale_signal_days=FLAGS.stale_signal_days,
        stale_backtest_days=FLAGS.stale_backtest_days,
    )

    health_config = HealthCheckConfig()

    config = JanitorConfig(
        retirement=retirement_config,
        maintenance=maintenance_config,
        health_check=health_config,
    )

    agent = JanitorAgent(config)

    if FLAGS.run_once:
        logging.info("Running single janitor cycle")
        report = agent.run_full_cycle()
        logging.info("Report:\n%s", report.to_markdown())
        return

    # Set up scheduler
    scheduler_config = SchedulerConfig(
        check_interval_seconds=FLAGS.check_interval_seconds,
        run_on_startup=FLAGS.run_on_startup,
    )
    scheduler = Scheduler(scheduler_config)

    scheduler.register_task(
        name="retirement_evaluation",
        frequency=TaskFrequency.DAILY,
        run_fn=agent.run_retirement_cycle,
    )
    scheduler.register_task(
        name="db_maintenance",
        frequency=TaskFrequency.DAILY,
        run_fn=agent.run_db_maintenance,
    )
    scheduler.register_task(
        name="health_checks",
        frequency=TaskFrequency.HOURLY,
        run_fn=agent.run_health_checks,
    )
    scheduler.register_task(
        name="state_repairs",
        frequency=TaskFrequency.DAILY,
        run_fn=agent.run_state_repairs,
    )
    scheduler.register_task(
        name="log_rotation",
        frequency=TaskFrequency.DAILY,
        run_fn=agent.run_log_rotation,
    )

    logging.info("Janitor Agent starting")
    scheduler.run_loop(lambda: _shutdown)
    logging.info("Janitor Agent shut down.")


if __name__ == "__main__":
    app.run(main)
