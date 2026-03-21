"""Strategy Execution Engine API Service.

Provides REST endpoints to start/stop strategy execution and query state/signals.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict

import psycopg2
import psycopg2.extras
import yaml
from absl import app as absl_app
from absl import flags
from flask import Flask, jsonify, request
from flask_cors import CORS

from services.shared.auth import flask_auth_middleware
from services.strategy_execution_engine.engine import StrategyExecutionEngine
from services.strategy_execution_engine.models import (
    Candle,
    StrategyConfig,
    StrategyStatus,
)

app = Flask(__name__)
CORS(app)
flask_auth_middleware(app)

FLAGS = flags.FLAGS

DB_CONFIG: Dict = {}

# Global engine instance
engine = StrategyExecutionEngine()

logger = logging.getLogger(__name__)


def get_db_connection():
    """Create a database connection from config."""
    if not DB_CONFIG:
        raise Exception("Database configuration not initialized")
    return psycopg2.connect(
        host=DB_CONFIG.get("host"),
        port=DB_CONFIG.get("port"),
        database=DB_CONFIG.get("database"),
        user=DB_CONFIG.get("username"),
        password=DB_CONFIG.get("password"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def load_strategy_config_from_db(strategy_id: str) -> dict:
    """Load strategy spec from the database by ID."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, name, description, complexity,
                      indicators, entry_conditions, exit_conditions, parameters
               FROM strategy_specs WHERE id = %s AND is_active = TRUE""",
            (strategy_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "name": row["name"],
            "description": row["description"] or "",
            "complexity": row["complexity"] or "SIMPLE",
            "indicators": (
                row["indicators"]
                if isinstance(row["indicators"], list)
                else json.loads(row["indicators"])
            ),
            "entryConditions": (
                row["entry_conditions"]
                if isinstance(row["entry_conditions"], list)
                else json.loads(row["entry_conditions"])
            ),
            "exitConditions": (
                row["exit_conditions"]
                if isinstance(row["exit_conditions"], list)
                else json.loads(row["exit_conditions"])
            ),
            "parameters": (
                row["parameters"]
                if isinstance(row["parameters"], list)
                else json.loads(row["parameters"])
            ),
        }
    finally:
        conn.close()


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "service": "strategy-execution-engine",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@app.route("/api/v1/strategies/<strategy_id>/start", methods=["POST"])
def start_strategy(strategy_id):
    """Start live execution of a strategy."""
    try:
        body = request.get_json(silent=True) or {}
        symbol = body.get("symbol", "BTC/USD")
        timeframe = body.get("timeframe", "1m")
        parameter_overrides = body.get("parameters")

        # Try loading config from request body first, then database
        config_data = body.get("config")
        if config_data:
            config = StrategyConfig.from_dict(config_data)
        else:
            config_data = load_strategy_config_from_db(strategy_id)
            if config_data is None:
                return jsonify({"error": f"Strategy {strategy_id} not found"}), 404
            config = StrategyConfig.from_dict(config_data)

        ctx = engine.start_strategy(
            strategy_id=strategy_id,
            config=config,
            symbol=symbol,
            timeframe=timeframe,
            parameter_overrides=parameter_overrides,
        )
        return (
            jsonify(
                {
                    "message": f"Strategy {strategy_id} started",
                    "context": ctx.to_dict(),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        logger.exception("Failed to start strategy %s", strategy_id)
        return jsonify({"error": f"Failed to start strategy: {str(e)}"}), 500


@app.route("/api/v1/strategies/<strategy_id>/stop", methods=["POST"])
def stop_strategy(strategy_id):
    """Stop execution of a strategy."""
    try:
        state = engine.stop_strategy(strategy_id)
        return (
            jsonify(
                {
                    "message": f"Strategy {strategy_id} stopped",
                    "state": state.to_dict(),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )
    except KeyError:
        return jsonify({"error": f"Strategy {strategy_id} not found"}), 404
    except Exception as e:
        logger.exception("Failed to stop strategy %s", strategy_id)
        return jsonify({"error": f"Failed to stop strategy: {str(e)}"}), 500


@app.route("/api/v1/strategies/<strategy_id>/state", methods=["GET"])
def get_strategy_state(strategy_id):
    """Get current execution state of a strategy."""
    state = engine.get_state(strategy_id)
    if state is None:
        return jsonify({"error": f"Strategy {strategy_id} not found"}), 404
    return (
        jsonify(
            {
                "state": state.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
            }
        ),
        200,
    )


@app.route("/api/v1/strategies/<strategy_id>/signals", methods=["GET"])
def get_strategy_signals(strategy_id):
    """Get recent signals emitted by a strategy."""
    limit = request.args.get("limit", 50, type=int)
    limit = min(limit, 200)

    ctx = engine.get_context(strategy_id)
    if ctx is None:
        return jsonify({"error": f"Strategy {strategy_id} not found"}), 404

    signals = engine.get_signals(strategy_id, limit=limit)
    return (
        jsonify(
            {
                "strategy_id": strategy_id,
                "signals": [s.to_dict() for s in signals],
                "count": len(signals),
                "timestamp": datetime.utcnow().isoformat(),
            }
        ),
        200,
    )


def main(argv):
    del argv  # Unused

    DB_CONFIG.update(
        {
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": int(os.environ.get("DB_PORT", "5432")),
            "database": os.environ.get("DB_NAME", "tradestream"),
            "username": os.environ.get("DB_USER", "tradestream"),
            "password": os.environ.get("DB_PASSWORD", ""),
        }
    )

    port = int(os.environ.get("PORT", "8080"))
    logger.info("Starting Strategy Execution Engine on port %d", port)
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    absl_app.run(main)
