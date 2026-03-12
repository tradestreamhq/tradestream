"""Portfolio State Awareness service.

Provides HTTP endpoints for querying current portfolio state,
risk metrics, and decision validation for the decision agent.
"""

import asyncio
import threading
from typing import Optional

from absl import logging
from flask import Flask, jsonify, request

from services.portfolio_state.portfolio_state import (
    build_portfolio_state,
    compute_balance,
    compute_positions,
    compute_risk_metrics,
    format_portfolio_context,
    validate_decision,
)
from services.portfolio_state.postgres_client import PostgresClient
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


def _fetch_current_prices(
    symbols: list, market_mcp_url: str
) -> dict:
    """Fetch current prices for a list of symbols."""
    prices = {}
    for symbol in symbols:
        price = _get_current_price(symbol, market_mcp_url)
        if price is not None:
            prices[symbol] = price
    return prices


def create_app(
    pg_client: PostgresClient,
    market_mcp_url: str,
    initial_capital: float = 10000.0,
    event_loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Flask:
    """Create the Flask application with portfolio state endpoints.

    Args:
        pg_client: Async PostgreSQL client.
        market_mcp_url: URL of the Market MCP service.
        initial_capital: Starting capital for paper trading account.
        event_loop: The event loop that owns the asyncpg pool.
    """
    app = Flask(__name__)
    flask_auth_middleware(app)

    if event_loop is None:
        event_loop = asyncio.new_event_loop()
        _thread = threading.Thread(
            target=event_loop.run_forever, daemon=True, name="portfolio-state-loop"
        )
        _thread.start()

    def run_async(coro):
        future = asyncio.run_coroutine_threadsafe(coro, event_loop)
        return future.result()

    def _build_state():
        """Build full portfolio state from DB and market data."""
        portfolio_rows = run_async(pg_client.get_positions())
        open_trades = run_async(pg_client.get_open_trades())
        recent_closed = run_async(pg_client.get_recent_closed_trades(limit=10))
        realized_today = run_async(pg_client.get_realized_pnl_today())
        total_realized = run_async(pg_client.get_total_realized_pnl())

        symbols = [r["symbol"] for r in portfolio_rows]
        current_prices = _fetch_current_prices(symbols, market_mcp_url)

        positions = compute_positions(portfolio_rows, open_trades, current_prices)
        balance = compute_balance(
            positions, realized_today, total_realized, initial_capital
        )
        risk_metrics = compute_risk_metrics(positions, balance.total_equity)

        return build_portfolio_state(
            positions=positions,
            balance=balance,
            risk_metrics=risk_metrics,
            recent_trades=recent_closed,
        )

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy", "service": "portfolio-state"})

    @app.route("/portfolio/state", methods=["GET"])
    def get_state():
        """Get full portfolio state including positions, balance, and risk."""
        try:
            state = _build_state()
            return jsonify({
                "balance": {
                    "total_equity": state.balance.total_equity,
                    "available_cash": state.balance.available_cash,
                    "buying_power": state.balance.buying_power,
                    "margin_used": state.balance.margin_used,
                    "margin_available": state.balance.margin_available,
                    "unrealized_pnl": state.balance.unrealized_pnl,
                    "realized_pnl_today": state.balance.realized_pnl_today,
                },
                "positions": [
                    {
                        "symbol": p.symbol,
                        "side": p.side,
                        "quantity": p.quantity,
                        "entry_price": p.entry_price,
                        "current_price": p.current_price,
                        "unrealized_pnl": p.unrealized_pnl,
                        "unrealized_pnl_percent": p.unrealized_pnl_percent,
                        "opened_at": p.opened_at,
                    }
                    for p in state.positions
                ],
                "risk_metrics": {
                    "portfolio_heat": state.risk_metrics.portfolio_heat,
                    "max_position_pct": state.risk_metrics.max_position_pct,
                    "max_position_symbol": state.risk_metrics.max_position_symbol,
                    "num_open_positions": state.risk_metrics.num_open_positions,
                    "sector_exposure": state.risk_metrics.sector_exposure,
                    "daily_drawdown": state.risk_metrics.daily_drawdown,
                },
                "recent_trades": state.recent_trades,
                "as_of": state.as_of,
            })
        except Exception as e:
            logging.error("Failed to get portfolio state: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/portfolio/context", methods=["GET"])
    def get_context():
        """Get formatted portfolio context string for decision prompts."""
        try:
            state = _build_state()
            context = format_portfolio_context(state)
            return jsonify({"context": context, "as_of": state.as_of})
        except Exception as e:
            logging.error("Failed to get portfolio context: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/portfolio/positions", methods=["GET"])
    def get_positions():
        """Get current open positions with live prices."""
        try:
            portfolio_rows = run_async(pg_client.get_positions())
            open_trades = run_async(pg_client.get_open_trades())
            symbols = [r["symbol"] for r in portfolio_rows]
            current_prices = _fetch_current_prices(symbols, market_mcp_url)
            positions = compute_positions(portfolio_rows, open_trades, current_prices)

            return jsonify({
                "positions": [
                    {
                        "symbol": p.symbol,
                        "side": p.side,
                        "quantity": p.quantity,
                        "entry_price": p.entry_price,
                        "current_price": p.current_price,
                        "unrealized_pnl": p.unrealized_pnl,
                        "unrealized_pnl_percent": p.unrealized_pnl_percent,
                        "opened_at": p.opened_at,
                    }
                    for p in positions
                ],
                "count": len(positions),
            })
        except Exception as e:
            logging.error("Failed to get positions: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/portfolio/risk", methods=["GET"])
    def get_risk():
        """Get current risk metrics."""
        try:
            state = _build_state()
            r = state.risk_metrics
            return jsonify({
                "portfolio_heat": r.portfolio_heat,
                "max_position_pct": r.max_position_pct,
                "max_position_symbol": r.max_position_symbol,
                "num_open_positions": r.num_open_positions,
                "sector_exposure": r.sector_exposure,
                "daily_drawdown": r.daily_drawdown,
                "total_equity": state.balance.total_equity,
                "margin_used": state.balance.margin_used,
            })
        except Exception as e:
            logging.error("Failed to get risk metrics: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/portfolio/validate", methods=["POST"])
    def validate():
        """Validate a proposed trade decision against portfolio constraints.

        Request body:
            action: BUY or SELL
            symbol: Trading symbol
            quantity: Amount to trade
            price: Expected execution price
            max_position_pct: Optional max position size (default 2%)
            max_portfolio_heat: Optional max heat (default 50%)
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        action = data.get("action")
        symbol = data.get("symbol")
        quantity = data.get("quantity")
        price = data.get("price")

        if not all([action, symbol, quantity, price]):
            return jsonify({"error": "action, symbol, quantity, and price are required"}), 400

        try:
            state = _build_state()
            result = validate_decision(
                action=action,
                symbol=symbol,
                quantity=float(quantity),
                price=float(price),
                state=state,
                max_position_pct=float(data.get("max_position_pct", 0.02)),
                max_portfolio_heat=float(data.get("max_portfolio_heat", 0.50)),
            )
            return jsonify(result)
        except Exception as e:
            logging.error("Failed to validate decision: %s", e)
            return jsonify({"error": str(e)}), 500

    return app
