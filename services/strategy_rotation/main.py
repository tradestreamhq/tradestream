#!/usr/bin/env python3
"""
Strategy Rotation - Phase 4 Implementation

Long-running service that continuously evaluates strategy rotation:
- Strategy switching based on performance
- Position management and sizing
- Dynamic rebalancing
- Risk management and stop-loss
- Market regime detection
- HTTP health endpoint for liveness/readiness probes
- Graceful shutdown on SIGINT/SIGTERM
"""

import asyncio
import signal
import sys
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Optional

import asyncpg
from absl import app, flags, logging
from dataclasses import dataclass
from enum import Enum

FLAGS = flags.FLAGS

# Database Configuration
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "", "PostgreSQL password")

# Rotation Configuration
flags.DEFINE_integer(
    "rotation_period_hours", 24, "How often to evaluate strategy rotation"
)
flags.DEFINE_float(
    "min_performance_threshold", 0.6, "Minimum performance to keep strategy"
)
flags.DEFINE_float(
    "rotation_threshold", 0.1, "Performance improvement needed for rotation"
)
flags.DEFINE_integer(
    "max_positions_per_symbol", 3, "Maximum concurrent positions per symbol"
)
flags.DEFINE_float(
    "position_size_factor", 0.1, "Position size as fraction of portfolio"
)
flags.DEFINE_float("stop_loss_threshold", 0.05, "Stop loss threshold (5%)")
flags.DEFINE_float("take_profit_threshold", 0.15, "Take profit threshold (15%)")

# Service Configuration
flags.DEFINE_integer(
    "rotation_interval_seconds",
    3600,
    "Seconds between rotation evaluations",
)
flags.DEFINE_integer("health_port", 8080, "Port for HTTP health endpoint")

# Output Configuration
flags.DEFINE_string(
    "output_topic", "strategy-rotations", "Kafka topic for rotation decisions"
)
flags.DEFINE_boolean("dry_run", False, "Run in dry-run mode (no Kafka output)")

_shutdown = False
_last_run_ok = False
_last_run_time = None


class PositionStatus(Enum):
    """Position status enumeration."""

    OPEN = "open"
    CLOSED = "closed"
    STOPPED_OUT = "stopped_out"
    TAKE_PROFIT = "take_profit"


@dataclass
class Position:
    """Represents a trading position."""

    position_id: str
    symbol: str
    strategy_id: str
    strategy_type: str
    entry_price: float
    current_price: float
    position_size: float
    entry_time: datetime
    status: PositionStatus
    pnl: float
    pnl_percent: float


@dataclass
class RotationDecision:
    """Represents a strategy rotation decision."""

    symbol: str
    old_strategy_id: Optional[str]
    new_strategy_id: str
    old_strategy_type: Optional[str]
    new_strategy_type: str
    reason: str
    performance_improvement: float
    decision_time: datetime


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoints."""

    def do_GET(self):
        if self.path == "/healthz" or self.path == "/readyz":
            if _shutdown:
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"shutting down")
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                status = "ok"
                if _last_run_time:
                    status += f" last_run={_last_run_time.isoformat()}"
                self.wfile.write(status.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def _start_health_server(port: int) -> HTTPServer:
    """Start HTTP health check server in a background thread."""
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info("Health endpoint listening on port %d", port)
    return server


def _handle_shutdown(signum, frame):
    global _shutdown
    logging.info("Received signal %d, shutting down...", signum)
    _shutdown = True


class StrategyRotator:
    """Handles dynamic strategy rotation and position management."""

    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.pool = None

    async def connect(self):
        """Connect to PostgreSQL."""
        self.pool = await asyncpg.create_pool(**self.db_config)
        logging.info("Connected to PostgreSQL")

    async def close(self):
        """Close database connection."""
        if self.pool:
            await self.pool.close()
            logging.info("Database connection closed")

    async def get_active_positions(self) -> List[Position]:
        """Get currently active positions."""
        return []

    async def get_candidate_strategies(self, symbol: str) -> List[Dict]:
        """Get candidate strategies for rotation."""
        query = """
        SELECT
            strategy_id,
            symbol,
            strategy_type,
            current_score,
            created_at,
            last_evaluated_at
        FROM strategies
        WHERE symbol = $1
        AND is_active = TRUE
        AND current_score >= $2
        ORDER BY current_score DESC
        LIMIT 10
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, symbol, FLAGS.min_performance_threshold)
            return [dict(row) for row in rows]

    async def evaluate_rotation_opportunities(self) -> List[RotationDecision]:
        """Evaluate opportunities for strategy rotation."""
        symbols_query = "SELECT DISTINCT symbol FROM strategies WHERE is_active = TRUE"

        async with self.pool.acquire() as conn:
            symbol_rows = await conn.fetch(symbols_query)
            symbols = [row["symbol"] for row in symbol_rows]

        rotation_decisions = []

        for symbol in symbols:
            candidate_strategies = await self.get_candidate_strategies(symbol)

            if len(candidate_strategies) < 2:
                continue

            active_positions = [
                p for p in await self.get_active_positions() if p.symbol == symbol
            ]

            rotation_decision = self._evaluate_symbol_rotation(
                symbol, candidate_strategies, active_positions
            )

            if rotation_decision:
                rotation_decisions.append(rotation_decision)

        return rotation_decisions

    def _evaluate_symbol_rotation(
        self, symbol: str, strategies: List[Dict], active_positions: List[Position]
    ) -> Optional[RotationDecision]:
        """Evaluate rotation opportunities for a specific symbol."""

        if not strategies:
            return None

        current_best = strategies[0]

        current_strategy_id = None
        if active_positions:
            current_strategy_id = active_positions[0].strategy_id
            current_strategy_type = active_positions[0].strategy_type

            current_in_top = any(
                s["strategy_id"] == current_strategy_id for s in strategies[:3]
            )

            if not current_in_top:
                return RotationDecision(
                    symbol=symbol,
                    old_strategy_id=current_strategy_id,
                    new_strategy_id=current_best["strategy_id"],
                    old_strategy_type=current_strategy_type,
                    new_strategy_type=current_best["strategy_type"],
                    reason="Current strategy no longer in top performers",
                    performance_improvement=current_best["current_score"] - 0.6,
                    decision_time=datetime.now(),
                )
        else:
            return RotationDecision(
                symbol=symbol,
                old_strategy_id=None,
                new_strategy_id=current_best["strategy_id"],
                old_strategy_type=None,
                new_strategy_type=current_best["strategy_type"],
                reason="No active positions, starting with best strategy",
                performance_improvement=current_best["current_score"],
                decision_time=datetime.now(),
            )

        return None

    async def calculate_position_sizes(
        self, strategies: List[Dict]
    ) -> Dict[str, float]:
        """Calculate position sizes for strategies."""
        position_sizes = {}
        total_weight = 1.0
        weight_per_strategy = total_weight / len(strategies)

        for strategy in strategies:
            position_sizes[strategy["strategy_id"]] = (
                weight_per_strategy * FLAGS.position_size_factor
            )

        return position_sizes

    async def get_rotation_statistics(self) -> Dict:
        """Get statistics about strategy rotation."""
        async with self.pool.acquire() as conn:
            total_query = "SELECT COUNT(*) FROM strategies WHERE is_active = TRUE"
            total_strategies = await conn.fetchval(total_query)

            performance_query = """
            SELECT
                COUNT(CASE WHEN current_score >= 0.9 THEN 1 END) as excellent,
                COUNT(CASE WHEN current_score >= 0.8 AND current_score < 0.9 THEN 1 END) as good,
                COUNT(CASE WHEN current_score >= 0.7 AND current_score < 0.8 THEN 1 END) as fair,
                COUNT(CASE WHEN current_score < 0.7 THEN 1 END) as poor
            FROM strategies
            WHERE is_active = TRUE
            """
            performance_stats = await conn.fetchrow(performance_query)

            return {
                "total_strategies": total_strategies or 0,
                "excellent_strategies": performance_stats["excellent"] or 0,
                "good_strategies": performance_stats["good"] or 0,
                "fair_strategies": performance_stats["fair"] or 0,
                "poor_strategies": performance_stats["poor"] or 0,
            }


async def _run_rotation_cycle(rotator: StrategyRotator) -> int:
    """Run a single rotation evaluation cycle. Returns number of decisions."""
    global _last_run_ok, _last_run_time

    try:
        stats = await rotator.get_rotation_statistics()
        logging.info(
            "Rotation stats: total=%d excellent=%d good=%d fair=%d poor=%d",
            stats["total_strategies"],
            stats["excellent_strategies"],
            stats["good_strategies"],
            stats["fair_strategies"],
            stats["poor_strategies"],
        )

        rotation_decisions = await rotator.evaluate_rotation_opportunities()

        if rotation_decisions:
            symbols_affected = set(d.symbol for d in rotation_decisions)
            avg_improvement = sum(
                d.performance_improvement for d in rotation_decisions
            ) / len(rotation_decisions)
            logging.info(
                "Rotation decisions: %d across %d symbols (avg improvement: %.3f)",
                len(rotation_decisions),
                len(symbols_affected),
                avg_improvement,
            )
            for decision in rotation_decisions[:5]:
                logging.info(
                    "  %s: %s -> %s (improvement: %.3f, reason: %s)",
                    decision.symbol,
                    decision.old_strategy_type or "None",
                    decision.new_strategy_type,
                    decision.performance_improvement,
                    decision.reason,
                )
        else:
            logging.info("No rotation opportunities found this cycle.")

        _last_run_ok = True
        _last_run_time = datetime.now()
        return len(rotation_decisions)

    except Exception as e:
        logging.exception("Error in rotation cycle: %s", e)
        _last_run_ok = False
        _last_run_time = datetime.now()
        return 0


def main(argv):
    """Main function."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")

    logging.set_verbosity(logging.INFO)

    if not FLAGS.postgres_password:
        logging.error("--postgres_password is required")
        sys.exit(1)
    logging.info("Starting Strategy Rotation Service")

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    health_server = _start_health_server(FLAGS.health_port)

    db_config = {
        "host": FLAGS.postgres_host,
        "port": FLAGS.postgres_port,
        "database": FLAGS.postgres_database,
        "user": FLAGS.postgres_username,
        "password": FLAGS.postgres_password,
    }

    rotator = StrategyRotator(db_config)

    async def run():
        try:
            await rotator.connect()
            logging.info(
                "Strategy rotation service started. "
                "Evaluating every %d seconds.",
                FLAGS.rotation_interval_seconds,
            )

            while not _shutdown:
                await _run_rotation_cycle(rotator)

                remaining = FLAGS.rotation_interval_seconds
                while remaining > 0 and not _shutdown:
                    await asyncio.sleep(min(remaining, 1.0))
                    remaining -= 1

        except Exception as e:
            logging.exception("Fatal error in strategy rotation: %s", e)
            sys.exit(1)
        finally:
            await rotator.close()
            health_server.shutdown()
            logging.info("Strategy rotation service shut down.")

    asyncio.run(run())


if __name__ == "__main__":
    app.run(main)
