"""
Portfolio REST API — RMM Level 2.

Provides endpoints for portfolio state, positions, balance,
risk metrics, trade validation, position management, and
portfolio history for equity curve visualization.
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request DTOs ---


class TradeValidation(BaseModel):
    instrument: str = Field(..., description="Trading instrument symbol")
    side: str = Field(..., description="BUY or SELL", pattern="^(BUY|SELL)$")
    size: float = Field(..., gt=0, description="Trade size")


class PositionRequest(BaseModel):
    symbol: str = Field(..., description="Trading instrument symbol")
    side: str = Field(..., description="LONG or SHORT", pattern="^(LONG|SHORT)$")
    quantity: float = Field(..., gt=0, description="Position quantity")
    entry_price: float = Field(..., gt=0, description="Entry price per unit")


class TradeEvent(BaseModel):
    symbol: str = Field(..., description="Trading instrument symbol")
    side: str = Field(..., description="BUY or SELL", pattern="^(BUY|SELL)$")
    quantity: float = Field(..., gt=0, description="Trade quantity")
    price: float = Field(..., gt=0, description="Execution price")
    signal_id: Optional[str] = Field(None, description="Associated signal ID")


# --- Helpers ---


def _serialize_position(row) -> dict:
    """Convert a DB position row to a serializable dict."""
    item = dict(row)
    if item.get("updated_at"):
        item["updated_at"] = item["updated_at"].isoformat()
    item["quantity"] = float(item["quantity"])
    item["avg_entry_price"] = float(item["avg_entry_price"])
    item["unrealized_pnl"] = float(item["unrealized_pnl"])
    return item


async def _update_position_from_trade(
    conn, symbol: str, trade_side: str, quantity: float, price: float
):
    """Update paper_portfolio when a trade executes.

    For BUY trades: increase long position (or reduce short).
    For SELL trades: increase short position (or reduce long).
    """
    existing = await conn.fetchrow(
        "SELECT quantity, avg_entry_price, side FROM paper_portfolio WHERE symbol = $1",
        symbol,
    )

    if existing is None:
        pos_side = "LONG" if trade_side == "BUY" else "SHORT"
        await conn.execute(
            """INSERT INTO paper_portfolio (symbol, quantity, avg_entry_price, unrealized_pnl, side)
               VALUES ($1, $2, $3, 0, $4)""",
            symbol,
            quantity,
            price,
            pos_side,
        )
        return

    current_qty = float(existing["quantity"])
    current_avg = float(existing["avg_entry_price"])
    current_side = existing["side"]

    increases_position = (current_side == "LONG" and trade_side == "BUY") or (
        current_side == "SHORT" and trade_side == "SELL"
    )

    if increases_position:
        new_qty = current_qty + quantity
        new_avg = ((current_avg * current_qty) + (price * quantity)) / new_qty
        await conn.execute(
            """UPDATE paper_portfolio
               SET quantity = $2, avg_entry_price = $3, updated_at = NOW()
               WHERE symbol = $1""",
            symbol,
            new_qty,
            new_avg,
        )
    else:
        if quantity >= current_qty:
            remaining = quantity - current_qty
            if remaining > 0:
                new_side = "LONG" if current_side == "SHORT" else "SHORT"
                await conn.execute(
                    """UPDATE paper_portfolio
                       SET quantity = $2, avg_entry_price = $3, side = $4,
                           unrealized_pnl = 0, updated_at = NOW()
                       WHERE symbol = $1""",
                    symbol,
                    remaining,
                    price,
                    new_side,
                )
            else:
                await conn.execute(
                    """UPDATE paper_portfolio
                       SET quantity = 0, unrealized_pnl = 0, updated_at = NOW()
                       WHERE symbol = $1""",
                    symbol,
                )
        else:
            new_qty = current_qty - quantity
            await conn.execute(
                """UPDATE paper_portfolio
                   SET quantity = $2, updated_at = NOW()
                   WHERE symbol = $1""",
                symbol,
                new_qty,
            )


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Portfolio API FastAPI application."""
    app = FastAPI(
        title="Portfolio API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/portfolio",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("portfolio-api", check_deps))

    # --- Portfolio state ---

    @app.get("/state", tags=["Portfolio"])
    async def get_state():
        """Get current portfolio state with all positions and aggregate metrics."""
        query = """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl, side, updated_at
            FROM paper_portfolio
            WHERE quantity != 0
            ORDER BY symbol
        """
        trades_query = """
            SELECT COUNT(*) as total_trades,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                   SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades,
                   SUM(pnl) as total_realized_pnl
            FROM paper_trades
            WHERE status = 'CLOSED'
        """
        async with db_pool.acquire() as conn:
            positions = await conn.fetch(query)
            trade_stats = await conn.fetchrow(trades_query)

        pos_list = [_serialize_position(row) for row in positions]
        total_unrealized = sum(p["unrealized_pnl"] for p in pos_list)

        stats = dict(trade_stats) if trade_stats else {}
        if stats.get("total_realized_pnl") is not None:
            stats["total_realized_pnl"] = float(stats["total_realized_pnl"])

        return success_response(
            {
                "positions": pos_list,
                "position_count": len(pos_list),
                "total_unrealized_pnl": total_unrealized,
                "trade_stats": stats,
            },
            "portfolio_state",
        )

    # --- Positions ---

    @app.get("/positions", tags=["Positions"])
    async def list_positions():
        """List all open positions."""
        query = """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl, side, updated_at
            FROM paper_portfolio
            WHERE quantity != 0
            ORDER BY symbol
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        items = [_serialize_position(row) for row in rows]
        return collection_response(items, "position")

    @app.get("/positions/{instrument}", tags=["Positions"])
    async def get_position(instrument: str):
        """Get position for a specific instrument."""
        query = """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl, side, updated_at
            FROM paper_portfolio
            WHERE symbol = $1
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, instrument)
        if not row:
            return not_found("Position", instrument)
        return success_response(
            _serialize_position(row), "position", resource_id=instrument
        )

    @app.post("/positions", tags=["Positions"], status_code=201)
    async def create_or_update_position(body: PositionRequest):
        """Record a new position or update an existing one.

        If a position already exists for the symbol with the same side,
        the quantity and average entry price are updated using a weighted
        average. If the side differs, the position is replaced.
        """
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT quantity, avg_entry_price, side FROM paper_portfolio WHERE symbol = $1",
                body.symbol,
            )

            if existing is None:
                await conn.execute(
                    """INSERT INTO paper_portfolio
                       (symbol, quantity, avg_entry_price, unrealized_pnl, side)
                       VALUES ($1, $2, $3, 0, $4)""",
                    body.symbol,
                    body.quantity,
                    body.entry_price,
                    body.side,
                )
            else:
                current_qty = float(existing["quantity"])
                current_avg = float(existing["avg_entry_price"])
                current_side = existing["side"]

                if current_side == body.side and current_qty > 0:
                    new_qty = current_qty + body.quantity
                    new_avg = (
                        (current_avg * current_qty) + (body.entry_price * body.quantity)
                    ) / new_qty
                    await conn.execute(
                        """UPDATE paper_portfolio
                           SET quantity = $2, avg_entry_price = $3, updated_at = NOW()
                           WHERE symbol = $1""",
                        body.symbol,
                        new_qty,
                        new_avg,
                    )
                else:
                    await conn.execute(
                        """UPDATE paper_portfolio
                           SET quantity = $2, avg_entry_price = $3, side = $4,
                               unrealized_pnl = 0, updated_at = NOW()
                           WHERE symbol = $1""",
                        body.symbol,
                        body.quantity,
                        body.entry_price,
                        body.side,
                    )

            row = await conn.fetchrow(
                """SELECT symbol, quantity, avg_entry_price, unrealized_pnl, side, updated_at
                   FROM paper_portfolio WHERE symbol = $1""",
                body.symbol,
            )

        return success_response(
            _serialize_position(row),
            "position",
            resource_id=body.symbol,
        )

    # --- Trade event handler ---

    @app.post("/trades", tags=["Trades"])
    async def handle_trade_event(body: TradeEvent):
        """Process a trade execution event and update portfolio positions.

        Called when a trade executes. Updates the paper_portfolio and
        records the trade in paper_trades.
        """
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO paper_trades
                   (symbol, side, entry_price, quantity, status, signal_id)
                   VALUES ($1, $2, $3, $4, 'OPEN', $5)""",
                body.symbol,
                body.side,
                body.price,
                body.quantity,
                body.signal_id,
            )

            await _update_position_from_trade(
                conn, body.symbol, body.side, body.quantity, body.price
            )

            row = await conn.fetchrow(
                """SELECT symbol, quantity, avg_entry_price, unrealized_pnl, side, updated_at
                   FROM paper_portfolio WHERE symbol = $1""",
                body.symbol,
            )

        position = _serialize_position(row) if row else None
        return success_response(
            {
                "trade": {
                    "symbol": body.symbol,
                    "side": body.side,
                    "quantity": body.quantity,
                    "price": body.price,
                },
                "position": position,
            },
            "trade_result",
        )

    # --- Portfolio history ---

    @app.get("/history", tags=["Portfolio"])
    async def get_history(
        start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
        end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
        limit: int = Query(90, ge=1, le=365, description="Max snapshots"),
    ):
        """Get daily portfolio value snapshots for equity curve visualization."""
        conditions = []
        params: list = []
        idx = 1

        if start_date:
            conditions.append(f"snapshot_date >= ${idx}")
            params.append(start_date)
            idx += 1
        if end_date:
            conditions.append(f"snapshot_date <= ${idx}")
            params.append(end_date)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        query = f"""
            SELECT snapshot_date, total_equity, total_unrealized_pnl,
                   total_realized_pnl, position_count
            FROM portfolio_snapshots
            {where}
            ORDER BY snapshot_date DESC
            LIMIT ${idx}
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            item = dict(row)
            item["snapshot_date"] = item["snapshot_date"].isoformat()
            item["total_equity"] = float(item["total_equity"])
            item["total_unrealized_pnl"] = float(item["total_unrealized_pnl"])
            item["total_realized_pnl"] = float(item["total_realized_pnl"])
            items.append(item)

        items.reverse()
        return collection_response(items, "portfolio_snapshot")

    # --- Snapshot creation (internal) ---

    @app.post("/snapshots", tags=["Portfolio"])
    async def create_snapshot():
        """Take a daily portfolio snapshot for equity curve tracking.

        Captures current positions, unrealized P&L, and realized P&L
        into a single row. Intended to be called by a daily cron job.
        """
        async with db_pool.acquire() as conn:
            positions = await conn.fetch(
                """SELECT symbol, quantity, avg_entry_price, unrealized_pnl, side
                   FROM paper_portfolio WHERE quantity != 0"""
            )
            realized_row = await conn.fetchrow(
                """SELECT COALESCE(SUM(pnl), 0) as total_realized
                   FROM paper_trades WHERE status = 'CLOSED'"""
            )

            total_unrealized = sum(float(r["unrealized_pnl"]) for r in positions)
            total_realized = float(realized_row["total_realized"])
            total_equity = total_realized + total_unrealized

            pos_json = [
                {
                    "symbol": r["symbol"],
                    "quantity": float(r["quantity"]),
                    "avg_entry_price": float(r["avg_entry_price"]),
                    "unrealized_pnl": float(r["unrealized_pnl"]),
                    "side": r["side"],
                }
                for r in positions
            ]

            today = date.today()
            await conn.execute(
                """INSERT INTO portfolio_snapshots
                   (snapshot_date, total_equity, total_unrealized_pnl,
                    total_realized_pnl, position_count, positions)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (snapshot_date)
                   DO UPDATE SET total_equity = $2, total_unrealized_pnl = $3,
                                 total_realized_pnl = $4, position_count = $5,
                                 positions = $6""",
                today,
                total_equity,
                total_unrealized,
                total_realized,
                len(positions),
                json.dumps(pos_json),
            )

        return success_response(
            {
                "snapshot_date": today.isoformat(),
                "total_equity": total_equity,
                "total_unrealized_pnl": total_unrealized,
                "total_realized_pnl": total_realized,
                "position_count": len(positions),
            },
            "portfolio_snapshot",
        )

    # --- Balance ---

    @app.get("/balance", tags=["Portfolio"])
    async def get_balance():
        """Get account balance (total realized + unrealized P&L)."""
        query = """
            SELECT COALESCE(SUM(unrealized_pnl), 0) as total_unrealized
            FROM paper_portfolio
        """
        trades_query = """
            SELECT COALESCE(SUM(pnl), 0) as total_realized
            FROM paper_trades
            WHERE status = 'CLOSED'
        """
        async with db_pool.acquire() as conn:
            unrealized_row = await conn.fetchrow(query)
            realized_row = await conn.fetchrow(trades_query)

        total_unrealized = float(unrealized_row["total_unrealized"])
        total_realized = float(realized_row["total_realized"])
        return success_response(
            {
                "total_realized_pnl": total_realized,
                "total_unrealized_pnl": total_unrealized,
                "total_equity": total_realized + total_unrealized,
            },
            "balance",
        )

    # --- Risk ---

    @app.get("/risk", tags=["Risk"])
    async def get_risk():
        """Get risk metrics across all positions."""
        query = """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl, side
            FROM paper_portfolio
            WHERE quantity != 0
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        positions = [dict(row) for row in rows]
        total_exposure = sum(
            abs(float(p["quantity"]) * float(p["avg_entry_price"])) for p in positions
        )
        position_count = len(positions)

        long_exposure = sum(
            abs(float(p["quantity"]) * float(p["avg_entry_price"]))
            for p in positions
            if p.get("side") == "LONG"
        )
        short_exposure = sum(
            abs(float(p["quantity"]) * float(p["avg_entry_price"]))
            for p in positions
            if p.get("side") == "SHORT"
        )

        concentrations = {}
        for p in positions:
            exposure = abs(float(p["quantity"]) * float(p["avg_entry_price"]))
            concentrations[p["symbol"]] = (
                round(exposure / total_exposure, 4) if total_exposure > 0 else 0
            )

        return success_response(
            {
                "total_exposure": total_exposure,
                "long_exposure": long_exposure,
                "short_exposure": short_exposure,
                "net_exposure": long_exposure - short_exposure,
                "position_count": position_count,
                "concentration": concentrations,
            },
            "risk_metrics",
        )

    # --- Validate ---

    @app.post("/validate", tags=["Risk"])
    async def validate_trade(body: TradeValidation):
        """Validate a proposed trade against risk limits."""
        errors: List[str] = []

        if body.size <= 0:
            errors.append("size must be positive")

        if body.side == "SELL":
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT quantity FROM paper_portfolio WHERE symbol = $1",
                    body.instrument,
                )
            if not row or float(row["quantity"]) < body.size:
                errors.append(
                    f"Insufficient position in {body.instrument} for SELL of {body.size}"
                )

        return success_response(
            {"valid": len(errors) == 0, "errors": errors},
            "trade_validation",
        )

    return app
