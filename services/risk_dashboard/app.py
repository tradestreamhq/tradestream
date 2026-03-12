"""Risk Dashboard REST API.

Provides GET /api/v1/risk/dashboard endpoint that aggregates portfolio risk
metrics across all active strategies.
"""

import logging
from dataclasses import asdict
from typing import Any, Dict, List

import asyncpg
from fastapi import FastAPI

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import server_error, success_response
from services.risk_dashboard.aggregator import aggregate_risk_dashboard
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Risk Dashboard FastAPI application."""
    app = FastAPI(
        title="Risk Dashboard API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/risk",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("risk-dashboard", check_deps))

    @app.get("/dashboard", tags=["Risk Dashboard"])
    async def get_dashboard():
        """Get aggregated risk dashboard across all active strategies."""
        try:
            async with db_pool.acquire() as conn:
                # Get open positions
                positions = await conn.fetch(
                    """
                    SELECT symbol, quantity, avg_entry_price, unrealized_pnl
                    FROM paper_portfolio
                    WHERE quantity != 0
                    ORDER BY symbol
                    """
                )

                # Get active strategy count
                active_count = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM strategies
                    WHERE is_active = TRUE
                    """
                )

                # Get total equity
                unrealized = await conn.fetchval(
                    "SELECT COALESCE(SUM(unrealized_pnl), 0) FROM paper_portfolio"
                )
                realized = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(pnl), 0)
                    FROM paper_trades
                    WHERE status = 'CLOSED'
                    """
                )
                total_equity = 10000.0 + float(realized) + float(unrealized)

                # Get daily PnL for return calculations (last 30 days)
                daily_pnl_rows = await conn.fetch(
                    """
                    SELECT symbol,
                           DATE(closed_at) as trade_date,
                           SUM(pnl) as daily_pnl
                    FROM paper_trades
                    WHERE status = 'CLOSED'
                      AND closed_at >= NOW() - INTERVAL '30 days'
                    GROUP BY symbol, DATE(closed_at)
                    ORDER BY symbol, trade_date
                    """
                )

            # Build daily returns by symbol
            pos_list = [dict(row) for row in positions]
            daily_returns_by_symbol: Dict[str, List[float]] = {}
            for row in daily_pnl_rows:
                symbol = row["symbol"]
                # Approximate daily return as pnl / position value
                pos_value = next(
                    (
                        abs(float(p["quantity"]) * float(p["avg_entry_price"]))
                        for p in pos_list
                        if p["symbol"] == symbol
                    ),
                    None,
                )
                if pos_value and pos_value > 0:
                    daily_return = float(row["daily_pnl"]) / pos_value
                    daily_returns_by_symbol.setdefault(symbol, []).append(daily_return)

            # Use first symbol's returns as benchmark proxy (BTC typically)
            benchmark_returns = daily_returns_by_symbol.get("BTC/USD", [])

            dashboard = aggregate_risk_dashboard(
                positions=pos_list,
                daily_returns_by_symbol=daily_returns_by_symbol,
                benchmark_returns=benchmark_returns,
                total_equity=total_equity,
                active_strategy_count=active_count or 0,
                benchmark_name="BTC/USD",
            )

            # Serialize dataclasses to dict
            result = asdict(dashboard)

            return success_response(result, "risk_dashboard")

        except Exception:
            logger.exception("Failed to compute risk dashboard")
            return server_error("Failed to compute risk dashboard")

    return app
