"""
Strategy Performance Dashboard REST API — RMM Level 2.

Provides read-only endpoints for strategy performance metrics,
trade history, and a leaderboard of top-performing strategies.
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Strategy Performance Dashboard API application."""
    app = FastAPI(
        title="Strategy Performance Dashboard API",
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

    app.include_router(create_health_router("strategy-performance-api", check_deps))

    performance_router = APIRouter(tags=["Performance"])
    leaderboard_router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])

    # --- GET /strategies/{strategy_id}/performance ---

    @performance_router.get("/{strategy_id}/performance")
    async def get_performance(
        strategy_id: str,
        instrument: Optional[str] = Query(None, description="Filter by instrument"),
        environment: Optional[str] = Query(
            None, description="Filter by environment (BACKTEST, PAPER, LIVE)"
        ),
        from_date: Optional[str] = Query(
            None, description="Start date filter (ISO format)"
        ),
        to_date: Optional[str] = Query(
            None, description="End date filter (ISO format)"
        ),
    ):
        """Return aggregated performance metrics for a strategy implementation."""
        # Verify implementation exists
        async with db_pool.acquire() as conn:
            impl = await conn.fetchrow(
                "SELECT id FROM strategy_implementations WHERE id = $1::uuid",
                strategy_id,
            )
            if not impl:
                return not_found("Strategy", strategy_id)

            # Build conditions for filtering performance records
            conditions = ["sp.implementation_id = $1::uuid"]
            params: list = [strategy_id]
            idx = 1

            if instrument is not None:
                idx += 1
                conditions.append(f"sp.instrument = ${idx}")
                params.append(instrument)

            if environment is not None:
                idx += 1
                conditions.append(f"sp.environment = ${idx}")
                params.append(environment)

            if from_date is not None:
                idx += 1
                conditions.append(f"sp.period_start >= ${idx}::timestamp")
                params.append(from_date)

            if to_date is not None:
                idx += 1
                conditions.append(f"sp.period_end <= ${idx}::timestamp")
                params.append(to_date)

            where = " AND ".join(conditions)

            query = f"""
                SELECT
                    COALESCE(SUM(sp.total_return), 0) AS cumulative_pnl,
                    CASE
                        WHEN SUM(sp.total_trades) > 0
                        THEN SUM(sp.winning_trades)::decimal / SUM(sp.total_trades)
                        ELSE 0
                    END AS win_rate,
                    COALESCE(SUM(sp.total_trades), 0) AS trade_count,
                    CASE
                        WHEN SUM(sp.total_trades) > 0
                        THEN SUM(sp.avg_trade_duration_seconds * sp.total_trades)
                             / SUM(sp.total_trades)
                        ELSE 0
                    END AS avg_hold_time_seconds,
                    AVG(sp.sharpe_ratio) AS avg_sharpe_ratio,
                    AVG(sp.max_drawdown) AS avg_max_drawdown,
                    AVG(sp.profit_factor) AS avg_profit_factor
                FROM strategy_performance sp
                WHERE {where}
            """
            row = await conn.fetchrow(query, *params)

        if not row or row["trade_count"] == 0:
            data = {
                "strategy_id": strategy_id,
                "cumulative_pnl": 0,
                "win_rate": 0,
                "trade_count": 0,
                "avg_hold_time_seconds": 0,
                "avg_sharpe_ratio": None,
                "avg_max_drawdown": None,
                "avg_profit_factor": None,
            }
        else:
            data = {
                "strategy_id": strategy_id,
                "cumulative_pnl": float(row["cumulative_pnl"]),
                "win_rate": float(row["win_rate"]),
                "trade_count": int(row["trade_count"]),
                "avg_hold_time_seconds": int(row["avg_hold_time_seconds"]),
                "avg_sharpe_ratio": (
                    float(row["avg_sharpe_ratio"])
                    if row["avg_sharpe_ratio"] is not None
                    else None
                ),
                "avg_max_drawdown": (
                    float(row["avg_max_drawdown"])
                    if row["avg_max_drawdown"] is not None
                    else None
                ),
                "avg_profit_factor": (
                    float(row["avg_profit_factor"])
                    if row["avg_profit_factor"] is not None
                    else None
                ),
            }

        return success_response(
            data, "strategy_performance", resource_id=strategy_id
        )

    # --- GET /strategies/{strategy_id}/trades ---

    @performance_router.get("/{strategy_id}/trades")
    async def list_trades(
        strategy_id: str,
        pagination: PaginationParams = Depends(),
        instrument: Optional[str] = Query(
            None, description="Filter by instrument/asset pair"
        ),
        from_date: Optional[str] = Query(
            None, description="Start date filter (ISO format)"
        ),
        to_date: Optional[str] = Query(
            None, description="End date filter (ISO format)"
        ),
        sort_by: Optional[str] = Query(
            None, description="Sort field", regex="^(created_at|pnl|instrument)$"
        ),
        sort_order: Optional[str] = Query(
            "desc", description="Sort order", regex="^(asc|desc)$"
        ),
    ):
        """Return paginated trade history for a strategy implementation."""
        # Verify implementation exists
        async with db_pool.acquire() as conn:
            impl = await conn.fetchrow(
                "SELECT id FROM strategy_implementations WHERE id = $1::uuid",
                strategy_id,
            )
            if not impl:
                return not_found("Strategy", strategy_id)

            conditions = ["s.implementation_id = $1::uuid"]
            params: list = [strategy_id]
            idx = 1

            if instrument is not None:
                idx += 1
                conditions.append(f"s.instrument = ${idx}")
                params.append(instrument)

            if from_date is not None:
                idx += 1
                conditions.append(f"s.created_at >= ${idx}::timestamp")
                params.append(from_date)

            if to_date is not None:
                idx += 1
                conditions.append(f"s.created_at <= ${idx}::timestamp")
                params.append(to_date)

            where = " AND ".join(conditions)

            order_map = {
                "created_at": "s.created_at",
                "pnl": "s.pnl",
                "instrument": "s.instrument",
            }
            order_col = order_map.get(sort_by, "s.created_at")
            direction = "ASC" if sort_order == "asc" else "DESC"

            idx += 1
            limit_idx = idx
            idx += 1
            offset_idx = idx
            params.extend([pagination.limit, pagination.offset])

            query = f"""
                SELECT s.id, s.instrument, s.signal_type, s.strength,
                       s.price AS entry_price, s.exit_price,
                       s.pnl, s.pnl_percent, s.outcome,
                       s.stop_loss, s.take_profit,
                       s.created_at, s.exit_time
                FROM signals s
                WHERE {where}
                ORDER BY {order_col} {direction}
                LIMIT ${limit_idx} OFFSET ${offset_idx}
            """
            count_query = f"""
                SELECT COUNT(*) FROM signals s WHERE {where}
            """

            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            for field in ("pnl", "pnl_percent", "entry_price", "exit_price",
                          "stop_loss", "take_profit", "strength"):
                if item.get(field) is not None:
                    item[field] = float(item[field])
            for field in ("created_at", "exit_time"):
                if item.get(field) is not None:
                    item[field] = item[field].isoformat()
            items.append(item)

        return collection_response(
            items,
            "trade",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # --- GET /strategies/leaderboard ---

    @leaderboard_router.get("")
    async def leaderboard(
        pagination: PaginationParams = Depends(),
        instrument: Optional[str] = Query(
            None, description="Filter by instrument/asset pair"
        ),
        environment: Optional[str] = Query(
            None, description="Filter by environment (BACKTEST, PAPER, LIVE)"
        ),
        from_date: Optional[str] = Query(
            None, description="Start date filter (ISO format)"
        ),
        to_date: Optional[str] = Query(
            None, description="End date filter (ISO format)"
        ),
    ):
        """Return strategies ranked by total return."""
        conditions = ["1=1"]
        params: list = []
        idx = 0

        if instrument is not None:
            idx += 1
            conditions.append(f"sp.instrument = ${idx}")
            params.append(instrument)

        if environment is not None:
            idx += 1
            conditions.append(f"sp.environment = ${idx}")
            params.append(environment)

        if from_date is not None:
            idx += 1
            conditions.append(f"sp.period_start >= ${idx}::timestamp")
            params.append(from_date)

        if to_date is not None:
            idx += 1
            conditions.append(f"sp.period_end <= ${idx}::timestamp")
            params.append(to_date)

        where = " AND ".join(conditions)

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT
                si.id AS implementation_id,
                ss.name AS strategy_name,
                COALESCE(SUM(sp.total_return), 0) AS total_return,
                CASE
                    WHEN SUM(sp.total_trades) > 0
                    THEN SUM(sp.winning_trades)::decimal / SUM(sp.total_trades)
                    ELSE 0
                END AS win_rate,
                COALESCE(SUM(sp.total_trades), 0) AS trade_count,
                AVG(sp.sharpe_ratio) AS avg_sharpe_ratio,
                AVG(sp.max_drawdown) AS avg_max_drawdown
            FROM strategy_implementations si
            JOIN strategy_specs ss ON ss.id = si.spec_id
            LEFT JOIN strategy_performance sp ON sp.implementation_id = si.id
                AND {where}
            WHERE si.status != 'INACTIVE'
            GROUP BY si.id, ss.name
            HAVING SUM(sp.total_trades) > 0
            ORDER BY total_return DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """

        count_query = f"""
            SELECT COUNT(*) FROM (
                SELECT si.id
                FROM strategy_implementations si
                LEFT JOIN strategy_performance sp ON sp.implementation_id = si.id
                    AND {where}
                WHERE si.status != 'INACTIVE'
                GROUP BY si.id
                HAVING SUM(sp.total_trades) > 0
            ) sub
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = []
        for i, row in enumerate(rows):
            item = {
                "rank": pagination.offset + i + 1,
                "id": str(row["implementation_id"]),
                "strategy_name": row["strategy_name"],
                "total_return": float(row["total_return"]),
                "win_rate": float(row["win_rate"]),
                "trade_count": int(row["trade_count"]),
                "avg_sharpe_ratio": (
                    float(row["avg_sharpe_ratio"])
                    if row["avg_sharpe_ratio"] is not None
                    else None
                ),
                "avg_max_drawdown": (
                    float(row["avg_max_drawdown"])
                    if row["avg_max_drawdown"] is not None
                    else None
                ),
            }
            items.append(item)

        return collection_response(
            items,
            "strategy_ranking",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    app.include_router(performance_router)
    app.include_router(leaderboard_router)
    return app
