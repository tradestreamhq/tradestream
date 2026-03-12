"""
Benchmark Comparison REST API — RMM Level 2.

Compares strategy performance against market benchmarks
(SPY, QQQ, BTC, or custom indices).
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import asyncpg
import numpy as np
from fastapi import FastAPI, Query

from services.benchmark_comparison.comparator import compare
from services.benchmark_comparison.models import (
    BenchmarkComparison,
    BenchmarkType,
    TimePeriod,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

DEFAULT_BENCHMARKS = ["SPY", "QQQ", "BTC"]

_PERIOD_DAYS = {
    TimePeriod.ONE_DAY: 1,
    TimePeriod.ONE_WEEK: 7,
    TimePeriod.ONE_MONTH: 30,
    TimePeriod.THREE_MONTHS: 90,
    TimePeriod.YTD: None,  # computed dynamically
    TimePeriod.ALL_TIME: None,
}


def _period_start(period: TimePeriod) -> Optional[datetime]:
    """Return the start datetime for a given period, or None for all-time."""
    now = datetime.now(timezone.utc)
    if period == TimePeriod.YTD:
        return datetime(now.year, 1, 1, tzinfo=timezone.utc)
    days = _PERIOD_DAYS.get(period)
    if days is None:
        return None
    return now - timedelta(days=days)


async def _fetch_daily_returns(
    conn,
    table: str,
    id_column: str,
    id_value: str,
    start: Optional[datetime],
) -> np.ndarray:
    """Fetch daily returns from a table, filtered by date."""
    if start:
        query = f"""
            SELECT daily_return FROM {table}
            WHERE {id_column} = $1 AND date >= $2
            ORDER BY date
        """
        rows = await conn.fetch(query, id_value, start)
    else:
        query = f"""
            SELECT daily_return FROM {table}
            WHERE {id_column} = $1
            ORDER BY date
        """
        rows = await conn.fetch(query, id_value)
    return np.array([float(r["daily_return"]) for r in rows], dtype=np.float64)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Benchmark Comparison API FastAPI application."""
    app = FastAPI(
        title="Benchmark Comparison API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/analytics/benchmark",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("benchmark-comparison-api", check_deps))

    @app.get("/{strategy_id}", tags=["Benchmark"])
    async def get_benchmark_comparison(
        strategy_id: str,
        benchmarks: Optional[str] = Query(
            None,
            description="Comma-separated benchmark symbols (default: SPY,QQQ,BTC)",
        ),
        period: TimePeriod = Query(
            TimePeriod.THREE_MONTHS, description="Time period for comparison"
        ),
    ):
        """Compare strategy returns against one or more benchmarks."""
        benchmark_list = (
            [b.strip().upper() for b in benchmarks.split(",")]
            if benchmarks
            else DEFAULT_BENCHMARKS
        )

        start = _period_start(period)

        try:
            async with db_pool.acquire() as conn:
                strategy_returns = await _fetch_daily_returns(
                    conn, "strategy_daily_returns", "strategy_id", strategy_id, start
                )

                if len(strategy_returns) == 0:
                    return not_found("Strategy returns", strategy_id)

                comparisons = []
                for bench_symbol in benchmark_list:
                    bench_returns = await _fetch_daily_returns(
                        conn,
                        "benchmark_daily_returns",
                        "symbol",
                        bench_symbol,
                        start,
                    )
                    if len(bench_returns) == 0:
                        continue

                    result = compare(
                        strategy_id=strategy_id,
                        benchmark_name=bench_symbol,
                        period=period,
                        strategy_returns=strategy_returns,
                        benchmark_returns=bench_returns,
                    )
                    comparisons.append(result.model_dump(mode="json"))

        except Exception:
            logger.exception("Error computing benchmark comparison")
            return server_error("Failed to compute benchmark comparison")

        return success_response(
            {
                "strategy_id": strategy_id,
                "period": period.value,
                "comparisons": comparisons,
            },
            "benchmark_comparison",
            resource_id=strategy_id,
        )

    return app
