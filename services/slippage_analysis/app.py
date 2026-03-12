"""
Slippage Analysis REST API — RMM Level 2.

Provides endpoints for analyzing execution quality by comparing
expected vs actual fill prices across all trades.
"""

import logging
from typing import Optional

import asyncpg
from fastapi import Depends, FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware
from services.slippage_analysis.analyzer import (
    build_report,
    count_slippage_records,
    fetch_slippage_records,
)

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Slippage Analysis API FastAPI application."""
    app = FastAPI(
        title="Slippage Analysis API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/analytics/slippage",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("slippage-analysis", check_deps))

    # --- Slippage report ---

    @app.get("/report", tags=["Slippage"])
    async def get_slippage_report(
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        side: Optional[str] = Query(None, description="Filter by side (BUY/SELL)"),
        start_date: Optional[str] = Query(None, description="Start date ISO 8601"),
        end_date: Optional[str] = Query(None, description="End date ISO 8601"),
    ):
        """Get comprehensive slippage analysis report with breakdowns."""
        async with db_pool.acquire() as conn:
            # Fetch all matching records for report (up to 10k for analysis)
            records = await fetch_slippage_records(
                conn,
                symbol=symbol,
                side=side,
                start_date=start_date,
                end_date=end_date,
                limit=10000,
                offset=0,
            )

        report = build_report(records)
        return success_response(report, "slippage_report")

    # --- Individual trade slippage records ---

    @app.get("/trades", tags=["Slippage"])
    async def list_slippage_trades(
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        side: Optional[str] = Query(None, description="Filter by side (BUY/SELL)"),
        start_date: Optional[str] = Query(None, description="Start date ISO 8601"),
        end_date: Optional[str] = Query(None, description="End date ISO 8601"),
        pagination: PaginationParams = Depends(),
    ):
        """List individual trades with slippage details."""
        async with db_pool.acquire() as conn:
            records = await fetch_slippage_records(
                conn,
                symbol=symbol,
                side=side,
                start_date=start_date,
                end_date=end_date,
                limit=pagination.limit,
                offset=pagination.offset,
            )
            total = await count_slippage_records(
                conn,
                symbol=symbol,
                side=side,
                start_date=start_date,
                end_date=end_date,
            )

        return collection_response(
            records,
            "slippage_trade",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    return app
