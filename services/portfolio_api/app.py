"""
Portfolio REST API — RMM Level 2.

Provides endpoints for portfolio state, positions, balance,
risk metrics, and trade validation.
"""

import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
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
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl, updated_at
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

        pos_list = []
        total_unrealized = 0.0
        for row in positions:
            item = dict(row)
            if item.get("updated_at"):
                item["updated_at"] = item["updated_at"].isoformat()
            item["quantity"] = float(item["quantity"])
            item["avg_entry_price"] = float(item["avg_entry_price"])
            item["unrealized_pnl"] = float(item["unrealized_pnl"])
            total_unrealized += item["unrealized_pnl"]
            pos_list.append(item)

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
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl, updated_at
            FROM paper_portfolio
            WHERE quantity != 0
            ORDER BY symbol
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        items = []
        for row in rows:
            item = dict(row)
            if item.get("updated_at"):
                item["updated_at"] = item["updated_at"].isoformat()
            item["quantity"] = float(item["quantity"])
            item["avg_entry_price"] = float(item["avg_entry_price"])
            item["unrealized_pnl"] = float(item["unrealized_pnl"])
            items.append(item)
        return collection_response(items, "position")

    @app.get("/positions/{instrument}", tags=["Positions"])
    async def get_position(instrument: str):
        """Get position for a specific instrument."""
        query = """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl, updated_at
            FROM paper_portfolio
            WHERE symbol = $1
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, instrument)
        if not row:
            return not_found("Position", instrument)
        item = dict(row)
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        item["quantity"] = float(item["quantity"])
        item["avg_entry_price"] = float(item["avg_entry_price"])
        item["unrealized_pnl"] = float(item["unrealized_pnl"])
        return success_response(item, "position", resource_id=instrument)

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
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl
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

        # Compute per-instrument concentration
        concentrations = {}
        for p in positions:
            exposure = abs(float(p["quantity"]) * float(p["avg_entry_price"]))
            concentrations[p["symbol"]] = (
                round(exposure / total_exposure, 4) if total_exposure > 0 else 0
            )

        return success_response(
            {
                "total_exposure": total_exposure,
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

        # Basic validation rules
        if body.size <= 0:
            errors.append("size must be positive")

        # Check existing position for SELL
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
