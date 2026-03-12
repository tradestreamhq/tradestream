"""
Strategy Performance Leaderboard API.

Ranks strategies by risk-adjusted returns using a composite scoring system
built on Sharpe ratio, total return, max drawdown, win rate, and trade count.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Enums & Constants ---


class TimePeriod(str, Enum):
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
    THREE_MONTHS = "3m"
    YTD = "ytd"
    ALL = "all"


class SortField(str, Enum):
    COMPOSITE = "composite_score"
    SHARPE = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    TOTAL_TRADES = "total_trades"


# Default weights for composite scoring
DEFAULT_WEIGHTS = {
    "sharpe_ratio": 0.35,
    "total_return": 0.25,
    "max_drawdown": 0.20,
    "win_rate": 0.15,
    "total_trades": 0.05,
}


# --- Scoring Logic ---


def compute_composite_score(
    sharpe_ratio: Optional[float],
    total_return: Optional[float],
    max_drawdown: Optional[float],
    win_rate: Optional[float],
    total_trades: int,
    weights: Dict[str, float] = DEFAULT_WEIGHTS,
) -> float:
    """Compute a weighted composite score from strategy metrics.

    Each metric is normalized to a 0-1 scale before weighting:
    - sharpe_ratio: sigmoid-like mapping, 2.0 maps to ~0.67
    - total_return: sigmoid-like mapping, 100% maps to ~0.5
    - max_drawdown: inverted (lower is better), 0% = 1.0, -50% = 0.5
    - win_rate: used directly (already 0-1)
    - total_trades: log scale, 100 trades maps to ~0.67
    """
    import math

    def _sigmoid(x: float, midpoint: float) -> float:
        return x / (x + midpoint) if x >= 0 else 0.0

    sharpe = float(sharpe_ratio) if sharpe_ratio is not None else 0.0
    ret = float(total_return) if total_return is not None else 0.0
    dd = float(max_drawdown) if max_drawdown is not None else 0.0
    wr = float(win_rate) if win_rate is not None else 0.0

    norm_sharpe = _sigmoid(max(sharpe, 0), 1.0)
    norm_return = _sigmoid(max(ret, 0), 1.0)
    norm_drawdown = 1.0 / (1.0 + abs(dd)) if dd <= 0 else 1.0
    norm_winrate = max(0.0, min(1.0, wr))
    norm_trades = _sigmoid(total_trades, 50) if total_trades > 0 else 0.0

    score = (
        weights.get("sharpe_ratio", 0.35) * norm_sharpe
        + weights.get("total_return", 0.25) * norm_return
        + weights.get("max_drawdown", 0.20) * norm_drawdown
        + weights.get("win_rate", 0.15) * norm_winrate
        + weights.get("total_trades", 0.05) * norm_trades
    )
    return round(score, 6)


def _period_start(
    period: TimePeriod, now: Optional[datetime] = None
) -> Optional[datetime]:
    """Return the start datetime for a given time period filter."""
    from datetime import timedelta

    now = now or datetime.now(timezone.utc)

    if period == TimePeriod.ALL:
        return None
    elif period == TimePeriod.ONE_DAY:
        return now - timedelta(days=1)
    elif period == TimePeriod.ONE_WEEK:
        return now - timedelta(weeks=1)
    elif period == TimePeriod.ONE_MONTH:
        return now - timedelta(days=30)
    elif period == TimePeriod.THREE_MONTHS:
        return now - timedelta(days=90)
    elif period == TimePeriod.YTD:
        return datetime(now.year, 1, 1, tzinfo=timezone.utc)
    return None


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Leaderboard API FastAPI application."""
    app = FastAPI(
        title="Strategy Leaderboard API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/strategies/leaderboard",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("leaderboard-api", check_deps))

    router = APIRouter(tags=["Leaderboard"])

    @router.get("")
    async def get_leaderboard(
        pagination: PaginationParams = Depends(),
        period: TimePeriod = Query(TimePeriod.ALL, description="Time period filter"),
        sort_by: SortField = Query(SortField.COMPOSITE, description="Field to sort by"),
        environment: Optional[str] = Query(
            None,
            description="Filter by environment (BACKTEST, PAPER, LIVE)",
            regex="^(BACKTEST|PAPER|LIVE)$",
        ),
        instrument: Optional[str] = Query(
            None, description="Filter by instrument symbol"
        ),
    ):
        """Get the strategy performance leaderboard.

        Aggregates performance metrics per strategy implementation and ranks
        them using a composite score based on risk-adjusted returns.
        """
        conditions = ["1=1"]
        params: list = []
        idx = 0

        start = _period_start(period)
        if start is not None:
            idx += 1
            conditions.append(f"sp.period_start >= ${idx}")
            params.append(start)

        if environment is not None:
            idx += 1
            conditions.append(f"sp.environment = ${idx}")
            params.append(environment)

        if instrument is not None:
            idx += 1
            conditions.append(f"sp.instrument = ${idx}")
            params.append(instrument)

        where = " AND ".join(conditions)

        # Aggregate metrics per implementation
        agg_query = f"""
            SELECT
                sp.implementation_id,
                ss.name AS strategy_name,
                sp.instrument,
                sp.environment,
                AVG(sp.sharpe_ratio)::DECIMAL(10,4) AS avg_sharpe_ratio,
                SUM(sp.total_return)::DECIMAL(10,4) AS total_return,
                MIN(sp.max_drawdown)::DECIMAL(10,4) AS max_drawdown,
                AVG(sp.win_rate)::DECIMAL(5,4) AS avg_win_rate,
                SUM(sp.total_trades) AS total_trades,
                AVG(sp.sortino_ratio)::DECIMAL(10,4) AS avg_sortino_ratio,
                AVG(sp.profit_factor)::DECIMAL(10,4) AS avg_profit_factor,
                MAX(sp.period_end) AS latest_period_end,
                COUNT(*) AS record_count
            FROM strategy_performance sp
            JOIN strategy_implementations si ON sp.implementation_id = si.id
            JOIN strategy_specs ss ON si.spec_id = ss.id
            WHERE {where}
            GROUP BY sp.implementation_id, ss.name, sp.instrument, sp.environment
        """

        # Wrap in a subquery to sort and paginate
        sort_map = {
            SortField.SHARPE: "avg_sharpe_ratio DESC NULLS LAST",
            SortField.TOTAL_RETURN: "total_return DESC NULLS LAST",
            SortField.MAX_DRAWDOWN: "max_drawdown DESC NULLS LAST",
            SortField.WIN_RATE: "avg_win_rate DESC NULLS LAST",
            SortField.TOTAL_TRADES: "total_trades DESC NULLS LAST",
            SortField.COMPOSITE: "avg_sharpe_ratio DESC NULLS LAST",  # placeholder; sorted in Python
        }

        order_clause = sort_map.get(sort_by, "avg_sharpe_ratio DESC NULLS LAST")

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        full_query = f"""
            SELECT * FROM ({agg_query}) agg
            ORDER BY {order_clause}
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """

        count_query = f"""
            SELECT COUNT(*) FROM ({agg_query}) agg
        """

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(full_query, *params)
                total = await conn.fetchval(count_query, *params[:-2])
        except Exception as e:
            logger.error("Leaderboard query failed: %s", e)
            return server_error(str(e))

        items = []
        for row in rows:
            item = dict(row)
            item["implementation_id"] = str(item["implementation_id"])
            if item.get("latest_period_end"):
                item["latest_period_end"] = item["latest_period_end"].isoformat()
            # Convert Decimals to float for JSON
            for key in (
                "avg_sharpe_ratio",
                "total_return",
                "max_drawdown",
                "avg_win_rate",
                "avg_sortino_ratio",
                "avg_profit_factor",
            ):
                if item.get(key) is not None:
                    item[key] = float(item[key])
            if item.get("total_trades") is not None:
                item["total_trades"] = int(item["total_trades"])
            if item.get("record_count") is not None:
                item["record_count"] = int(item["record_count"])
            item["composite_score"] = compute_composite_score(
                sharpe_ratio=item.get("avg_sharpe_ratio"),
                total_return=item.get("total_return"),
                max_drawdown=item.get("max_drawdown"),
                win_rate=item.get("avg_win_rate"),
                total_trades=item.get("total_trades", 0),
            )
            items.append(item)

        # If sorting by composite score, re-sort in Python
        if sort_by == SortField.COMPOSITE:
            items.sort(key=lambda x: x.get("composite_score", 0), reverse=True)

        return collection_response(
            items,
            "leaderboard_entry",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @router.get("/scoring-weights")
    async def get_scoring_weights():
        """Return the current composite scoring weights."""
        return success_response(
            DEFAULT_WEIGHTS,
            "scoring_weights",
        )

    app.include_router(router)
    return app
