"""
Strategy Monitor API Service
Provides REST endpoints for strategy monitoring and visualization.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request
from flask_cors import CORS
from absl import flags
from absl import app as absl_app

# Flask configuration
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

FLAGS = flags.FLAGS

# Database configuration flags
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "", "PostgreSQL password")
flags.DEFINE_integer("api_port", 8080, "API server port")
flags.DEFINE_string("api_host", "0.0.0.0", "API server host")

# Global database connection parameters
DB_CONFIG = {}


def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["username"],
        password=DB_CONFIG["password"],
    )


def fetch_all_strategies() -> List[Dict]:
    """Fetch all active strategies from the database."""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = """
        SELECT 
            strategy_id,
            symbol,
            strategy_type,
            parameters,
            current_score,
            strategy_hash,
            discovery_symbol,
            discovery_start_time,
            discovery_end_time,
            first_discovered_at,
            last_evaluated_at,
            created_at,
            updated_at
        FROM Strategies 
        WHERE is_active = TRUE
        ORDER BY current_score DESC
        """

        cursor.execute(query)
        rows = cursor.fetchall()
        
        strategies = []
        for row in rows:
            strategy = {
                "strategy_id": str(row["strategy_id"]),
                "symbol": row["symbol"],
                "strategy_type": row["strategy_type"],
                "parameters": row["parameters"] if row["parameters"] else {},
                "current_score": float(row["current_score"]),
                "strategy_hash": row["strategy_hash"],
                "discovery_symbol": row["discovery_symbol"],
                "discovery_start_time": row["discovery_start_time"].isoformat() if row["discovery_start_time"] else None,
                "discovery_end_time": row["discovery_end_time"].isoformat() if row["discovery_end_time"] else None,
                "first_discovered_at": row["first_discovered_at"].isoformat() if row["first_discovered_at"] else None,
                "last_evaluated_at": row["last_evaluated_at"].isoformat() if row["last_evaluated_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            strategies.append(strategy)
        
        return strategies
    
    finally:
        conn.close()


def fetch_strategy_metrics() -> Dict:
    """Fetch strategy metrics and aggregated data."""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM Strategies WHERE is_active = TRUE")
        total_strategies = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM Strategies WHERE is_active = TRUE")
        total_symbols = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT strategy_type) FROM Strategies WHERE is_active = TRUE")
        total_strategy_types = cursor.fetchone()[0]
        
        # Score statistics
        cursor.execute("SELECT AVG(current_score), MAX(current_score), MIN(current_score) FROM Strategies WHERE is_active = TRUE")
        score_stats = cursor.fetchone()
        avg_score, max_score, min_score = score_stats
        
        # Recent strategies (last 24 hours)
        yesterday = datetime.now() - timedelta(days=1)
        cursor.execute("SELECT COUNT(*) FROM Strategies WHERE is_active = TRUE AND created_at > %s", (yesterday,))
        recent_strategies = cursor.fetchone()[0]
        
        # Top strategy types by count
        cursor.execute("""
            SELECT strategy_type, COUNT(*) as count, AVG(current_score) as avg_score
            FROM Strategies 
            WHERE is_active = TRUE 
            GROUP BY strategy_type 
            ORDER BY count DESC 
            LIMIT 10
        """)
        strategy_type_counts = cursor.fetchall()
        
        # Top symbols by count
        cursor.execute("""
            SELECT symbol, COUNT(*) as count, AVG(current_score) as avg_score
            FROM Strategies 
            WHERE is_active = TRUE 
            GROUP BY symbol 
            ORDER BY count DESC 
            LIMIT 10
        """)
        symbol_counts = cursor.fetchall()
        
        return {
            "total_strategies": total_strategies or 0,
            "total_symbols": total_symbols or 0,
            "total_strategy_types": total_strategy_types or 0,
            "avg_score": float(avg_score) if avg_score else 0.0,
            "max_score": float(max_score) if max_score else 0.0,
            "min_score": float(min_score) if min_score else 0.0,
            "recent_strategies_24h": recent_strategies or 0,
            "top_strategy_types": [
                {
                    "strategy_type": row[0],
                    "count": row[1],
                    "avg_score": float(row[2])
                } for row in strategy_type_counts
            ],
            "top_symbols": [
                {
                    "symbol": row[0],
                    "count": row[1],
                    "avg_score": float(row[2])
                } for row in symbol_counts
            ]
        }
    
    finally:
        conn.close()


# API Routes

@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


@app.route("/api/strategies", methods=["GET"])
def get_strategies():
    """Get all strategies with optional filtering."""
    try:
        # Get query parameters
        symbol = request.args.get("symbol")
        strategy_type = request.args.get("strategy_type")
        limit = request.args.get("limit", type=int)
        min_score = request.args.get("min_score", type=float)
        
        # Fetch strategies
        strategies = fetch_all_strategies()
        
        # Apply filters
        if symbol:
            strategies = [s for s in strategies if s["symbol"].lower() == symbol.lower()]
        
        if strategy_type:
            strategies = [s for s in strategies if s["strategy_type"].lower() == strategy_type.lower()]
        
        if min_score is not None:
            strategies = [s for s in strategies if s["current_score"] >= min_score]
        
        if limit:
            strategies = strategies[:limit]
        
        return jsonify({
            "strategies": strategies,
            "count": len(strategies),
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"Error fetching strategies: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategies/<strategy_id>", methods=["GET"])
def get_strategy_by_id(strategy_id):
    """Get a specific strategy by ID."""
    try:
        strategies = fetch_all_strategies()
        
        strategy = next((s for s in strategies if s["strategy_id"] == strategy_id), None)
        
        if not strategy:
            return jsonify({"error": "Strategy not found"}), 404
        
        return jsonify(strategy)
    
    except Exception as e:
        logging.error(f"Error fetching strategy {strategy_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Get strategy metrics and aggregated data."""
    try:
        metrics = fetch_strategy_metrics()
        
        return jsonify({
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"Error fetching metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/symbols", methods=["GET"])
def get_symbols():
    """Get all unique symbols."""
    try:
        strategies = fetch_all_strategies()
        
        symbols = sorted(list(set(s["symbol"] for s in strategies)))
        
        return jsonify({
            "symbols": symbols,
            "count": len(symbols),
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"Error fetching symbols: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy-types", methods=["GET"])
def get_strategy_types():
    """Get all unique strategy types."""
    try:
        strategies = fetch_all_strategies()
        
        strategy_types = sorted(list(set(s["strategy_type"] for s in strategies)))
        
        return jsonify({
            "strategy_types": strategy_types,
            "count": len(strategy_types),
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"Error fetching strategy types: {e}")
        return jsonify({"error": str(e)}), 500


def main(argv):
    """Main function to start the API server."""
    global DB_CONFIG
    
    # Parse flags
    absl_app.parse_flags_with_usage(argv)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Validate required configuration
    if not FLAGS.postgres_password:
        logging.error("PostgreSQL password is required")
        return 1
    
    # Store database configuration
    DB_CONFIG = {
        "host": FLAGS.postgres_host,
        "port": FLAGS.postgres_port,
        "database": FLAGS.postgres_database,
        "username": FLAGS.postgres_username,
        "password": FLAGS.postgres_password,
    }
    
    # Test database connection
    try:
        test_conn = get_db_connection()
        test_conn.close()
        logging.info("Database connection test successful")
    except Exception as e:
        logging.error(f"Database connection test failed: {e}")
        return 1
    
    # Start Flask server
    logging.info(f"Starting Strategy Monitor API on {FLAGS.api_host}:{FLAGS.api_port}")
    app.run(
        host=FLAGS.api_host,
        port=FLAGS.api_port,
        debug=False,
        threaded=True
    )


if __name__ == "__main__":
    absl_app.run(main)
