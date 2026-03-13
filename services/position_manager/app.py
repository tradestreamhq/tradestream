"""
Position Manager REST API — RMM Level 2.

Provides endpoints for tracking open positions, calculating unrealized PnL,
managing stop-loss/take-profit exits, and viewing closed position history.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query

from services.position_manager.models import CloseRequest, Position, Side
from services.position_manager.pnl import realized_pnl as calc_realized_pnl
from services.position_manager.pnl import (
    should_stop_loss,
    should_take_profit,
    unrealized_pnl as calc_unrealized_pnl,
)
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


def _row_to_dict(row) -> dict:
    """Convert an asyncpg Record to a JSON-safe dict."""
    item = dict(row)
    for ts_field in ("opened_at", "closed_at"):
        if item.get(ts_field):
            item[ts_field] = item[ts_field].isoformat()
    for decimal_field in (
        "entry_price",
        "quantity",
        "stop_loss",
        "take_profit",
        "unrealized_pnl",
        "realized_pnl",
        "current_price",
    ):
        if item.get(decimal_field) is not None:
            item[decimal_field] = float(item[decimal_field])
    if item.get("id"):
        item["id"] = str(item["id"])
    if item.get("strategy_id"):
        item["strategy_id"] = str(item["strategy_id"])
    return item


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Position Manager FastAPI application."""
    app = FastAPI(
        title="Position Manager API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/positions",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("position-manager", check_deps))

    # --- List open positions ---

    @app.get("/", tags=["Positions"])
    async def list_positions(
        strategy_id: Optional[str] = Query(None),
        symbol: Optional[str] = Query(None),
    ):
        """List all open positions, optionally filtered by strategy or symbol."""
        query = """
            SELECT id, strategy_id, symbol, side, entry_price, quantity,
                   stop_loss, take_profit, unrealized_pnl, realized_pnl,
                   status, sizing_method, opened_at, closed_at,
                   close_reason, current_price
            FROM positions
            WHERE status = 'OPEN'
        """
        params = []
        idx = 1
        if strategy_id:
            query += f" AND strategy_id = ${idx}::uuid"
            params.append(strategy_id)
            idx += 1
        if symbol:
            query += f" AND symbol = ${idx}"
            params.append(symbol)
            idx += 1
        query += " ORDER BY opened_at DESC"

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
            items = [_row_to_dict(r) for r in rows]
            return collection_response(items, "position")
        except Exception as e:
            logger.exception("Failed to list positions")
            return server_error(str(e))

    # --- Position detail ---

    @app.get("/{position_id}", tags=["Positions"])
    async def get_position(position_id: str):
        """Get a single position with its current PnL."""
        query = """
            SELECT id, strategy_id, symbol, side, entry_price, quantity,
                   stop_loss, take_profit, unrealized_pnl, realized_pnl,
                   status, sizing_method, opened_at, closed_at,
                   close_reason, current_price
            FROM positions
            WHERE id = $1::uuid
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(query, position_id)
        except Exception as e:
            logger.exception("Failed to get position")
            return server_error(str(e))

        if not row:
            return not_found("Position", position_id)
        item = _row_to_dict(row)
        return success_response(item, "position", resource_id=position_id)

    # --- Closed position history ---

    @app.get("/history/closed", tags=["Positions"])
    async def closed_history(
        symbol: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """List closed positions with realized PnL."""
        query = """
            SELECT id, strategy_id, symbol, side, entry_price, quantity,
                   stop_loss, take_profit, unrealized_pnl, realized_pnl,
                   status, sizing_method, opened_at, closed_at,
                   close_reason, current_price
            FROM positions
            WHERE status = 'CLOSED'
        """
        count_query = "SELECT COUNT(*) FROM positions WHERE status = 'CLOSED'"
        params = []
        count_params = []
        idx = 1
        if symbol:
            query += f" AND symbol = ${idx}"
            count_query += f" AND symbol = ${idx}"
            params.append(symbol)
            count_params.append(symbol)
            idx += 1
        query += f" ORDER BY closed_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                total = await conn.fetchval(count_query, *count_params)
            items = [_row_to_dict(r) for r in rows]
            return collection_response(
                items, "position", total=total, limit=limit, offset=offset
            )
        except Exception as e:
            logger.exception("Failed to get position history")
            return server_error(str(e))

    # --- Close a position ---

    @app.put("/{position_id}/close", tags=["Positions"])
    async def close_position(position_id: str, body: CloseRequest):
        """Manually close an open position at the given exit price."""
        fetch_query = """
            SELECT id, strategy_id, symbol, side, entry_price, quantity,
                   stop_loss, take_profit, status
            FROM positions
            WHERE id = $1::uuid
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(fetch_query, position_id)

                if not row:
                    return not_found("Position", position_id)

                if row["status"] == "CLOSED":
                    return validation_error("Position is already closed")

                pos = Position(
                    id=str(row["id"]),
                    strategy_id=str(row["strategy_id"]) if row["strategy_id"] else None,
                    symbol=row["symbol"],
                    side=Side(row["side"]),
                    entry_price=float(row["entry_price"]),
                    quantity=float(row["quantity"]),
                )
                pnl = calc_realized_pnl(pos, body.exit_price)
                reason = body.reason or "MANUAL"
                now = datetime.now(timezone.utc)

                update_query = """
                    UPDATE positions
                    SET status = 'CLOSED',
                        realized_pnl = $2,
                        current_price = $3,
                        closed_at = $4,
                        close_reason = $5,
                        unrealized_pnl = 0
                    WHERE id = $1::uuid
                    RETURNING id, strategy_id, symbol, side, entry_price, quantity,
                              stop_loss, take_profit, unrealized_pnl, realized_pnl,
                              status, sizing_method, opened_at, closed_at,
                              close_reason, current_price
                """
                updated = await conn.fetchrow(
                    update_query, position_id, pnl, body.exit_price, now, reason
                )

            item = _row_to_dict(updated)
            return success_response(item, "position", resource_id=position_id)
        except Exception as e:
            logger.exception("Failed to close position")
            return server_error(str(e))

    return app
