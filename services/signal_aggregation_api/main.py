"""
Signal Aggregation and Consensus Engine API Service.
Combines signals from multiple strategies to produce consensus views
with configurable weights and signal decay.
"""

import json
import logging
import math
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from absl import app as absl_app
from absl import flags
from flask import Flask, request, jsonify
from flask_cors import CORS

from services.shared.auth import flask_auth_middleware

# Flask configuration
app = Flask(__name__)
CORS(app)
flask_auth_middleware(app)

FLAGS = flags.FLAGS

logger = logging.getLogger(__name__)

# Global database configuration
DB_CONFIG = {}

# Default consensus parameters
DEFAULT_DECAY_HALF_LIFE_HOURS = 24
DEFAULT_RECENCY_WEIGHT = 0.3
DEFAULT_PERFORMANCE_WEIGHT = 0.4
DEFAULT_CONFIDENCE_WEIGHT = 0.3

# Signal type to numeric direction mapping
SIGNAL_DIRECTION = {
    "BUY": 1.0,
    "SELL": -1.0,
    "HOLD": 0.0,
    "CLOSE_LONG": -0.5,
    "CLOSE_SHORT": 0.5,
}


def get_db_connection():
    """Create a new database connection."""
    return psycopg2.connect(
        host=DB_CONFIG.get("host", "localhost"),
        port=DB_CONFIG.get("port", 5432),
        dbname=DB_CONFIG.get("dbname", "tradestream"),
        user=DB_CONFIG.get("user", "tradestream"),
        password=DB_CONFIG.get("password", ""),
    )


def compute_decay_factor(
    signal_age_hours: float, half_life_hours: float = DEFAULT_DECAY_HALF_LIFE_HOURS
) -> float:
    """Compute exponential decay factor for a signal based on its age.

    Returns a value between 0 and 1, where 1 means no decay (fresh signal)
    and values approach 0 for very old signals.
    """
    if half_life_hours <= 0:
        return 1.0
    return math.pow(0.5, signal_age_hours / half_life_hours)


def compute_strategy_performance_score(strategy_row: Dict) -> float:
    """Compute a performance score for a strategy based on its outcome history.

    Returns a value between 0 and 1.
    """
    total = strategy_row.get("total_signals", 0)
    if total == 0:
        return 0.5  # neutral for unknown strategies

    profitable = strategy_row.get("profitable_signals", 0)
    return profitable / total


def compute_signal_score(
    signal: Dict,
    now: datetime,
    strategy_performance: float,
    user_weights: Optional[Dict] = None,
    half_life_hours: float = DEFAULT_DECAY_HALF_LIFE_HOURS,
) -> float:
    """Compute the weighted score for a single signal.

    Combines:
    - Signal confidence/strength
    - Strategy historical performance
    - Recency (exponential decay)
    - Signal direction (BUY=+1, SELL=-1, etc.)

    Returns a score in [-1, 1] where positive = bullish, negative = bearish.
    """
    weights = user_weights or {}
    recency_w = weights.get("recency", DEFAULT_RECENCY_WEIGHT)
    performance_w = weights.get("performance", DEFAULT_PERFORMANCE_WEIGHT)
    confidence_w = weights.get("confidence", DEFAULT_CONFIDENCE_WEIGHT)

    # Normalize weights
    total_w = recency_w + performance_w + confidence_w
    if total_w > 0:
        recency_w /= total_w
        performance_w /= total_w
        confidence_w /= total_w

    # Signal confidence (strength field, 0-1)
    confidence = float(signal.get("strength") or 0.5)

    # Recency via decay
    created_at = signal.get("created_at")
    if created_at:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        age_hours = (now - created_at).total_seconds() / 3600
    else:
        age_hours = 0
    decay = compute_decay_factor(age_hours, half_life_hours)

    # Combined quality score (0 to 1)
    quality = (
        confidence_w * confidence
        + performance_w * strategy_performance
        + recency_w * decay
    )

    # Apply direction
    direction = SIGNAL_DIRECTION.get(signal.get("signal_type", "HOLD"), 0.0)
    return quality * direction


def compute_consensus(
    signals: List[Dict],
    now: datetime,
    strategy_performances: Dict[str, float],
    user_weights: Optional[Dict] = None,
    half_life_hours: float = DEFAULT_DECAY_HALF_LIFE_HOURS,
) -> Dict:
    """Compute consensus from a list of signals.

    Returns dict with:
    - direction: 'bullish', 'bearish', or 'neutral'
    - score: float in [-1, 1]
    - signal_count: number of contributing signals
    - confidence: average confidence across signals
    """
    if not signals:
        return {
            "direction": "neutral",
            "score": 0.0,
            "signal_count": 0,
            "confidence": 0.0,
        }

    total_score = 0.0
    total_weight = 0.0
    total_confidence = 0.0

    for signal in signals:
        spec_id = str(signal.get("spec_id", ""))
        perf = strategy_performances.get(spec_id, 0.5)

        score = compute_signal_score(signal, now, perf, user_weights, half_life_hours)

        # Weight by decay for aggregation
        created_at = signal.get("created_at")
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_hours = (now - created_at).total_seconds() / 3600
        else:
            age_hours = 0
        weight = compute_decay_factor(age_hours, half_life_hours)

        total_score += score * weight
        total_weight += weight
        total_confidence += float(signal.get("strength") or 0.5)

    if total_weight > 0:
        consensus_score = total_score / total_weight
    else:
        consensus_score = 0.0

    avg_confidence = total_confidence / len(signals)

    # Clamp to [-1, 1]
    consensus_score = max(-1.0, min(1.0, consensus_score))

    if consensus_score > 0.1:
        direction = "bullish"
    elif consensus_score < -0.1:
        direction = "bearish"
    else:
        direction = "neutral"

    return {
        "direction": direction,
        "score": round(consensus_score, 4),
        "signal_count": len(signals),
        "confidence": round(avg_confidence, 4),
    }


def fetch_signals_for_symbol(
    symbol: str,
    hours: int = 48,
    limit: int = 100,
) -> List[Dict]:
    """Fetch recent signals for a symbol from the database."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, spec_id, implementation_id, instrument,
                       signal_type, strength, price, stop_loss, take_profit,
                       outcome, pnl, pnl_percent, timeframe, metadata,
                       created_at
                FROM signals
                WHERE instrument = %s
                  AND created_at >= NOW() - INTERVAL '%s hours'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (symbol, hours, limit),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_strategy_performances(spec_ids: List[str]) -> Dict[str, float]:
    """Fetch performance scores for strategies based on historical outcomes."""
    if not spec_ids:
        return {}

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT spec_id::text,
                       COUNT(*) as total_signals,
                       COUNT(*) FILTER (WHERE outcome = 'PROFIT') as profitable_signals
                FROM signals
                WHERE spec_id = ANY(%s::uuid[])
                  AND outcome IS NOT NULL
                  AND outcome != 'PENDING'
                GROUP BY spec_id
                """,
                (spec_ids,),
            )
            results = {}
            for row in cur.fetchall():
                results[row["spec_id"]] = compute_strategy_performance_score(dict(row))
            return results
    finally:
        conn.close()


def fetch_signal_history(
    symbol: str,
    days: int = 30,
    limit: int = 200,
    offset: int = 0,
) -> Tuple[List[Dict], int]:
    """Fetch historical signal timeline with outcomes for a symbol."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get total count
            cur.execute(
                """
                SELECT COUNT(*) as total
                FROM signals
                WHERE instrument = %s
                  AND created_at >= NOW() - INTERVAL '%s days'
                """,
                (symbol, days),
            )
            total = cur.fetchone()["total"]

            # Get paginated results
            cur.execute(
                """
                SELECT id, spec_id, implementation_id, instrument,
                       signal_type, strength, price, stop_loss, take_profit,
                       outcome, exit_price, exit_time, pnl, pnl_percent,
                       timeframe, metadata, created_at
                FROM signals
                WHERE instrument = %s
                  AND created_at >= NOW() - INTERVAL '%s days'
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (symbol, days, limit, offset),
            )
            signals = []
            for row in cur.fetchall():
                signal = dict(row)
                # Serialize non-JSON-safe types
                for key in ("id", "spec_id", "implementation_id"):
                    if signal.get(key) is not None:
                        signal[key] = str(signal[key])
                for key in ("created_at", "exit_time"):
                    if signal.get(key) is not None:
                        signal[key] = signal[key].isoformat()
                for key in (
                    "strength",
                    "price",
                    "stop_loss",
                    "take_profit",
                    "exit_price",
                    "pnl",
                    "pnl_percent",
                ):
                    if signal.get(key) is not None:
                        signal[key] = float(signal[key])
                signals.append(signal)
            return signals, total
    finally:
        conn.close()


def clamp_pagination(limit: int, offset: int, max_limit: int = 200) -> Tuple[int, int]:
    """Clamp pagination parameters to safe ranges."""
    limit = max(1, min(limit, max_limit))
    offset = max(0, offset)
    return limit, offset


# --- API Endpoints ---


@app.route("/api/health")
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "signal-aggregation-api"})


@app.route("/api/v1/signals/aggregate", methods=["POST"])
def aggregate_signals():
    """Aggregate signals from multiple strategies for a symbol.

    Request body:
    {
        "symbol": "BTC-USD",
        "hours": 48,           // optional, lookback window
        "weights": {           // optional, user-defined weights
            "recency": 0.3,
            "performance": 0.4,
            "confidence": 0.3
        },
        "half_life_hours": 24  // optional, decay half-life
    }
    """
    data = request.get_json()
    if not data or "symbol" not in data:
        return jsonify({"error": "symbol is required"}), 400

    symbol = data["symbol"]
    hours = data.get("hours", 48)
    user_weights = data.get("weights")
    half_life = data.get("half_life_hours", DEFAULT_DECAY_HALF_LIFE_HOURS)

    try:
        signals = fetch_signals_for_symbol(symbol, hours=hours)

        # Get unique strategy spec_ids
        spec_ids = list({str(s["spec_id"]) for s in signals if s.get("spec_id")})
        strategy_performances = fetch_strategy_performances(spec_ids)

        now = datetime.now(timezone.utc)
        consensus = compute_consensus(
            signals, now, strategy_performances, user_weights, half_life
        )

        # Build per-signal detail
        signal_details = []
        for signal in signals:
            spec_id = str(signal.get("spec_id", ""))
            perf = strategy_performances.get(spec_id, 0.5)
            score = compute_signal_score(signal, now, perf, user_weights, half_life)
            signal_details.append(
                {
                    "id": str(signal["id"]),
                    "signal_type": signal["signal_type"],
                    "strength": float(signal.get("strength") or 0),
                    "strategy_performance": round(perf, 4),
                    "weighted_score": round(score, 4),
                    "created_at": (
                        signal["created_at"].isoformat()
                        if signal.get("created_at")
                        else None
                    ),
                }
            )

        return jsonify(
            {
                "symbol": symbol,
                "consensus": consensus,
                "signals": signal_details,
                "parameters": {
                    "hours": hours,
                    "half_life_hours": half_life,
                    "weights": user_weights
                    or {
                        "recency": DEFAULT_RECENCY_WEIGHT,
                        "performance": DEFAULT_PERFORMANCE_WEIGHT,
                        "confidence": DEFAULT_CONFIDENCE_WEIGHT,
                    },
                },
            }
        )
    except Exception as e:
        logger.exception("Error aggregating signals")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/signals/consensus")
def get_consensus():
    """Get current consensus view for a symbol.

    Query params:
    - symbol (required): Trading pair symbol
    - hours: Lookback window in hours (default: 48)
    - half_life_hours: Decay half-life (default: 24)
    """
    symbol = request.args.get("symbol")
    if not symbol:
        return jsonify({"error": "symbol query parameter is required"}), 400

    hours = int(request.args.get("hours", 48))
    half_life = float(
        request.args.get("half_life_hours", DEFAULT_DECAY_HALF_LIFE_HOURS)
    )

    try:
        signals = fetch_signals_for_symbol(symbol, hours=hours)

        spec_ids = list({str(s["spec_id"]) for s in signals if s.get("spec_id")})
        strategy_performances = fetch_strategy_performances(spec_ids)

        now = datetime.now(timezone.utc)
        consensus = compute_consensus(
            signals, now, strategy_performances, half_life_hours=half_life
        )
        consensus["symbol"] = symbol
        consensus["as_of"] = now.isoformat()

        return jsonify(consensus)
    except Exception as e:
        logger.exception("Error computing consensus")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/signals/history")
def get_signal_history():
    """Get historical signal timeline with outcomes.

    Query params:
    - symbol (required): Trading pair symbol
    - days: Lookback window in days (default: 30)
    - limit: Max results per page (default: 50, max: 200)
    - offset: Pagination offset (default: 0)
    """
    symbol = request.args.get("symbol")
    if not symbol:
        return jsonify({"error": "symbol query parameter is required"}), 400

    days = int(request.args.get("days", 30))
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    limit, offset = clamp_pagination(limit, offset)

    try:
        signals, total = fetch_signal_history(
            symbol, days=days, limit=limit, offset=offset
        )

        return jsonify(
            {
                "symbol": symbol,
                "signals": signals,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                },
            }
        )
    except Exception as e:
        logger.exception("Error fetching signal history")
        return jsonify({"error": str(e)}), 500


def main(argv):
    del argv  # Unused

    global DB_CONFIG
    DB_CONFIG = {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", "tradestream"),
        "user": os.environ.get("DB_USER", "tradestream"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }

    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"Starting Signal Aggregation API on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    absl_app.run(main)
