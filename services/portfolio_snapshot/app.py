"""
Portfolio Snapshot REST API.

Provides endpoints for capturing and querying daily portfolio snapshots
used for historical analysis and performance attribution.
"""

import logging
from datetime import date, datetime
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query

from services.portfolio_snapshot.snapshot import capture_snapshot
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def _snapshot_to_dict(row, positions=None):
    """Convert a snapshot DB row to a response dict."""
    result = {
        "id": str(row["id"]),
        "snapshot_date": row["snapshot_date"].isoformat(),
        "total_equity": float(row["total_equity"]),
        "cash_balance": float(row["cash_balance"]),
        "margin_used": float(row["margin_used"]),
        "daily_change": float(row["daily_change"]) if row["daily_change"] is not None else None,
        "daily_change_pct": float(row["daily_change_pct"]) if row["daily_change_pct"] is not None else None,
    }
    if positions is not None:
        result["positions"] = [
            {
                "symbol": p["symbol"],
                "quantity": float(p["quantity"]),
                "market_value": float(p["market_value"]),
            }
            for p in positions
        ]
    return result


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Portfolio Snapshot API FastAPI application."""
    app = FastAPI(
        title="Portfolio Snapshot API",
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

    app.include_router(create_health_router("portfolio-snapshot", check_deps))

    @app.post("/snapshots", tags=["Snapshots"])
    async def create_snapshot():
        """Capture a new portfolio snapshot for today."""
        try:
            snapshot = await capture_snapshot(db_pool)
            return success_response(
                {
                    "id": snapshot.id,
                    "snapshot_date": snapshot.snapshot_date.isoformat(),
                    "total_equity": snapshot.total_equity,
                    "cash_balance": snapshot.cash_balance,
                    "margin_used": snapshot.margin_used,
                    "daily_change": snapshot.daily_change,
                    "daily_change_pct": snapshot.daily_change_pct,
                    "positions": [
                        {
                            "symbol": p.symbol,
                            "quantity": p.quantity,
                            "market_value": p.market_value,
                        }
                        for p in snapshot.positions
                    ],
                },
                "portfolio_snapshot",
                resource_id=snapshot.id,
                status_code=201,
            )
        except Exception:
            logger.exception("Failed to capture snapshot")
            return server_error("Failed to capture portfolio snapshot")

    @app.get("/snapshots", tags=["Snapshots"])
    async def list_snapshots(
        start_date: Optional[date] = Query(None, description="Start date (inclusive)"),
        end_date: Optional[date] = Query(None, description="End date (inclusive)"),
        limit: int = Query(50, ge=1, le=365),
        offset: int = Query(0, ge=0),
    ):
        """List portfolio snapshots with optional date range filter."""
        conditions = []
        params = []
        param_idx = 0

        if start_date is not None:
            param_idx += 1
            conditions.append(f"snapshot_date >= ${param_idx}")
            params.append(start_date)
        if end_date is not None:
            param_idx += 1
            conditions.append(f"snapshot_date <= ${param_idx}")
            params.append(end_date)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        param_idx += 1
        limit_param = f"${param_idx}"
        params.append(limit)

        param_idx += 1
        offset_param = f"${param_idx}"
        params.append(offset)

        query = (
            f"SELECT id, snapshot_date, total_equity, cash_balance, margin_used, "
            f"daily_change, daily_change_pct FROM portfolio_snapshots "
            f"{where} ORDER BY snapshot_date DESC "
            f"LIMIT {limit_param} OFFSET {offset_param}"
        )

        count_query = f"SELECT COUNT(*) FROM portfolio_snapshots {where}"
        count_params = [p for p in params[: len(params) - 2]]

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *count_params)

        items = [_snapshot_to_dict(row) for row in rows]
        return collection_response(items, "portfolio_snapshot", total=total, limit=limit, offset=offset)

    @app.get("/snapshots/{snapshot_date}", tags=["Snapshots"])
    async def get_snapshot(snapshot_date: date):
        """Get a specific snapshot by date, including positions."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, snapshot_date, total_equity, cash_balance, margin_used, "
                "daily_change, daily_change_pct "
                "FROM portfolio_snapshots WHERE snapshot_date = $1",
                snapshot_date,
            )
            if not row:
                return not_found("Snapshot", snapshot_date.isoformat())

            positions = await conn.fetch(
                "SELECT symbol, quantity, market_value "
                "FROM portfolio_snapshot_positions WHERE snapshot_id = $1 ORDER BY symbol",
                row["id"],
            )

        return success_response(
            _snapshot_to_dict(row, positions),
            "portfolio_snapshot",
            resource_id=str(row["id"]),
        )

    return app
