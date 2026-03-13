"""Paper Trading Engine — wraps execution in simulation mode.

Manages paper trading sessions with virtual portfolios and tracks
simulated trades separately from live execution.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from absl import logging

from services.paper_trading.postgres_client import PostgresClient
from services.shared.mcp_client import call_mcp_tool


class PaperTradingEngine:
    """Simulation engine that wraps trade execution in paper mode.

    Manages session lifecycle (start/stop), executes simulated trades
    against a virtual balance, and provides performance metrics.
    """

    def __init__(
        self,
        pg_client: PostgresClient,
        market_mcp_url: str,
    ):
        self._pg = pg_client
        self._market_mcp_url = market_mcp_url

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Fetch the latest price for a symbol from market-mcp."""
        result = call_mcp_tool(
            "get_latest_price",
            {"symbol": symbol},
            self._market_mcp_url,
            timeout=10,
        )
        if not isinstance(result, dict):
            return None
        price = result.get("price") or result.get("close")
        return float(price) if price is not None else None

    async def start_session(
        self, starting_balance: float = 100000.0
    ) -> Dict[str, Any]:
        """Start a new paper trading session with the given balance.

        Only one session can be ACTIVE at a time.
        """
        active = await self._pg.get_active_session()
        if active is not None:
            raise ValueError(
                f"Session {active['session_id']} is already active. "
                "Stop it before starting a new one."
            )
        return await self._pg.create_session(starting_balance)

    async def stop_session(self, session_id: str) -> Dict[str, Any]:
        """Stop an active paper trading session."""
        session = await self._pg.stop_session(session_id)
        if session is None:
            raise ValueError(
                f"Session '{session_id}' not found or already stopped."
            )
        return session

    async def execute_paper_trade(
        self,
        session_id: str,
        symbol: str,
        side: str,
        quantity: float,
        signal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a simulated trade within a session.

        Validates balance, fetches market price, and records the trade.
        """
        session = await self._pg.get_session(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found.")
        if session["status"] != "ACTIVE":
            raise ValueError("Cannot trade on a stopped session.")

        price = self._get_current_price(symbol)
        if price is None:
            raise RuntimeError(f"Could not fetch price for {symbol}")

        # Check sufficient balance for BUY
        cost = price * quantity
        if side == "BUY" and cost > float(session["current_balance"]):
            raise ValueError(
                f"Insufficient balance. Need {cost:.2f}, "
                f"have {float(session['current_balance']):.2f}"
            )

        trade = await self._pg.execute_session_trade(
            session_id=session_id,
            signal_id=signal_id,
            symbol=symbol,
            side=side,
            entry_price=price,
            quantity=quantity,
        )
        return trade

    async def get_session_portfolio(
        self, session_id: str
    ) -> Dict[str, Any]:
        """Get portfolio state for a session including updated P&L."""
        session = await self._pg.get_session(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found.")

        positions = await self._pg.get_session_portfolio(session_id)

        # Update unrealized P&L with current prices
        for pos in positions:
            price = self._get_current_price(pos["symbol"])
            if price is not None:
                pos["current_price"] = price
                pos["unrealized_pnl"] = round(
                    pos["quantity"] * (price - pos["avg_entry_price"]), 8
                )

        total_unrealized = sum(p.get("unrealized_pnl", 0) for p in positions)
        return {
            "session_id": session["session_id"],
            "starting_balance": session["starting_balance"],
            "current_balance": session["current_balance"],
            "total_realized_pnl": session["total_realized_pnl"],
            "total_unrealized_pnl": total_unrealized,
            "total_equity": session["current_balance"] + total_unrealized,
            "positions": positions,
        }

    async def get_session_trades(
        self,
        session_id: str,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get trades for a specific session."""
        trades = await self._pg.get_session_trades(
            session_id=session_id, symbol=symbol, status=status, limit=limit
        )
        return {"session_id": session_id, "trades": trades, "count": len(trades)}

    async def get_performance_comparison(
        self, session_id: str
    ) -> Dict[str, Any]:
        """Compare paper trading performance against live metrics.

        Returns paper session stats and live stats side-by-side.
        """
        paper_stats = await self._pg.get_session_stats(session_id)
        live_stats = await self._pg.get_live_trade_stats()

        return {
            "session_id": session_id,
            "paper": paper_stats,
            "live": live_stats,
            "comparison": _compute_comparison(paper_stats, live_stats),
        }


def _compute_comparison(
    paper: Dict[str, Any], live: Dict[str, Any]
) -> Dict[str, Any]:
    """Compute delta metrics between paper and live performance."""
    paper_return = paper.get("return_pct", 0.0)
    live_return = live.get("return_pct", 0.0)

    return {
        "return_pct_delta": round(paper_return - live_return, 4),
        "win_rate_delta": round(
            paper.get("win_rate", 0.0) - live.get("win_rate", 0.0), 2
        ),
        "avg_pnl_delta": round(
            paper.get("avg_pnl", 0.0) - live.get("avg_pnl", 0.0), 8
        ),
        "total_trades_delta": (
            paper.get("total_trades", 0) - live.get("total_trades", 0)
        ),
    }
