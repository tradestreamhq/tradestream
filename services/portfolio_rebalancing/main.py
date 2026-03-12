"""Portfolio rebalancing service entry point.

Runs the rebalancer on a schedule (or once in dry-run mode).
"""

import asyncio
import os
import sys

import asyncpg
from absl import app, flags, logging

from services.portfolio_rebalancing.rebalancer import (
    RebalanceConstraints,
    format_rebalance_report,
)
from services.portfolio_rebalancing.scheduler import (
    RebalanceFrequency,
    RebalanceSchedule,
)
from services.portfolio_rebalancing.service import RebalancingService

FLAGS = flags.FLAGS

flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string(
    "postgres_database",
    os.environ.get("POSTGRES_DATABASE", ""),
    "PostgreSQL database",
)
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "", "PostgreSQL password")

flags.DEFINE_boolean("dry_run", True, "Compute but do not execute trades")
flags.DEFINE_boolean("once", False, "Run once and exit instead of scheduling")
flags.DEFINE_enum(
    "frequency",
    "daily",
    [f.value for f in RebalanceFrequency],
    "Rebalance frequency when running on schedule",
)

flags.DEFINE_float("min_trade_value", 10.0, "Minimum trade value in USD")
flags.DEFINE_float("max_trade_pct", 0.25, "Max single trade as fraction of portfolio")
flags.DEFINE_float("max_slippage_pct", 0.005, "Max expected slippage")
flags.DEFINE_float("drift_threshold_pct", 0.02, "Min drift to trigger rebalance")


def main(argv):
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")

    logging.set_verbosity(logging.INFO)

    if not FLAGS.postgres_password:
        logging.error("--postgres_password is required")
        sys.exit(1)

    db_config = {
        "host": FLAGS.postgres_host,
        "port": FLAGS.postgres_port,
        "database": FLAGS.postgres_database,
        "user": FLAGS.postgres_username,
        "password": FLAGS.postgres_password,
    }

    constraints = RebalanceConstraints(
        min_trade_value=FLAGS.min_trade_value,
        max_trade_pct=FLAGS.max_trade_pct,
        max_slippage_pct=FLAGS.max_slippage_pct,
        drift_threshold_pct=FLAGS.drift_threshold_pct,
    )

    async def run():
        pool = await asyncpg.create_pool(**db_config)
        service = RebalancingService(pool)

        try:
            if FLAGS.once:
                report = await service.run_rebalance(
                    constraints=constraints,
                    dry_run=FLAGS.dry_run,
                )
                print(format_rebalance_report(report))
                return

            schedule = RebalanceSchedule(RebalanceFrequency(FLAGS.frequency))
            logging.info(
                "Starting rebalancer on %s schedule (dry_run=%s)",
                FLAGS.frequency,
                FLAGS.dry_run,
            )

            while True:
                if schedule.is_due():
                    logging.info("Running scheduled rebalance")
                    report = await service.run_rebalance(
                        constraints=constraints,
                        dry_run=FLAGS.dry_run,
                    )
                    logging.info("Rebalance complete: %d trades", len(report.trades))
                    schedule.mark_run()

                wait = min(schedule.seconds_until_next(), 60.0)
                await asyncio.sleep(wait)

        finally:
            await pool.close()

    asyncio.run(run())


if __name__ == "__main__":
    app.run(main)
