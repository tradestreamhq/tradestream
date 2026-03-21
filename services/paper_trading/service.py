"""Paper Trading evaluation service.

Provides HTTP endpoints for simulating trades from agent signals,
tracking hypothetical P&L without executing real trades.
"""

import asyncio
import json
import threading
from typing import Optional

from absl import logging
from flask import Flask, jsonify, request

from services.paper_trading.engine import PaperTradingEngine
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
    pg_client: PostgresClient,
    market_mcp_url: str,
    signal_mcp_url: str,
    event_loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Flask:
    """Create the Flask application with all paper trading endpoints.

    Args:
        pg_client: Async PostgreSQL client (pool bound to *event_loop*).
        market_mcp_url: URL of the Market MCP service.
        signal_mcp_url: URL of the Signal MCP service.
        event_loop: The event loop that owns the asyncpg pool.  When
            ``None`` a new background loop is created automatically.
    """
    app = Flask(__name__)
    flask_auth_middleware(app)

    # Use the caller-supplied loop or spin up a dedicated background loop.
    # The asyncpg pool is bound to the loop where ``connect()`` was awaited,
    # so all coroutines must be dispatched to that same loop.
    if event_loop is None:
        event_loop = asyncio.new_event_loop()
        _thread = threading.Thread(
            target=event_loop.run_forever, daemon=True, name="paper-trading-loop"
        )
        _thread.start()

    def run_async(coro):
        """Run an async coroutine from a sync Flask handler.

        Dispatches the coroutine to the dedicated background event loop
        that owns the asyncpg connection pool, then blocks until the
        result is ready.  This is safe to call from any Flask worker thread.
        """
        future = asyncio.run_coroutine_threadsafe(coro, event_loop)
        return future.result()

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

    # ---- Paper Trading Mode endpoints (/api/v1/paper-trading) ----

    engine = PaperTradingEngine(pg_client, market_mcp_url)

    @app.route("/api/v1/paper-trading/start", methods=["POST"])
    def start_session():
        """Start a new paper trading session.

        Request body (optional):
            starting_balance: Initial virtual balance (default 100000.0)
        """
        data = request.get_json(silent=True) or {}
        starting_balance = float(data.get("starting_balance", 100000.0))

        if starting_balance <= 0:
            return jsonify({"error": "starting_balance must be positive"}), 400

        try:
            session = run_async(engine.start_session(starting_balance))
            return jsonify(session), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 409
        except Exception as e:
            logging.error("Failed to start paper trading session: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/paper-trading/stop", methods=["POST"])
    def stop_session():
        """Stop an active paper trading session.

        Request body:
            session_id: UUID of the session to stop
        """
        data = request.get_json()
        if not data or not data.get("session_id"):
            return jsonify({"error": "session_id is required"}), 400

        try:
            session = run_async(engine.stop_session(data["session_id"]))
            return jsonify(session)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logging.error("Failed to stop paper trading session: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/paper-trading/portfolio", methods=["GET"])
    def get_session_portfolio():
        """Get portfolio for a paper trading session.

        Query params:
            session_id: UUID of the session
        """
        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"error": "session_id query param is required"}), 400

        try:
            portfolio = run_async(engine.get_session_portfolio(session_id))
            return jsonify(portfolio)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            logging.error("Failed to get session portfolio: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/paper-trading/trades", methods=["GET"])
    def get_session_trades():
        """Get trades for a paper trading session.

        Query params:
            session_id: UUID of the session (required)
            symbol: Filter by symbol
            status: Filter by status (OPEN/CLOSED)
            limit: Max results (default 50)
        """
        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"error": "session_id query param is required"}), 400

        symbol = request.args.get("symbol")
        status = request.args.get("status")
        limit = int(request.args.get("limit", 50))

        try:
            result = run_async(
                engine.get_session_trades(
                    session_id, symbol=symbol, status=status, limit=limit
                )
            )
            return jsonify(result)
        except Exception as e:
            logging.error("Failed to get session trades: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/paper-trading/performance", methods=["GET"])
    def get_performance_comparison():
        """Compare paper trading performance against live trades.

        Query params:
            session_id: UUID of the session to compare
        """
        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"error": "session_id query param is required"}), 400

        try:
            comparison = run_async(engine.get_performance_comparison(session_id))
            return jsonify(comparison)
        except Exception as e:
            logging.error("Failed to get performance comparison: %s", e)
            return jsonify({"error": str(e)}), 500

    return app
