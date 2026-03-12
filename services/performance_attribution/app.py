"""
Performance Attribution REST API — RMM Level 2.

Breaks down P&L by strategy, asset class, and time period.
Provides Sharpe ratio, max drawdown, and win rate per strategy.
"""

import logging
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Query

from services.performance_attribution.attribution import (
    compute_daily_returns,
    compute_max_drawdown,
    compute_sharpe_ratio,
    compute_win_rate,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# Asset class classification based on symbol conventions.
CRYPTO_SUFFIXES = ("/USD", "/USDT", "/BTC", "/ETH", "/EUR")
FUTURES_SUFFIXES = ("-PERP", "-FUT", "_FUT")


def classify_asset_class(symbol: str) -> str:
    """Classify a trading symbol into an asset class."""
    upper = symbol.upper()
    if any(upper.endswith(s) for s in FUTURES_SUFFIXES):
        return "futures"
    if any(upper.endswith(s) for s in CRYPTO_SUFFIXES) or "/" in upper:
        return "crypto"
    return "equities"


class TimeBucket(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


def _date_trunc_sql(bucket: TimeBucket) -> str:
    """Return the PostgreSQL date_trunc interval for a time bucket."""
    return {
        TimeBucket.DAILY: "day",
        TimeBucket.WEEKLY: "week",
        TimeBucket.MONTHLY: "month",
    }[bucket]


def _serialize_decimal(val: Any) -> Optional[float]:
    """Safely convert a Decimal or numeric value to float."""
    if val is None:
        return None
    f = float(val)
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 8)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Performance Attribution API FastAPI application."""
    app = FastAPI(
        title="Performance Attribution API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/attribution",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("performance-attribution", check_deps))

    # --- P&L by Strategy ---

    @app.get("/strategy", tags=["Attribution"])
    async def pnl_by_strategy():
        """Break down P&L, Sharpe, max drawdown, and win rate per strategy."""
        query = """
            SELECT
                ss.name AS strategy_name,
                pt.symbol,
                pt.pnl,
                pt.opened_at,
                pt.closed_at
            FROM paper_trades pt
            JOIN signals s ON s.id = pt.signal_id
            JOIN strategy_specs ss ON ss.id = s.spec_id
            WHERE pt.status = 'CLOSED' AND pt.pnl IS NOT NULL
            ORDER BY ss.name, pt.closed_at
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query)
        except Exception as exc:
            logger.exception("Failed to query strategy attribution")
            return server_error(str(exc))

        # Group trades by strategy
        strategies: Dict[str, List[Dict]] = {}
        for row in rows:
            name = row["strategy_name"]
            strategies.setdefault(name, []).append(dict(row))

        items = []
        for name, trades in strategies.items():
            pnls = [float(t["pnl"]) for t in trades]
            total_pnl = sum(pnls)
            daily_rets = compute_daily_returns(trades)
            items.append(
                {
                    "strategy_name": name,
                    "total_pnl": round(total_pnl, 8),
                    "trade_count": len(trades),
                    "win_rate": compute_win_rate(pnls),
                    "sharpe_ratio": compute_sharpe_ratio(daily_rets),
                    "max_drawdown": compute_max_drawdown(pnls),
                }
            )

        items.sort(key=lambda x: x["total_pnl"], reverse=True)
        return collection_response(items, "strategy_attribution")

    # --- P&L by Asset Class ---

    @app.get("/asset-class", tags=["Attribution"])
    async def pnl_by_asset_class():
        """Break down P&L by asset class (equities, crypto, futures)."""
        query = """
            SELECT symbol, pnl, opened_at, closed_at
            FROM paper_trades
            WHERE status = 'CLOSED' AND pnl IS NOT NULL
            ORDER BY closed_at
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query)
        except Exception as exc:
            logger.exception("Failed to query asset class attribution")
            return server_error(str(exc))

        classes: Dict[str, List[Dict]] = {}
        for row in rows:
            ac = classify_asset_class(row["symbol"])
            classes.setdefault(ac, []).append(dict(row))

        items = []
        for ac, trades in classes.items():
            pnls = [float(t["pnl"]) for t in trades]
            total_pnl = sum(pnls)
            daily_rets = compute_daily_returns(trades)
            items.append(
                {
                    "asset_class": ac,
                    "total_pnl": round(total_pnl, 8),
                    "trade_count": len(trades),
                    "win_rate": compute_win_rate(pnls),
                    "sharpe_ratio": compute_sharpe_ratio(daily_rets),
                    "max_drawdown": compute_max_drawdown(pnls),
                }
            )

        items.sort(key=lambda x: x["total_pnl"], reverse=True)
        return collection_response(items, "asset_class_attribution")

    # --- P&L by Time Period ---

    @app.get("/time", tags=["Attribution"])
    async def pnl_by_time(
        bucket: TimeBucket = Query(
            TimeBucket.DAILY, description="Time bucket granularity"
        ),
    ):
        """Break down P&L into time buckets (daily, weekly, monthly)."""
        interval = _date_trunc_sql(bucket)
        query = f"""
            SELECT
                date_trunc('{interval}', closed_at) AS period,
                SUM(pnl) AS total_pnl,
                COUNT(*) AS trade_count,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losing_trades
            FROM paper_trades
            WHERE status = 'CLOSED' AND pnl IS NOT NULL AND closed_at IS NOT NULL
            GROUP BY period
            ORDER BY period
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query)
        except Exception as exc:
            logger.exception("Failed to query time attribution")
            return server_error(str(exc))

        items = []
        for row in rows:
            total = int(row["trade_count"])
            winning = int(row["winning_trades"])
            items.append(
                {
                    "period": row["period"].isoformat() if row["period"] else None,
                    "bucket": bucket.value,
                    "total_pnl": _serialize_decimal(row["total_pnl"]),
                    "trade_count": total,
                    "win_rate": round(winning / total, 4) if total > 0 else None,
                }
            )

        return collection_response(items, "time_attribution")

    # --- Summary ---

    @app.get("/summary", tags=["Attribution"])
    async def attribution_summary():
        """Overall attribution summary combining strategy, asset class, and aggregate metrics."""
        query = """
            SELECT
                pnl, symbol, opened_at, closed_at
            FROM paper_trades
            WHERE status = 'CLOSED' AND pnl IS NOT NULL
            ORDER BY closed_at
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query)
        except Exception as exc:
            logger.exception("Failed to query attribution summary")
            return server_error(str(exc))

        if not rows:
            return success_response(
                {
                    "total_pnl": 0,
                    "trade_count": 0,
                    "win_rate": None,
                    "sharpe_ratio": None,
                    "max_drawdown": None,
                },
                "attribution_summary",
            )

        trades = [dict(r) for r in rows]
        pnls = [float(t["pnl"]) for t in trades]
        daily_rets = compute_daily_returns(trades)

        return success_response(
            {
                "total_pnl": round(sum(pnls), 8),
                "trade_count": len(pnls),
                "win_rate": compute_win_rate(pnls),
                "sharpe_ratio": compute_sharpe_ratio(daily_rets),
                "max_drawdown": compute_max_drawdown(pnls),
            },
            "attribution_summary",
        )

    return app
