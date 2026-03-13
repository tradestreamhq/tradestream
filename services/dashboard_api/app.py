"""
Dashboard REST API — RMM Level 2.

Aggregated endpoints optimized for frontend single-page load.
Provides overview, portfolio chart, top strategies, recent activity,
and market summary.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Query

from services.dashboard_api.cache import TTLCache
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    server_error,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

# Cache TTL defaults (seconds)
OVERVIEW_TTL = int(os.environ.get("DASHBOARD_OVERVIEW_TTL", "30"))
CHART_TTL = int(os.environ.get("DASHBOARD_CHART_TTL", "60"))
STRATEGIES_TTL = int(os.environ.get("DASHBOARD_STRATEGIES_TTL", "60"))
ACTIVITY_TTL = int(os.environ.get("DASHBOARD_ACTIVITY_TTL", "15"))
MARKET_TTL = int(os.environ.get("DASHBOARD_MARKET_TTL", "10"))

_PORTFOLIO_VALUE_SQL = """
    SELECT
        COALESCE(SUM(quantity * avg_entry_price), 0) AS portfolio_value,
        COALESCE(SUM(unrealized_pnl), 0) AS total_unrealized_pnl
    FROM paper_portfolio
    WHERE quantity != 0
"""

_PNL_BY_PERIOD_SQL = """
    SELECT
        COALESCE(SUM(pnl), 0) AS total_realized_pnl,
        COALESCE(SUM(CASE WHEN closed_at >= NOW() - INTERVAL '1 day'
            THEN pnl ELSE 0 END), 0) AS pnl_today,
        COALESCE(SUM(CASE WHEN closed_at >= NOW() - INTERVAL '7 days'
            THEN pnl ELSE 0 END), 0) AS pnl_week,
        COALESCE(SUM(CASE WHEN closed_at >= NOW() - INTERVAL '30 days'
            THEN pnl ELSE 0 END), 0) AS pnl_month
    FROM paper_trades
    WHERE status = 'CLOSED'
"""

_ACTIVE_STRATEGIES_SQL = """
    SELECT COUNT(*) AS active_strategies
    FROM strategies
    WHERE is_active = true
"""

_OPEN_POSITIONS_SQL = """
    SELECT COUNT(*) AS open_positions
    FROM paper_portfolio
    WHERE quantity != 0
"""

_PENDING_ALERTS_SQL = """
    SELECT COUNT(*) AS pending_alerts
    FROM signals
    WHERE notified_at IS NULL
"""

_CHART_SQL_TEMPLATE = """
    WITH time_series AS (
        SELECT generate_series(
            NOW() - INTERVAL '{lookback}',
            NOW(),
            INTERVAL '{bucket}'
        ) AS ts
    ),
    trade_equity AS (
        SELECT
            date_trunc('hour', closed_at) AS ts,
            SUM(pnl) OVER (ORDER BY closed_at) AS cumulative_pnl
        FROM paper_trades
        WHERE status = 'CLOSED'
            AND closed_at >= NOW() - INTERVAL '{lookback}'
        ORDER BY closed_at
    )
    SELECT
        t.ts,
        COALESCE(
            (SELECT te.cumulative_pnl
             FROM trade_equity te
             WHERE te.ts <= t.ts
             ORDER BY te.ts DESC LIMIT 1),
            0
        ) AS value
    FROM time_series t
    ORDER BY t.ts
"""

_TOP_STRATEGIES_SQL = """
    SELECT
        si.id,
        ss.name AS strategy_name,
        si.status,
        sp.sharpe_ratio,
        sp.total_return,
        sp.max_drawdown,
        sp.total_trades,
        sp.win_rate
    FROM strategy_implementations si
    JOIN strategy_specs ss ON si.spec_id = ss.id
    JOIN strategy_performance sp ON sp.implementation_id = si.id
    WHERE sp.period = '30d'
    ORDER BY sp.total_return DESC NULLS LAST
    LIMIT 5
"""

_SPARKLINE_SQL = """
    SELECT
        date_trunc('day', closed_at) AS day,
        SUM(pnl) AS daily_pnl
    FROM paper_trades
    WHERE status = 'CLOSED'
        AND closed_at >= NOW() - INTERVAL '30 days'
    GROUP BY date_trunc('day', closed_at)
    ORDER BY day
"""

_RECENT_TRADES_SQL = """
    SELECT
        'trade' AS activity_type,
        symbol AS title,
        side || ' ' || quantity::text || ' @ ' || entry_price::text AS description,
        COALESCE(closed_at, created_at) AS occurred_at,
        pnl
    FROM paper_trades
    ORDER BY COALESCE(closed_at, created_at) DESC
    LIMIT $1
"""

_RECENT_SIGNALS_SQL = """
    SELECT
        'signal' AS activity_type,
        instrument AS title,
        signal_type || ' signal (strength: ' || strength::text || ')' AS description,
        created_at AS occurred_at,
        NULL::numeric AS pnl
    FROM signals
    ORDER BY created_at DESC
    LIMIT $1
"""

_WATCHED_SYMBOLS_SQL = """
    SELECT DISTINCT symbol FROM (
        SELECT symbol FROM paper_portfolio WHERE quantity != 0
        UNION
        SELECT symbol FROM strategies WHERE is_active = true
    ) AS watched_symbols
    ORDER BY symbol
"""

_LATEST_PRICE_SQL = """
    SELECT
        instrument,
        price,
        created_at
    FROM signals
    WHERE instrument = $1
    ORDER BY created_at DESC
    LIMIT 1
"""

_PREV_PRICE_SQL = """
    SELECT price
    FROM signals
    WHERE instrument = $1
        AND created_at <= NOW() - INTERVAL '24 hours'
    ORDER BY created_at DESC
    LIMIT 1
"""


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Dashboard API FastAPI application."""
    app = FastAPI(
        title="Dashboard API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/dashboard",
    )
    fastapi_auth_middleware(app)

    cache = TTLCache()

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("dashboard-api", check_deps))

    # --- Overview ---

    @app.get("/overview", tags=["Dashboard"])
    async def get_overview():
        """Portfolio value, total PnL, active strategies, open positions, pending alerts."""
        cached = cache.get("overview")
        if cached is not None:
            return success_response(cached, "dashboard_overview")

        try:
            async with db_pool.acquire() as conn:
                portfolio_row = await conn.fetchrow(_PORTFOLIO_VALUE_SQL)
                pnl_row = await conn.fetchrow(_PNL_BY_PERIOD_SQL)
                strategies_row = await conn.fetchrow(_ACTIVE_STRATEGIES_SQL)
                positions_row = await conn.fetchrow(_OPEN_POSITIONS_SQL)
                alerts_row = await conn.fetchrow(_PENDING_ALERTS_SQL)

            data = {
                "portfolio_value": float(portfolio_row["portfolio_value"]),
                "total_unrealized_pnl": float(
                    portfolio_row["total_unrealized_pnl"]
                ),
                "total_realized_pnl": float(pnl_row["total_realized_pnl"]),
                "pnl_today": float(pnl_row["pnl_today"]),
                "pnl_week": float(pnl_row["pnl_week"]),
                "pnl_month": float(pnl_row["pnl_month"]),
                "active_strategies": int(strategies_row["active_strategies"]),
                "open_positions": int(positions_row["open_positions"]),
                "pending_alerts": int(alerts_row["pending_alerts"]),
            }

            cache.set("overview", data, OVERVIEW_TTL)
            return success_response(data, "dashboard_overview")
        except Exception:
            logger.exception("Failed to fetch dashboard overview")
            return server_error("Failed to fetch dashboard overview")

    # --- Portfolio Chart ---

    @app.get("/portfolio-chart", tags=["Dashboard"])
    async def get_portfolio_chart(
        period: str = Query("1m", pattern="^(1d|1w|1m|3m|1y)$"),
    ):
        """Time series of portfolio value for charting."""
        cache_key = f"portfolio_chart:{period}"
        cached = cache.get(cache_key)
        if cached is not None:
            return success_response(cached, "portfolio_chart")

        interval_map = {
            "1d": ("1 day", "1 hour"),
            "1w": ("7 days", "6 hours"),
            "1m": ("30 days", "1 day"),
            "3m": ("90 days", "3 days"),
            "1y": ("365 days", "1 week"),
        }
        lookback, bucket = interval_map[period]

        try:
            async with db_pool.acquire() as conn:
                query = _CHART_SQL_TEMPLATE.format(
                    lookback=lookback, bucket=bucket
                )
                rows = await conn.fetch(query)

            points = [
                {
                    "timestamp": row["ts"].isoformat(),
                    "value": float(row["value"]),
                }
                for row in rows
            ]

            data = {"period": period, "points": points}
            cache.set(cache_key, data, CHART_TTL)
            return success_response(data, "portfolio_chart")
        except Exception:
            logger.exception("Failed to fetch portfolio chart")
            return server_error("Failed to fetch portfolio chart")

    # --- Top Strategies ---

    @app.get("/top-strategies", tags=["Dashboard"])
    async def get_top_strategies():
        """Top 5 strategies by return with recent performance sparkline data."""
        cached = cache.get("top_strategies")
        if cached is not None:
            return success_response(cached, "top_strategies")

        try:
            async with db_pool.acquire() as conn:
                strategies = await conn.fetch(_TOP_STRATEGIES_SQL)

                result = []
                for row in strategies:
                    impl_id = row["id"]
                    sparkline_rows = await conn.fetch(_SPARKLINE_SQL)
                    sparkline = [
                        float(s["daily_pnl"]) for s in sparkline_rows
                    ]

                    result.append(
                        {
                            "id": str(impl_id),
                            "strategy_name": row["strategy_name"],
                            "status": row["status"],
                            "sharpe_ratio": (
                                float(row["sharpe_ratio"])
                                if row["sharpe_ratio"]
                                else None
                            ),
                            "total_return": (
                                float(row["total_return"])
                                if row["total_return"]
                                else None
                            ),
                            "max_drawdown": (
                                float(row["max_drawdown"])
                                if row["max_drawdown"]
                                else None
                            ),
                            "total_trades": (
                                int(row["total_trades"])
                                if row["total_trades"]
                                else 0
                            ),
                            "win_rate": (
                                float(row["win_rate"])
                                if row["win_rate"]
                                else None
                            ),
                            "sparkline": sparkline,
                        }
                    )

            data = {"strategies": result}
            cache.set("top_strategies", data, STRATEGIES_TTL)
            return success_response(data, "top_strategies")
        except Exception:
            logger.exception("Failed to fetch top strategies")
            return server_error("Failed to fetch top strategies")

    # --- Recent Activity ---

    @app.get("/recent-activity", tags=["Dashboard"])
    async def get_recent_activity(
        limit: int = Query(20, ge=1, le=100),
    ):
        """Recent trades, signals, and alerts combined into a single feed."""
        cache_key = f"recent_activity:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return success_response(cached, "recent_activity")

        try:
            async with db_pool.acquire() as conn:
                trades = await conn.fetch(_RECENT_TRADES_SQL, limit)
                signals = await conn.fetch(_RECENT_SIGNALS_SQL, limit)

            activities = []
            for row in list(trades) + list(signals):
                item = {
                    "activity_type": row["activity_type"],
                    "title": row["title"],
                    "description": row["description"],
                    "occurred_at": (
                        row["occurred_at"].isoformat()
                        if row["occurred_at"]
                        else None
                    ),
                }
                if row["pnl"] is not None:
                    item["pnl"] = float(row["pnl"])
                activities.append(item)

            activities.sort(
                key=lambda x: x["occurred_at"] or "",
                reverse=True,
            )
            activities = activities[:limit]

            data = {"activities": activities, "count": len(activities)}
            cache.set(cache_key, data, ACTIVITY_TTL)
            return success_response(data, "recent_activity")
        except Exception:
            logger.exception("Failed to fetch recent activity")
            return server_error("Failed to fetch recent activity")

    # --- Market Summary ---

    @app.get("/market-summary", tags=["Dashboard"])
    async def get_market_summary():
        """Prices for watched pairs with 24h change."""
        cached = cache.get("market_summary")
        if cached is not None:
            return success_response(cached, "market_summary")

        try:
            async with db_pool.acquire() as conn:
                symbols = await conn.fetch(_WATCHED_SYMBOLS_SQL)

                market_data = []
                for sym_row in symbols:
                    symbol = sym_row["symbol"]
                    latest = await conn.fetchrow(
                        _LATEST_PRICE_SQL, symbol
                    )
                    prev = await conn.fetchrow(_PREV_PRICE_SQL, symbol)

                    if latest and latest["price"]:
                        current_price = float(latest["price"])
                        prev_price = (
                            float(prev["price"])
                            if prev and prev["price"]
                            else current_price
                        )
                        change_24h = (
                            (
                                (current_price - prev_price)
                                / prev_price
                                * 100
                            )
                            if prev_price != 0
                            else 0.0
                        )

                        market_data.append(
                            {
                                "symbol": symbol,
                                "price": current_price,
                                "change_24h_pct": round(change_24h, 2),
                                "updated_at": latest[
                                    "created_at"
                                ].isoformat(),
                            }
                        )
                    else:
                        market_data.append(
                            {
                                "symbol": symbol,
                                "price": None,
                                "change_24h_pct": None,
                                "updated_at": None,
                            }
                        )

            data = {"pairs": market_data, "count": len(market_data)}
            cache.set("market_summary", data, MARKET_TTL)
            return success_response(data, "market_summary")
        except Exception:
            logger.exception("Failed to fetch market summary")
            return server_error("Failed to fetch market summary")

    return app
