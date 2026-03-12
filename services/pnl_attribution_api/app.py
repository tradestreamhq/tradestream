"""
PnL Attribution REST API — RMM Level 2.

Provides endpoints for decomposing portfolio returns by strategy,
asset class, direction, realization status, and time period.
"""

import logging
from datetime import datetime
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query

from services.pnl_attribution_api.attributor import compute_attribution
from services.pnl_attribution_api.models import Period
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the PnL Attribution API FastAPI application."""
    app = FastAPI(
        title="PnL Attribution API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/analytics",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("pnl-attribution-api", check_deps))

    @app.get("/attribution", tags=["Attribution"])
    async def get_attribution(
        period: Period = Query(Period.DAILY, description="Time bucketing granularity"),
        start: Optional[str] = Query(None, description="Start date ISO-8601"),
        end: Optional[str] = Query(None, description="End date ISO-8601"),
    ):
        """Get full PnL attribution breakdown."""
        start_dt = None
        end_dt = None

        if start:
            try:
                start_dt = datetime.fromisoformat(start)
            except ValueError:
                return validation_error("Invalid start date format, use ISO-8601")
        if end:
            try:
                end_dt = datetime.fromisoformat(end)
            except ValueError:
                return validation_error("Invalid end date format, use ISO-8601")

        try:
            async with db_pool.acquire() as conn:
                result = await compute_attribution(
                    conn, period=period, start=start_dt, end=end_dt
                )
        except Exception as e:
            logger.exception("Attribution computation failed")
            return server_error(f"Attribution computation failed: {e}")

        return success_response(result.model_dump(), "pnl_attribution")

    @app.get("/attribution/strategies", tags=["Attribution"])
    async def get_strategy_attribution(
        start: Optional[str] = Query(None, description="Start date ISO-8601"),
        end: Optional[str] = Query(None, description="End date ISO-8601"),
    ):
        """Get PnL attribution by strategy only."""
        start_dt = None
        end_dt = None

        if start:
            try:
                start_dt = datetime.fromisoformat(start)
            except ValueError:
                return validation_error("Invalid start date format, use ISO-8601")
        if end:
            try:
                end_dt = datetime.fromisoformat(end)
            except ValueError:
                return validation_error("Invalid end date format, use ISO-8601")

        try:
            async with db_pool.acquire() as conn:
                result = await compute_attribution(
                    conn, start=start_dt, end=end_dt
                )
        except Exception as e:
            logger.exception("Strategy attribution failed")
            return server_error(f"Strategy attribution failed: {e}")

        return success_response(
            {
                "total_pnl": result.total_pnl,
                "strategies": [s.model_dump() for s in result.by_strategy],
            },
            "strategy_attribution",
        )

    @app.get("/attribution/assets", tags=["Attribution"])
    async def get_asset_attribution(
        start: Optional[str] = Query(None, description="Start date ISO-8601"),
        end: Optional[str] = Query(None, description="End date ISO-8601"),
    ):
        """Get PnL attribution by asset only."""
        start_dt = None
        end_dt = None

        if start:
            try:
                start_dt = datetime.fromisoformat(start)
            except ValueError:
                return validation_error("Invalid start date format, use ISO-8601")
        if end:
            try:
                end_dt = datetime.fromisoformat(end)
            except ValueError:
                return validation_error("Invalid end date format, use ISO-8601")

        try:
            async with db_pool.acquire() as conn:
                result = await compute_attribution(
                    conn, start=start_dt, end=end_dt
                )
        except Exception as e:
            logger.exception("Asset attribution failed")
            return server_error(f"Asset attribution failed: {e}")

        return success_response(
            {
                "total_pnl": result.total_pnl,
                "assets": [a.model_dump() for a in result.by_asset],
            },
            "asset_attribution",
        )

    return app
