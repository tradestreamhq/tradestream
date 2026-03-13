"""
Leaderboard REST API.

Ranks strategies by performance metrics over configurable periods
and provides side-by-side comparison of selected strategies.
"""

import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


class Period(str, Enum):
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"
    YTD = "ytd"
    ALL_TIME = "all_time"


class SortMetric(str, Enum):
    TOTAL_RETURN = "total_return"
    SHARPE = "sharpe"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    TOTAL_TRADES = "total_trades"


# Column mapping from sort metric to DB column
SORT_COLUMN_MAP = {
    SortMetric.TOTAL_RETURN: "total_return",
    SortMetric.SHARPE: "sharpe_ratio",
    SortMetric.MAX_DRAWDOWN: "max_drawdown",
    SortMetric.WIN_RATE: "win_rate",
    SortMetric.PROFIT_FACTOR: "profit_factor",
    SortMetric.TOTAL_TRADES: "total_trades",
}

# Higher is better for all except max_drawdown (less negative is better)
SORT_DIRECTION = {
    SortMetric.TOTAL_RETURN: "DESC",
    SortMetric.SHARPE: "DESC",
    SortMetric.MAX_DRAWDOWN: "DESC",
    SortMetric.WIN_RATE: "DESC",
    SortMetric.PROFIT_FACTOR: "DESC",
    SortMetric.TOTAL_TRADES: "DESC",
}

CACHE_TTL_SECONDS = 300  # 5 minutes


def period_start_date(period: Period) -> Optional[datetime]:
    """Return the start datetime for a given period, or None for all_time."""
    now = datetime.now(timezone.utc)
    if period == Period.SEVEN_DAYS:
        from datetime import timedelta

        return now - timedelta(days=7)
    elif period == Period.THIRTY_DAYS:
        from datetime import timedelta

        return now - timedelta(days=30)
    elif period == Period.NINETY_DAYS:
        from datetime import timedelta

        return now - timedelta(days=90)
    elif period == Period.YTD:
        return datetime(now.year, 1, 1, tzinfo=timezone.utc)
    elif period == Period.ALL_TIME:
        return None
    return None


def _build_leaderboard_query(period: Period, sort_by: SortMetric) -> tuple:
    """Build the leaderboard SQL query and params."""
    sort_col = SORT_COLUMN_MAP[sort_by]
    sort_dir = SORT_DIRECTION[sort_by]

    date_filter = ""
    params: list = []
    start = period_start_date(period)
    if start is not None:
        date_filter = "AND sp.period_start >= $1"
        params.append(start)

    query = f"""
        SELECT
            si.id AS implementation_id,
            ss.id AS spec_id,
            ss.name AS strategy_name,
            si.status,
            AVG(sp.total_return) AS total_return,
            AVG(sp.sharpe_ratio) AS sharpe_ratio,
            MIN(sp.max_drawdown) AS max_drawdown,
            AVG(sp.win_rate) AS win_rate,
            AVG(sp.profit_factor) AS profit_factor,
            SUM(sp.total_trades) AS total_trades,
            COUNT(sp.id) AS record_count
        FROM strategy_performance sp
        JOIN strategy_implementations si ON sp.implementation_id = si.id
        JOIN strategy_specs ss ON si.spec_id = ss.id
        WHERE si.status IN ('VALIDATED', 'DEPLOYED')
        {date_filter}
        GROUP BY si.id, ss.id, ss.name, si.status
        HAVING SUM(sp.total_trades) > 0
        ORDER BY {sort_col} {sort_dir} NULLS LAST
    """
    return query, params


def _build_comparison_query(ids: List[str], period: Period) -> tuple:
    """Build a comparison query for specific implementation IDs."""
    start = period_start_date(period)
    params: list = list(ids)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(ids)))

    date_filter = ""
    if start is not None:
        params.append(start)
        date_filter = f"AND sp.period_start >= ${len(params)}"

    query = f"""
        SELECT
            si.id AS implementation_id,
            ss.id AS spec_id,
            ss.name AS strategy_name,
            si.status,
            AVG(sp.total_return) AS total_return,
            AVG(sp.sharpe_ratio) AS sharpe_ratio,
            AVG(sp.sortino_ratio) AS sortino_ratio,
            MIN(sp.max_drawdown) AS max_drawdown,
            AVG(sp.win_rate) AS win_rate,
            AVG(sp.profit_factor) AS profit_factor,
            SUM(sp.total_trades) AS total_trades,
            SUM(sp.winning_trades) AS winning_trades,
            SUM(sp.losing_trades) AS losing_trades,
            AVG(sp.annualized_return) AS annualized_return,
            AVG(sp.volatility) AS volatility,
            COUNT(sp.id) AS record_count
        FROM strategy_performance sp
        JOIN strategy_implementations si ON sp.implementation_id = si.id
        JOIN strategy_specs ss ON si.spec_id = ss.id
        WHERE si.id::text IN ({placeholders})
        {date_filter}
        GROUP BY si.id, ss.id, ss.name, si.status
    """
    return query, params


def _build_equity_curve_query(ids: List[str], period: Period) -> tuple:
    """Build a query to get time-series equity curve data."""
    start = period_start_date(period)
    params: list = list(ids)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(ids)))

    date_filter = ""
    if start is not None:
        params.append(start)
        date_filter = f"AND sp.period_start >= ${len(params)}"

    query = f"""
        SELECT
            si.id AS implementation_id,
            ss.name AS strategy_name,
            sp.period_start,
            sp.period_end,
            sp.total_return
        FROM strategy_performance sp
        JOIN strategy_implementations si ON sp.implementation_id = si.id
        JOIN strategy_specs ss ON si.spec_id = ss.id
        WHERE si.id::text IN ({placeholders})
        {date_filter}
        ORDER BY si.id, sp.period_start
    """
    return query, params


def _row_to_metrics(row) -> Dict[str, Any]:
    """Convert a DB row to a metrics dict with proper float conversion."""
    result = {}
    for key in (
        "total_return",
        "sharpe_ratio",
        "max_drawdown",
        "win_rate",
        "profit_factor",
        "sortino_ratio",
        "annualized_return",
        "volatility",
    ):
        val = row.get(key)
        result[key] = float(val) if val is not None else None

    for key in ("total_trades", "winning_trades", "losing_trades", "record_count"):
        val = row.get(key)
        result[key] = int(val) if val is not None else None

    result["implementation_id"] = str(row["implementation_id"])
    result["spec_id"] = str(row["spec_id"])
    result["strategy_name"] = row["strategy_name"]
    result["status"] = row["status"]
    return result


def _normalize_equity_curves(rows) -> Dict[str, List[Dict[str, Any]]]:
    """Group equity curve rows by strategy and normalize to 1.0 start."""
    curves: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        impl_id = str(row["implementation_id"])
        if impl_id not in curves:
            curves[impl_id] = {
                "strategy_name": row["strategy_name"],
                "points": [],
            }
        total_return = (
            float(row["total_return"])
            if row["total_return"] is not None
            else 0.0
        )
        curves[impl_id]["points"].append(
            {
                "period_start": row["period_start"].isoformat(),
                "period_end": row["period_end"].isoformat(),
                "total_return": total_return,
            }
        )

    # Normalize: compute cumulative equity curve starting at 1.0
    for impl_id, data in curves.items():
        equity = 1.0
        normalized = []
        for pt in data["points"]:
            equity *= 1.0 + (pt["total_return"] or 0.0)
            normalized.append(
                {
                    "period_start": pt["period_start"],
                    "period_end": pt["period_end"],
                    "equity": round(equity, 6),
                }
            )
        data["points"] = normalized

    return curves


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Leaderboard API FastAPI application."""
    app = FastAPI(
        title="Leaderboard API",
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
        period: Period = Query(
            Period.THIRTY_DAYS, description="Time period for metrics"
        ),
        sort_by: SortMetric = Query(SortMetric.SHARPE, description="Metric to rank by"),
    ):
        """Get ranked list of strategies by performance metrics."""
        cache_key = f"leaderboard:{period.value}:{sort_by.value}"
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

        query, params = _build_leaderboard_query(period, sort_by)

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for rank, row in enumerate(rows, start=1):
            entry = _row_to_metrics(row)
            entry["rank"] = rank
            items.append(entry)

        response = collection_response(items, "strategy_ranking")
        _set_cached(cache_key, response)
        return response

    @app.get("/leaderboard/compare", tags=["Leaderboard"])
    async def compare_strategies(
        ids: str = Query(..., description="Comma-separated implementation IDs"),
        period: Period = Query(
            Period.THIRTY_DAYS, description="Time period for metrics"
        ),
    ):
        """Side-by-side comparison of selected strategies."""
        id_list = [s.strip() for s in ids.split(",") if s.strip()]
        if not id_list:
            return validation_error("At least one strategy ID is required")
        if len(id_list) > 10:
            return validation_error("Maximum 10 strategies for comparison")

        cache_key = f"compare:{','.join(sorted(id_list))}:{period.value}"
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

        comp_query, comp_params = _build_comparison_query(id_list, period)
        eq_query, eq_params = _build_equity_curve_query(id_list, period)

        async with db_pool.acquire() as conn:
            comp_rows = await conn.fetch(comp_query, *comp_params)
            eq_rows = await conn.fetch(eq_query, *eq_params)

        strategies = [_row_to_metrics(row) for row in comp_rows]
        equity_curves = _normalize_equity_curves(eq_rows)

        response = success_response(
            {
                "strategies": strategies,
                "equity_curves": equity_curves,
                "period": period.value,
            },
            "strategy_comparison",
        )
        _set_cached(cache_key, response)
        return response

    return app
