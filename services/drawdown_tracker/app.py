"""
Drawdown Tracker REST API — monitors strategy drawdown recovery.

Provides endpoints for drawdown depth, duration, recovery trajectory,
and time-to-recovery estimation per strategy.
"""

import logging
from datetime import datetime, timezone
from typing import List, Tuple

import asyncpg
from fastapi import FastAPI

from services.drawdown_tracker.tracker import build_summary
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    not_found,
    server_error,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Drawdown Tracker FastAPI application."""
    app = FastAPI(
        title="Drawdown Tracker API",
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

    app.include_router(create_health_router("drawdown-tracker", check_deps))

    @app.get("/drawdowns/{strategy_id}", tags=["Drawdowns"])
    async def get_drawdowns(strategy_id: str):
        """Get drawdown analysis for a strategy including current state,
        historical events, and time-to-recovery estimates."""
        try:
            equity_curve = await _load_equity_curve(db_pool, strategy_id)
        except Exception:
            logger.exception("Failed to load equity curve for %s", strategy_id)
            return server_error("Failed to load equity data")

        if not equity_curve:
            return not_found("Strategy equity data", strategy_id)

        summary = build_summary(strategy_id, equity_curve)
        return success_response(summary.to_dict(), "drawdown_summary", resource_id=strategy_id)

    return app


async def _load_equity_curve(
    pool: asyncpg.Pool, strategy_id: str
) -> List[Tuple[datetime, float]]:
    """Load the equity curve for a strategy from paper_trades and performance data."""
    query = """
        SELECT
            period_start AS ts,
            total_return AS equity
        FROM strategy_performance
        WHERE implementation_id = $1::uuid
          AND environment = 'PAPER'
        ORDER BY period_start ASC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, strategy_id)

    if not rows:
        return []

    # Convert cumulative returns to an equity curve (base = 10000)
    base_equity = 10000.0
    curve = []
    for row in rows:
        ts = row["ts"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ret = float(row["equity"])
        curve.append((ts, base_equity * (1 + ret)))

    return curve
