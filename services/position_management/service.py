"""Position Management service.

Provides HTTP endpoints for managing positions across strategies,
with real-time P&L calculation and position lifecycle tracking.
"""

import asyncio
import threading
from typing import Optional

from absl import logging
from flask import Flask, jsonify, request

from services.position_management.position_management import classify_asset_class
from services.position_management.postgres_client import PostgresClient
from services.shared.auth import flask_auth_middleware
from services.shared.mcp_client import call_mcp_tool


def _get_current_price(symbol: str, market_mcp_url: str) -> Optional[float]:
    """Fetch the latest price for a symbol from market-mcp."""
    result = call_mcp_tool(
        "get_latest_price", {"symbol": symbol}, market_mcp_url, timeout=10
    )
    if not isinstance(result, dict):
        return None
    price = result.get("price") or result.get("close")
    if price is not None:
        return float(price)
    return None


def create_app(
    pg_client: PostgresClient,
    market_mcp_url: str,
    event_loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Flask:
    """Create the Flask application with position management endpoints."""
    app = Flask(__name__)
    flask_auth_middleware(app)

    if event_loop is None:
        event_loop = asyncio.new_event_loop()
        _thread = threading.Thread(
            target=event_loop.run_forever,
            daemon=True,
            name="position-management-loop",
        )
        _thread.start()

    def run_async(coro):
        future = asyncio.run_coroutine_threadsafe(coro, event_loop)
        return future.result()

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "service": "position-management"})

    @app.route("/positions", methods=["GET"])
    def list_positions():
        """Query positions with optional filters.

        Query params: symbol, strategy, status, asset_class, limit
        """
        try:
            positions = run_async(
                pg_client.get_positions(
                    symbol=request.args.get("symbol"),
                    strategy_name=request.args.get("strategy"),
                    status=request.args.get("status"),
                    asset_class=request.args.get("asset_class"),
                    limit=int(request.args.get("limit", 100)),
                )
            )
            return jsonify({"positions": positions, "count": len(positions)})
        except Exception as e:
            logging.error("Failed to list positions: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/positions/<position_id>", methods=["GET"])
    def get_position(position_id):
        """Get a single position by ID."""
        try:
            position = run_async(pg_client.get_position(position_id))
            if not position:
                return jsonify({"error": "Position not found"}), 404
            return jsonify(position)
        except Exception as e:
            logging.error("Failed to get position %s: %s", position_id, e)
            return jsonify({"error": str(e)}), 500

    @app.route("/positions", methods=["POST"])
    def open_position():
        """Open a new managed position.

        Request body:
            symbol: Trading symbol (required)
            side: LONG or SHORT (required)
            quantity: Position size (required)
            entry_price: Entry price (required)
            strategy_name: Strategy that opened this position
            signal_id: Originating signal ID
            stop_loss: Stop loss price
            take_profit: Take profit price
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        symbol = data.get("symbol")
        side = data.get("side")
        quantity = data.get("quantity")
        entry_price = data.get("entry_price")

        if not all([symbol, side, quantity, entry_price]):
            return (
                jsonify(
                    {"error": "symbol, side, quantity, and entry_price are required"}
                ),
                400,
            )

        if side not in ("LONG", "SHORT"):
            return jsonify({"error": "side must be LONG or SHORT"}), 400

        try:
            asset_class = classify_asset_class(symbol)
            result = run_async(
                pg_client.open_position(
                    symbol=symbol,
                    side=side,
                    quantity=float(quantity),
                    entry_price=float(entry_price),
                    strategy_name=data.get("strategy_name"),
                    asset_class=asset_class,
                    signal_id=data.get("signal_id"),
                    stop_loss=(
                        float(data["stop_loss"]) if data.get("stop_loss") else None
                    ),
                    take_profit=(
                        float(data["take_profit"]) if data.get("take_profit") else None
                    ),
                )
            )
            return jsonify(result), 201
        except Exception as e:
            logging.error("Failed to open position: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/positions/<position_id>/close", methods=["POST"])
    def close_position(position_id):
        """Close or partially close a position.

        Request body:
            exit_price: Exit price (required)
            quantity: Quantity to close (optional, defaults to full close)
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        exit_price = data.get("exit_price")
        if exit_price is None:
            return jsonify({"error": "exit_price is required"}), 400

        try:
            result = run_async(
                pg_client.close_position(
                    position_id=position_id,
                    exit_price=float(exit_price),
                    close_quantity=(
                        float(data["quantity"]) if data.get("quantity") else None
                    ),
                )
            )
            if not result:
                return jsonify({"error": "Position not found or already closed"}), 404
            return jsonify(result)
        except Exception as e:
            logging.error("Failed to close position %s: %s", position_id, e)
            return jsonify({"error": str(e)}), 500

    @app.route("/positions/<position_id>/mark", methods=["POST"])
    def mark_position(position_id):
        """Update market price for a position (mark-to-market).

        Request body:
            current_price: Latest market price (required)
        """
        data = request.get_json()
        if not data or data.get("current_price") is None:
            return jsonify({"error": "current_price is required"}), 400

        try:
            run_async(
                pg_client.update_market_price(position_id, float(data["current_price"]))
            )
            position = run_async(pg_client.get_position(position_id))
            if not position:
                return jsonify({"error": "Position not found"}), 404
            return jsonify(position)
        except Exception as e:
            logging.error("Failed to mark position %s: %s", position_id, e)
            return jsonify({"error": str(e)}), 500

    @app.route("/positions/summary", methods=["GET"])
    def position_summary():
        """Get aggregated position stats.

        Query params: group_by (strategy|asset_class, default: strategy)
        """
        try:
            group_by = request.args.get("group_by", "strategy")
            if group_by not in ("strategy", "asset_class"):
                return (
                    jsonify({"error": "group_by must be strategy or asset_class"}),
                    400,
                )

            summary = run_async(pg_client.get_position_summary(group_by=group_by))
            return jsonify({"summary": summary, "group_by": group_by})
        except Exception as e:
            logging.error("Failed to get position summary: %s", e)
            return jsonify({"error": str(e)}), 500

    return app
