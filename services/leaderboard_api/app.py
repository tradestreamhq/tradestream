"""
Trading Leaderboard REST API.

Ranks traders by performance metrics (total return, Sharpe ratio,
win rate, consistency score) over configurable periods with opt-in
privacy and caching.
"""

import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Header, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300  # 5 minutes


class Period(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALL_TIME = "all_time"


class SortMetric(str, Enum):
    TOTAL_RETURN = "total_return_pct"
    SHARPE = "sharpe_ratio"
    WIN_RATE = "win_rate"
    CONSISTENCY = "consistency_score"


SORT_COLUMN = {
    SortMetric.TOTAL_RETURN: "total_return_pct",
    SortMetric.SHARPE: "sharpe_ratio",
    SortMetric.WIN_RATE: "win_rate",
    SortMetric.CONSISTENCY: "consistency_score",
}


def _snapshot_to_dict(row) -> Dict[str, Any]:
    """Convert a leaderboard snapshot row to a response dict."""
    result: Dict[str, Any] = {}

    result["user_id"] = str(row["user_id"])
    result["display_name"] = row["display_name"]
    result["period"] = row["period"]

    for key in ("total_return_pct", "sharpe_ratio", "win_rate", "consistency_score"):
        val = row.get(key)
        result[key] = float(val) if val is not None else None

    for key in ("total_trades", "winning_trades", "losing_trades", "rank"):
        val = row.get(key)
        result[key] = int(val) if val is not None else None

    val = row.get("percentile")
    result["percentile"] = float(val) if val is not None else None

    snapshot_date = row.get("snapshot_date")
    result["snapshot_date"] = str(snapshot_date) if snapshot_date is not None else None

    if row.get("strategy_type") is not None:
        result["strategy_type"] = row["strategy_type"]
    if row.get("asset_class") is not None:
        result["asset_class"] = row["asset_class"]

    return result


def _build_leaderboard_query(
    period: Period,
    sort_by: SortMetric,
    strategy_type: Optional[str],
    asset_class: Optional[str],
    limit: int,
    offset: int,
) -> tuple:
    """Build ranked leaderboard query with filters."""
    sort_col = SORT_COLUMN[sort_by]
    params: list = [period.value]
    conditions = [
        "tp.leaderboard_visible = TRUE",
        "ls.period = $1",
        "ls.snapshot_date = (SELECT MAX(snapshot_date) FROM leaderboard_snapshots WHERE period = $1)",
    ]

    idx = 2
    if strategy_type is not None:
        conditions.append(f"tp.strategy_type = ${idx}")
        params.append(strategy_type)
        idx += 1
    if asset_class is not None:
        conditions.append(f"tp.asset_class = ${idx}")
        params.append(asset_class)
        idx += 1

    where = " AND ".join(conditions)
    params.append(limit)
    params.append(offset)

    query = f"""
        SELECT
            tp.user_id,
            tp.display_name,
            tp.strategy_type,
            tp.asset_class,
            ls.period,
            ls.total_return_pct,
            ls.sharpe_ratio,
            ls.win_rate,
            ls.consistency_score,
            ls.total_trades,
            ls.winning_trades,
            ls.losing_trades,
            ls.rank,
            ls.percentile,
            ls.snapshot_date
        FROM leaderboard_snapshots ls
        JOIN trader_profiles tp ON ls.user_id = tp.user_id
        WHERE {where}
        ORDER BY {sort_col} DESC NULLS LAST
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    return query, params


def _build_count_query(
    period: Period,
    strategy_type: Optional[str],
    asset_class: Optional[str],
) -> tuple:
    """Build count query for total visible traders."""
    params: list = [period.value]
    conditions = [
        "tp.leaderboard_visible = TRUE",
        "ls.period = $1",
        "ls.snapshot_date = (SELECT MAX(snapshot_date) FROM leaderboard_snapshots WHERE period = $1)",
    ]

    idx = 2
    if strategy_type is not None:
        conditions.append(f"tp.strategy_type = ${idx}")
        params.append(strategy_type)
        idx += 1
    if asset_class is not None:
        conditions.append(f"tp.asset_class = ${idx}")
        params.append(asset_class)
        idx += 1

    where = " AND ".join(conditions)
    query = f"""
        SELECT COUNT(*)
        FROM leaderboard_snapshots ls
        JOIN trader_profiles tp ON ls.user_id = tp.user_id
        WHERE {where}
    """
    return query, params


def _build_me_query(period: Period) -> str:
    """Build query for current user's ranking."""
    return """
        SELECT
            tp.user_id,
            tp.display_name,
            tp.strategy_type,
            tp.asset_class,
            ls.period,
            ls.total_return_pct,
            ls.sharpe_ratio,
            ls.win_rate,
            ls.consistency_score,
            ls.total_trades,
            ls.winning_trades,
            ls.losing_trades,
            ls.rank,
            ls.percentile,
            ls.snapshot_date
        FROM leaderboard_snapshots ls
        JOIN trader_profiles tp ON ls.user_id = tp.user_id
        WHERE ls.user_id = $1
          AND ls.period = $2
          AND ls.snapshot_date = (
              SELECT MAX(snapshot_date)
              FROM leaderboard_snapshots
              WHERE period = $2
          )
    """


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Trading Leaderboard API FastAPI application."""
    app = FastAPI(
        title="Trading Leaderboard API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/leaderboard",
    )
    fastapi_auth_middleware(app)

    # Simple in-memory cache: key -> (timestamp, data)
    _cache: Dict[str, tuple] = {}

    def _get_cached(key: str) -> Optional[Any]:
        if key in _cache:
            ts, data = _cache[key]
            if time.monotonic() - ts < CACHE_TTL_SECONDS:
                return data
            del _cache[key]
        return None

    def _set_cached(key: str, data: Any) -> None:
        _cache[key] = (time.monotonic(), data)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("leaderboard-api", check_deps))

    @app.get("/leaderboard", tags=["Leaderboard"])
    async def get_leaderboard(
        period: Period = Query(Period.MONTHLY, description="Time period"),
        sort_by: SortMetric = Query(
            SortMetric.TOTAL_RETURN, description="Metric to rank by"
        ),
        strategy_type: Optional[str] = Query(
            None, description="Filter by strategy type"
        ),
        asset_class: Optional[str] = Query(None, description="Filter by asset class"),
        pagination: PaginationParams = Depends(),
    ):
        """Get ranked list of traders by performance metrics."""
        cache_key = (
            f"lb:{period.value}:{sort_by.value}"
            f":{strategy_type}:{asset_class}"
            f":{pagination.limit}:{pagination.offset}"
        )
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

        query, params = _build_leaderboard_query(
            period,
            sort_by,
            strategy_type,
            asset_class,
            pagination.limit,
            pagination.offset,
        )
        count_query, count_params = _build_count_query(
            period,
            strategy_type,
            asset_class,
        )

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *count_params)

        items = [_snapshot_to_dict(row) for row in rows]

        response = collection_response(
            items,
            "trader_ranking",
            total=total or 0,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        _set_cached(cache_key, response)
        return response

    @app.get("/leaderboard/me", tags=["Leaderboard"])
    async def get_my_ranking(
        period: Period = Query(Period.MONTHLY, description="Time period"),
        x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    ):
        """Get current user's ranking and percentile."""
        if not x_user_id:
            return error_response(
                "UNAUTHORIZED",
                "X-User-Id header is required",
                status_code=401,
            )

        query = _build_me_query(period)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, x_user_id, period.value)

        if row is None:
            return not_found("trader_ranking", x_user_id)

        entry = _snapshot_to_dict(row)
        return success_response(entry, "trader_ranking", resource_id=x_user_id)

    @app.put("/leaderboard/visibility", tags=["Leaderboard"])
    async def update_visibility(
        visible: bool = Query(
            ..., description="Enable or disable leaderboard visibility"
        ),
        x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    ):
        """Opt in or out of leaderboard visibility."""
        if not x_user_id:
            return error_response(
                "UNAUTHORIZED",
                "X-User-Id header is required",
                status_code=401,
            )

        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE trader_profiles
                SET leaderboard_visible = $1, updated_at = NOW()
                WHERE user_id = $2
                """,
                visible,
                x_user_id,
            )

        if result == "UPDATE 0":
            return not_found("trader_profile", x_user_id)

        return success_response(
            {"user_id": x_user_id, "leaderboard_visible": visible},
            "trader_profile",
            resource_id=x_user_id,
        )

    return app
