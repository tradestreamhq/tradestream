"""Entry point for the Learning Engine — periodic self-reflection and reporting."""

import signal
import sys
import time

from absl import app, flags, logging

from services.learning_engine.engine import LearningEngine
from services.shared.structured_logger import StructuredLogger

FLAGS = flags.FLAGS

flags.DEFINE_string("db_url", None, "PostgreSQL connection string.")
flags.DEFINE_string(
    "instruments",
    "BTC-USD,ETH-USD",
    "Comma-separated list of instruments to analyze.",
)
flags.DEFINE_integer(
    "interval_seconds",
    3600,
    "Interval between self-reflection runs in seconds (default: 1 hour).",
)

flags.mark_flag_as_required("db_url")

_shutdown = False

_log = StructuredLogger(service_name="learning_engine")


def _handle_shutdown(signum, frame):
    global _shutdown
    _log.info("Received shutdown signal", signum=signum)
    _shutdown = True


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    instruments = [s.strip() for s in FLAGS.instruments.split(",") if s.strip()]
    if not instruments:
        _log.error("No instruments configured.")
        sys.exit(1)

    engine = LearningEngine(db_url=FLAGS.db_url)

    _log.info(
        "Learning Engine started",
        instruments=instruments,
        interval_seconds=FLAGS.interval_seconds,
    )

    while not _shutdown:
        _log.new_correlation_id()
        try:
            # Generate overall performance report
            _log.info("Generating performance report")
            report = engine.generate_report()
            _log.info(
                "Performance report",
                total_decisions=report.total_decisions,
                total_outcomes=report.total_outcomes,
                win_rate=report.win_rate,
                avg_pnl=report.avg_pnl_percent,
                total_pnl=report.total_pnl,
            )

            # Per-instrument analysis
            for instrument in instruments:
                if _shutdown:
                    break
                _log.info("Analyzing instrument", instrument=instrument)

                ctx = engine.get_historical_context(instrument)
                _log.info(
                    "Historical context",
                    instrument=instrument,
                    win_rate=ctx.win_rate,
                    recent_decisions=len(ctx.recent_decisions),
                    biases=len(ctx.detected_biases),
                )

                # Detect and store patterns
                patterns = engine.detect_patterns(instrument)
                if patterns:
                    _log.info(
                        "Patterns detected",
                        instrument=instrument,
                        count=len(patterns),
                        patterns=[p["pattern_type"] for p in patterns],
                    )

            # Log biases across all instruments
            biases = engine.detect_biases()
            if biases:
                _log.warning(
                    "Biases detected",
                    count=len(biases),
                    types=[b["bias_type"] for b in biases],
                )

        except Exception as e:
            _log.exception("Error during self-reflection run", error=str(e))

        if not _shutdown:
            _log.info(
                "Sleeping before next run",
                interval_seconds=FLAGS.interval_seconds,
            )
            for _ in range(FLAGS.interval_seconds):
                if _shutdown:
                    break
                time.sleep(1)

    _log.info("Learning Engine shut down.")


if __name__ == "__main__":
    app.run(main)
