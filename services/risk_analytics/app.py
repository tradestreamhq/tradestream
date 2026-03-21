"""
Portfolio Risk Analytics REST API — RMM Level 2.

Provides endpoints for portfolio-level risk metrics, historical
risk snapshots, and strategy correlation analysis.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import Depends, FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    server_error,
    success_response,
)
from services.risk_analytics.risk_service import (
    StrategyReturn,
    build_risk_snapshot,
    compute_correlation_matrix,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


async def _load_strategy_returns(
    conn: asyncpg.Connection,
) -> tuple[List[StrategyReturn], float]:
    """Load strategy return data from the database.

    Queries strategy_performance for per-strategy returns and
    paper_portfolio for current portfolio value.
    """
    perf_query = """
        SELECT
            si.id::text AS strategy_id,
            sp.total_return,
            sp.period_start,
            sp.period_end
        FROM strategy_performance sp
        JOIN strategy_implementations si ON sp.implementation_id = si.id
        WHERE sp.environment IN ('PAPER', 'LIVE')
        ORDER BY si.id, sp.period_start
    """
    rows = await conn.fetch(perf_query)

    # Group returns by strategy
    strat_map: Dict[str, List[float]] = {}
    for row in rows:
        sid = row["strategy_id"]
        ret = float(row["total_return"]) if row["total_return"] is not None else 0.0
        strat_map.setdefault(sid, []).append(ret)

    # Get capital per strategy from current positions
    alloc_query = """
        SELECT
            si.id::text AS strategy_id,
            COALESCE(SUM(ABS(pp.quantity * pp.avg_entry_price)), 0) AS capital
        FROM strategy_implementations si
        LEFT JOIN paper_portfolio pp ON TRUE
        GROUP BY si.id
    """
    alloc_rows = await conn.fetch(alloc_query)
    alloc_map = {row["strategy_id"]: float(row["capital"]) for row in alloc_rows}

    # Build StrategyReturn objects
    strategy_returns = []
    for sid, returns in strat_map.items():
        strategy_returns.append(
            StrategyReturn(
                strategy_id=sid,
                returns=returns,
                capital_allocated=alloc_map.get(sid, 0.0),
            )
        )

    # Portfolio value
    value_row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(quantity * avg_entry_price), 0) AS total_value
        FROM paper_portfolio
        """
    )
    portfolio_value = float(value_row["total_value"]) if value_row else 0.0

    return strategy_returns, portfolio_value


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Risk Analytics API FastAPI application."""
    app = FastAPI(
        title="Risk Analytics API",
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

    app.include_router(create_health_router("risk-analytics", check_deps))

    # --- Risk Snapshot ---

    @app.get("/risk", tags=["Risk"])
    async def get_risk():
        """Get current portfolio risk snapshot with all computed metrics."""
        try:
            async with db_pool.acquire() as conn:
                strategy_returns, portfolio_value = await _load_strategy_returns(conn)

            snapshot = build_risk_snapshot(strategy_returns, portfolio_value)
            return success_response(
                {
                    "total_exposure": snapshot.total_exposure,
                    "net_position": snapshot.net_position,
                    "portfolio_value": snapshot.portfolio_value,
                    "var_95": snapshot.var_95,
                    "var_99": snapshot.var_99,
                    "max_drawdown": snapshot.max_drawdown,
                    "current_drawdown": snapshot.current_drawdown,
                    "sharpe_ratio": snapshot.sharpe_ratio,
                    "sortino_ratio": snapshot.sortino_ratio,
                    "strategy_concentrations": snapshot.strategy_concentrations,
                    "strategy_count": snapshot.strategy_count,
                },
                "risk_snapshot",
            )
        except Exception:
            logger.exception("Failed to compute risk snapshot")
            return server_error("Failed to compute risk snapshot")

    # --- Risk History ---

    @app.get("/risk/history", tags=["Risk"])
    async def get_risk_history(pagination: PaginationParams = Depends()):
        """Get historical risk snapshots."""
        try:
            query = """
                SELECT id, total_exposure, net_position, portfolio_value,
                       var_95, var_99, max_drawdown, current_drawdown,
                       sharpe_ratio, sortino_ratio,
                       strategy_concentrations, strategy_count,
                       snapshot_type, created_at
                FROM risk_snapshots
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """
            count_query = "SELECT COUNT(*) FROM risk_snapshots"

            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, pagination.limit, pagination.offset)
                total = await conn.fetchval(count_query)

            items = []
            for row in rows:
                item = dict(row)
                item["id"] = str(item["id"])
                for key in (
                    "total_exposure",
                    "net_position",
                    "portfolio_value",
                    "var_95",
                    "var_99",
                    "max_drawdown",
                    "current_drawdown",
                    "sharpe_ratio",
                    "sortino_ratio",
                ):
                    if item.get(key) is not None:
                        item[key] = float(item[key])
                if item.get("created_at"):
                    item["created_at"] = item["created_at"].isoformat()
                items.append(item)

            return collection_response(
                items,
                "risk_snapshot",
                total=total,
                limit=pagination.limit,
                offset=pagination.offset,
            )
        except Exception:
            logger.exception("Failed to fetch risk history")
            return server_error("Failed to fetch risk history")

    # --- Correlation ---

    @app.get("/correlation", tags=["Risk"])
    async def get_correlation():
        """Get strategy return correlation matrix."""
        try:
            async with db_pool.acquire() as conn:
                strategy_returns, _ = await _load_strategy_returns(conn)

            corr = compute_correlation_matrix(strategy_returns)
            return success_response(
                {
                    "strategy_count": len(strategy_returns),
                    "matrix": corr,
                },
                "correlation_matrix",
            )
        except Exception:
            logger.exception("Failed to compute correlation matrix")
            return server_error("Failed to compute correlation matrix")

    return app
