"""Entry point for the Learning Engine — regime detection, performance tracking,
weight optimization, parameter adaptation, and A/B testing."""

import signal
import sys
import time
from datetime import datetime, timezone

import psycopg2
from absl import app, flags, logging

from services.learning_engine.ab_testing import ABTestManager
from services.learning_engine.dashboard_provider import DashboardProvider
from services.learning_engine.engine import LearningEngine
from services.learning_engine.parameter_adapter import ParameterAdapter
from services.learning_engine.performance_tracker import PerformanceTracker
from services.learning_engine.regime_alerter import RegimeAlerter
from services.learning_engine.regime_detector import RegimeDetector
from services.learning_engine.weight_optimizer import WeightOptimizer
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


def _get_candles_from_db(conn, instrument, limit=100):
    """Fetch recent candle data for an instrument from the database."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT open_price, high_price, low_price, close_price, volume
                FROM candles
                WHERE instrument = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (instrument, limit),
            )
            if not cur.description:
                return []
            rows = cur.fetchall()
            rows.reverse()
            return [
                {
                    "open": float(r[0]) if r[0] else 0,
                    "high": float(r[1]) if r[1] else 0,
                    "low": float(r[2]) if r[2] else 0,
                    "close": float(r[3]) if r[3] else 0,
                    "volume": float(r[4]) if r[4] else 0,
                }
                for r in rows
            ]
    except Exception as e:
        _log.warning("Could not fetch candles", instrument=instrument, error=str(e))
        return []


def _get_strategy_trades(conn, instrument, limit=50):
    """Fetch recent trades grouped by strategy for an instrument."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.spec_id as strategy_spec_id,
                    do.pnl_percent,
                    do.hold_duration
                FROM decision_outcomes do
                LEFT JOIN signals s ON s.id::text = do.decision_id::text
                WHERE do.instrument = %s
                ORDER BY do.created_at DESC
                LIMIT %s
                """,
                (instrument, limit),
            )
            if not cur.description:
                return {}
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            by_strategy = {}
            for row in rows:
                sid = str(row.get("strategy_spec_id", "unknown"))
                if sid not in by_strategy:
                    by_strategy[sid] = []
                by_strategy[sid].append(row)
            return by_strategy
    except Exception as e:
        _log.warning("Could not fetch trades", instrument=instrument, error=str(e))
        return {}


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    instruments = [s.strip() for s in FLAGS.instruments.split(",") if s.strip()]
    if not instruments:
        _log.error("No instruments configured.")
        sys.exit(1)

    conn = psycopg2.connect(FLAGS.db_url)

    engine = LearningEngine(connection=conn)
    regime_detector = RegimeDetector(db_connection=conn)
    performance_tracker = PerformanceTracker(db_connection=conn)
    weight_optimizer = WeightOptimizer(db_connection=conn)
    parameter_adapter = ParameterAdapter(db_connection=conn)
    regime_alerter = RegimeAlerter(db_connection=conn)
    ab_manager = ABTestManager(db_connection=conn)
    dashboard = DashboardProvider(db_connection=conn)

    _log.info(
        "Learning Engine started",
        instruments=instruments,
        interval_seconds=FLAGS.interval_seconds,
        components=[
            "regime_detector", "performance_tracker", "weight_optimizer",
            "parameter_adapter", "regime_alerter", "ab_testing", "dashboard",
        ],
    )

    while not _shutdown:
        _log.new_correlation_id()
        try:
            # Phase 1: Self-Reflection (existing)
            _log.info("Phase 1: Generating performance report")
            report = engine.generate_report()
            _log.info(
                "Performance report",
                total_decisions=report.total_decisions,
                total_outcomes=report.total_outcomes,
                win_rate=report.win_rate,
                avg_pnl=report.avg_pnl_percent,
                total_pnl=report.total_pnl,
            )

            # Phase 2: Regime Detection & Strategy Optimization
            for instrument in instruments:
                if _shutdown:
                    break

                _log.info("Phase 2: Regime analysis", instrument=instrument)

                candles = _get_candles_from_db(conn, instrument)
                if len(candles) >= 20:
                    previous_regime = regime_detector.get_current_regime(instrument)
                    regime_result = regime_detector.detect(candles, instrument)
                    regime_detector.store_regime(regime_result)

                    _log.info(
                        "Regime detected",
                        instrument=instrument,
                        regime=regime_result["regime_type"],
                        confidence=regime_result["confidence"],
                    )

                    alert = regime_alerter.check_regime_change(
                        instrument=instrument,
                        new_regime=regime_result,
                        previous_regime=previous_regime,
                    )
                    if alert:
                        _log.warning(
                            "Regime change alert",
                            instrument=instrument,
                            previous=alert["previous_regime"],
                            new=alert["new_regime"],
                        )

                    strategy_trades = _get_strategy_trades(conn, instrument)
                    strategy_performances = []
                    now = datetime.now(timezone.utc)
                    for strategy_id, trades in strategy_trades.items():
                        if _shutdown:
                            break
                        metrics = performance_tracker.track_strategy_performance(
                            strategy_spec_id=strategy_id,
                            regime_type=regime_result["regime_type"],
                            instrument=instrument,
                            trades=trades,
                            window_start=now,
                            window_end=now,
                        )
                        strategy_performances.append(metrics)

                    if strategy_performances:
                        weights = weight_optimizer.optimize_weights(
                            strategy_performances,
                            regime_result["regime_type"],
                            instrument,
                        )
                        _log.info(
                            "Weights optimized",
                            instrument=instrument,
                            strategies=len(weights),
                        )
                else:
                    _log.info(
                        "Insufficient candle data for regime detection",
                        instrument=instrument,
                        candles=len(candles),
                    )

                ctx = engine.get_historical_context(instrument)
                _log.info(
                    "Historical context",
                    instrument=instrument,
                    win_rate=ctx.win_rate,
                    recent_decisions=len(ctx.recent_decisions),
                    biases=len(ctx.detected_biases),
                )

                patterns = engine.detect_patterns(instrument)
                if patterns:
                    _log.info(
                        "Patterns detected",
                        instrument=instrument,
                        count=len(patterns),
                        patterns=[p["pattern_type"] for p in patterns],
                    )

            # Phase 3: A/B Test Evaluation
            _log.info("Phase 3: Evaluating A/B tests")
            for instrument in instruments:
                if _shutdown:
                    break
                experiments = ab_manager.get_running_experiments(instrument=instrument)
                for exp in experiments:
                    result = ab_manager.evaluate_experiment(exp["id"])
                    if result["recommendation"] in ("adopt_treatment", "keep_control"):
                        ab_manager.complete_experiment(
                            exp["id"], result["recommendation"]
                        )
                        _log.info(
                            "A/B test completed",
                            experiment_id=exp["id"],
                            recommendation=result["recommendation"],
                            improvement=result.get("improvement"),
                        )

            biases = engine.detect_biases()
            if biases:
                _log.warning(
                    "Biases detected",
                    count=len(biases),
                    types=[b["bias_type"] for b in biases],
                )

        except Exception as e:
            _log.exception("Error during learning engine run", error=str(e))

        if not _shutdown:
            _log.info(
                "Sleeping before next run",
                interval_seconds=FLAGS.interval_seconds,
            )
            for _ in range(FLAGS.interval_seconds):
                if _shutdown:
                    break
                time.sleep(1)

    conn.close()
    _log.info("Learning Engine shut down.")


if __name__ == "__main__":
    app.run(main)
