"""
Fee Analytics REST API — RMM Level 2.

Provides endpoints for recording trading fees, querying fee records,
and viewing fee analytics (summaries, trends) by strategy.
"""

import logging
from datetime import datetime
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query

from services.fee_tracker.models import FeeRecordCreate, FeeType
from services.fee_tracker.tracker import FeeTracker
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    server_error,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Fee Analytics FastAPI application."""
    app = FastAPI(
        title="Fee Analytics API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/analytics/fees",
    )
    fastapi_auth_middleware(app)

    tracker = FeeTracker(db_pool)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("fee-analytics-api", check_deps))

    # --- Record a fee ---

    @app.post("/", tags=["Fees"])
    async def record_fee(body: FeeRecordCreate):
        """Record a new trading fee."""
        try:
            row = await tracker.record_fee(body)
            return success_response(row, "fee", status_code=201)
        except Exception:
            logger.exception("Failed to record fee")
            return server_error("Failed to record fee")

    # --- List fees ---

    @app.get("/", tags=["Fees"])
    async def list_fees(
        strategy_id: Optional[str] = Query(None, description="Filter by strategy"),
        fee_type: Optional[FeeType] = Query(None, description="Filter by fee type"),
        start: Optional[datetime] = Query(None, description="Start of date range"),
        end: Optional[datetime] = Query(None, description="End of date range"),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        """List fee records with optional filters."""
        try:
            rows = await tracker.get_fees(
                strategy_id=strategy_id,
                fee_type=fee_type,
                start=start,
                end=end,
                limit=limit,
                offset=offset,
            )
            return collection_response(rows, "fee", limit=limit, offset=offset)
        except Exception:
            logger.exception("Failed to list fees")
            return server_error("Failed to list fees")

    # --- Summary by strategy ---

    @app.get("/summary", tags=["Analytics"])
    async def fee_summary(
        strategy_id: Optional[str] = Query(None, description="Filter by strategy"),
        start: Optional[datetime] = Query(None, description="Start of date range"),
        end: Optional[datetime] = Query(None, description="End of date range"),
    ):
        """Get aggregated fee totals grouped by strategy and fee type."""
        try:
            rows = await tracker.get_summary_by_strategy(
                strategy_id=strategy_id, start=start, end=end
            )
            return success_response(
                {"strategies": rows},
                "fee_summary",
            )
        except Exception:
            logger.exception("Failed to compute fee summary")
            return server_error("Failed to compute fee summary")

    # --- Daily trend ---

    @app.get("/trend", tags=["Analytics"])
    async def fee_trend(
        strategy_id: Optional[str] = Query(None, description="Filter by strategy"),
        start: Optional[datetime] = Query(None, description="Start of date range"),
        end: Optional[datetime] = Query(None, description="End of date range"),
    ):
        """Get daily fee totals for trend analysis."""
        try:
            rows = await tracker.get_fee_trend(
                strategy_id=strategy_id, start=start, end=end
            )
            return success_response(
                {"trend": rows},
                "fee_trend",
            )
        except Exception:
            logger.exception("Failed to compute fee trend")
            return server_error("Failed to compute fee trend")

    return app
