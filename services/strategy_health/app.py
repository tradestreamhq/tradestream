"""Strategy Health Checker REST API.

Provides an endpoint to check strategy health based on performance metrics.
"""

import logging
from datetime import datetime, timezone

import asyncpg
from fastapi import FastAPI

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import not_found, server_error, success_response
from services.shared.auth import fastapi_auth_middleware
from services.strategy_health.checker import evaluate_health
from services.strategy_health.models import HealthState, MetricSnapshot

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Strategy Health Checker FastAPI application."""
    app = FastAPI(
        title="Strategy Health Checker API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/strategies",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("strategy-health", check_deps))

    @app.get("/{strategy_id}/health")
    async def get_strategy_health(strategy_id: str):
        """Check health of a strategy by evaluating its performance metrics."""
        try:
            async with db_pool.acquire() as conn:
                # Verify strategy exists
                strategy = await conn.fetchrow(
                    "SELECT id, status FROM strategies WHERE id = $1::uuid",
                    strategy_id,
                )
                if not strategy:
                    return not_found("Strategy", strategy_id)

                previous_state = None
                if strategy["status"] == "DISABLED":
                    previous_state = HealthState.DISABLED

                # Fetch rolling Sharpe and 90-day average Sharpe
                sharpe_row = await conn.fetchrow(
                    """
                    SELECT
                        AVG(sharpe_ratio) FILTER (
                            WHERE recorded_at >= NOW() - INTERVAL '30 days'
                        ) AS rolling_sharpe,
                        AVG(sharpe_ratio) FILTER (
                            WHERE recorded_at >= NOW() - INTERVAL '90 days'
                        ) AS sharpe_90d_avg
                    FROM strategy_metrics
                    WHERE strategy_id = $1::uuid
                    """,
                    strategy_id,
                )

                # Fetch win rate and win rate trend
                win_rate_row = await conn.fetchrow(
                    """
                    SELECT
                        AVG(win_rate) FILTER (
                            WHERE recorded_at >= NOW() - INTERVAL '30 days'
                        ) AS current_win_rate,
                        AVG(win_rate) FILTER (
                            WHERE recorded_at >= NOW() - INTERVAL '30 days'
                        ) - AVG(win_rate) FILTER (
                            WHERE recorded_at >= NOW() - INTERVAL '90 days'
                        ) AS win_rate_trend
                    FROM strategy_metrics
                    WHERE strategy_id = $1::uuid
                    """,
                    strategy_id,
                )

                # Fetch drawdown metrics
                drawdown_row = await conn.fetchrow(
                    """
                    SELECT
                        COALESCE(
                            (SELECT drawdown FROM strategy_metrics
                             WHERE strategy_id = $1::uuid
                             ORDER BY recorded_at DESC LIMIT 1),
                            0
                        ) AS current_drawdown,
                        COALESCE(MAX(drawdown), 0) AS historical_max_drawdown
                    FROM strategy_metrics
                    WHERE strategy_id = $1::uuid
                    """,
                    strategy_id,
                )

                # Fetch average trade duration
                duration_row = await conn.fetchrow(
                    """
                    SELECT AVG(EXTRACT(EPOCH FROM (closed_at - opened_at)))
                           AS avg_duration_seconds
                    FROM trades
                    WHERE strategy_id = $1::uuid
                      AND closed_at IS NOT NULL
                      AND opened_at >= NOW() - INTERVAL '30 days'
                    """,
                    strategy_id,
                )

            metrics = MetricSnapshot(
                rolling_sharpe=(
                    float(sharpe_row["rolling_sharpe"])
                    if sharpe_row and sharpe_row["rolling_sharpe"] is not None
                    else None
                ),
                sharpe_90d_avg=(
                    float(sharpe_row["sharpe_90d_avg"])
                    if sharpe_row and sharpe_row["sharpe_90d_avg"] is not None
                    else None
                ),
                win_rate=(
                    float(win_rate_row["current_win_rate"])
                    if win_rate_row and win_rate_row["current_win_rate"] is not None
                    else None
                ),
                win_rate_trend=(
                    float(win_rate_row["win_rate_trend"])
                    if win_rate_row and win_rate_row["win_rate_trend"] is not None
                    else None
                ),
                avg_trade_duration_seconds=(
                    float(duration_row["avg_duration_seconds"])
                    if duration_row
                    and duration_row["avg_duration_seconds"] is not None
                    else None
                ),
                drawdown_depth=(
                    float(drawdown_row["current_drawdown"])
                    if drawdown_row
                    and drawdown_row["current_drawdown"] is not None
                    else None
                ),
                historical_max_drawdown=(
                    float(drawdown_row["historical_max_drawdown"])
                    if drawdown_row
                    and drawdown_row["historical_max_drawdown"] is not None
                    else None
                ),
            )

            now = datetime.now(timezone.utc).isoformat()
            report = evaluate_health(strategy_id, metrics, now, previous_state)

            return success_response(
                report.model_dump(),
                "strategy_health",
                resource_id=strategy_id,
            )

        except Exception as e:
            logger.error("Health check failed for strategy %s: %s", strategy_id, e)
            return server_error(str(e))

    return app
