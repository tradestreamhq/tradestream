"""Paper Trading evaluation service.

Provides HTTP endpoints for simulating trades from agent signals,
tracking hypothetical P&L without executing real trades.
"""

import asyncio
import json
from typing import Optional

from absl import logging
from flask import Flask, jsonify, request

from services.paper_trading.postgres_client import PostgresClient
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
    pg_client: PostgresClient, market_mcp_url: str, signal_mcp_url: str
) -> Flask:
    """Create the Flask application with all paper trading endpoints."""
    app = Flask(__name__)
    flask_auth_middleware(app)

    def run_async(coro):
        """Run an async coroutine from a sync Flask handler.

        Uses asyncio.run() per call to avoid sharing a single event loop
        across Flask's request-handling threads.
        """
        return asyncio.run(coro)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "service": "paper-trading"})

    @app.route("/paper/execute", methods=["POST"])
    def execute_trade():
        """Simulate a trade from a signal.

        Request body:
            signal_id: UUID of the signal to trade on
            quantity: Amount to trade
            reasoning: Optional reasoning for the trade decision
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        signal_id = data.get("signal_id")
        quantity = data.get("quantity")
        reasoning = data.get("reasoning", "Paper trade execution")

        if not signal_id:
            return jsonify({"error": "signal_id is required"}), 400
        if not quantity or float(quantity) <= 0:
            return jsonify({"error": "quantity must be positive"}), 400

        # Fetch signal details from signal-mcp
        signals = call_mcp_tool(
            "get_recent_signals",
            {"limit": 50},
            signal_mcp_url,
            timeout=10,
        )

        signal_data = None
        if isinstance(signals, list):
            for s in signals:
                if s.get("signal_id") == signal_id:
                    signal_data = s
                    break

        if not signal_data:
            return jsonify({"error": "Signal not found"}), 404

        symbol = signal_data.get("symbol", "")
        action = signal_data.get("action", "")

        if action not in ("BUY", "SELL"):
            return jsonify({"error": f"Cannot trade on {action} signal"}), 400

        # Get current market price for entry
        price = _get_current_price(symbol, market_mcp_url)
        if price is None:
            return jsonify({"error": f"Could not get price for {symbol}"}), 502

        try:
            trade = run_async(
                pg_client.execute_trade(
                    signal_id=signal_id,
                    symbol=symbol,
                    side=action,
                    entry_price=price,
                    quantity=float(quantity),
                )
            )

            # Log decision to agent_decisions
            run_async(
                pg_client.log_decision(
                    signal_id=signal_id,
                    reasoning=reasoning,
                    action=action,
                )
            )

            return jsonify(trade), 201
        except Exception as e:
            logging.error("Failed to execute paper trade: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/paper/portfolio", methods=["GET"])
    def get_portfolio():
        """Get current paper portfolio positions with unrealized P&L."""
        try:
            positions = run_async(pg_client.get_portfolio())

            # Update unrealized P&L with current prices
            for pos in positions:
                price = _get_current_price(pos["symbol"], market_mcp_url)
                if price is not None:
                    run_async(pg_client.update_unrealized_pnl(pos["symbol"], price))
                    pos["current_price"] = price
                    pos["unrealized_pnl"] = round(
                        pos["quantity"] * (price - pos["avg_entry_price"]), 8
                    )

            return jsonify({"positions": positions})
        except Exception as e:
            logging.error("Failed to get portfolio: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/paper/trades", methods=["GET"])
    def get_trades():
        """Get paper trades with optional filters.

        Query params:
            symbol: Filter by symbol
            status: Filter by status (OPEN/CLOSED)
            limit: Max results (default 50)
        """
        symbol = request.args.get("symbol")
        status = request.args.get("status")
        limit = int(request.args.get("limit", 50))

        try:
            trades = run_async(
                pg_client.get_trades(symbol=symbol, status=status, limit=limit)
            )
            return jsonify({"trades": trades, "count": len(trades)})
        except Exception as e:
            logging.error("Failed to get trades: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/paper/pnl-summary", methods=["GET"])
    def get_pnl_summary():
        """Get aggregated P&L summary.

        Query params:
            symbol: Optional filter by symbol
        """
        symbol = request.args.get("symbol")

        try:
            summary = run_async(pg_client.get_pnl_summary(symbol=symbol))
            return jsonify(summary)
        except Exception as e:
            logging.error("Failed to get P&L summary: %s", e)
            return jsonify({"error": str(e)}), 500

    return app
