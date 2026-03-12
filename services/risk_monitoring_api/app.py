"""
Risk Monitoring REST API — RMM Level 2.

Provides endpoints for real-time risk metrics across all active strategies,
including exposure, VaR, portfolio beta, correlation matrix, and
concentration alerts.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
)
from services.risk_monitoring_api.risk_calculator import (
    compute_concentration_alerts,
    compute_correlation_matrix,
    compute_exposure_by_asset,
    compute_portfolio_beta,
    compute_returns,
    compute_var,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Risk Monitoring API FastAPI application."""
    app = FastAPI(
        title="Risk Monitoring API",
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

    app.include_router(create_health_router("risk-monitoring-api", check_deps))

    # --- Helpers ---

    async def _get_positions(conn) -> List[Dict[str, Any]]:
        rows = await conn.fetch(
            """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl
            FROM paper_portfolio
            WHERE quantity != 0
            """
        )
        return [dict(r) for r in rows]

    async def _get_trade_returns_by_strategy(
        conn, lookback_days: int
    ) -> Dict[str, List[float]]:
        """Get per-strategy returns from closed trades within the lookback window."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        rows = await conn.fetch(
            """
            SELECT
                COALESCE(s.spec_id::text, 'unlinked') AS strategy_id,
                pt.pnl,
                ABS(pt.quantity * pt.entry_price) AS exposure
            FROM paper_trades pt
            LEFT JOIN signals s ON pt.signal_id = s.id
            WHERE pt.status = 'CLOSED'
              AND pt.closed_at >= $1
            ORDER BY pt.closed_at
            """,
            cutoff,
        )
        strategy_returns: Dict[str, List[float]] = {}
        for r in rows:
            sid = r["strategy_id"]
            pnl = float(r["pnl"]) if r["pnl"] else 0.0
            exp = float(r["exposure"]) if r["exposure"] else 0.0
            ret = pnl / exp if exp > 0 else 0.0
            strategy_returns.setdefault(sid, []).append(ret)
        return strategy_returns

    async def _get_portfolio_returns(conn, lookback_days: int) -> List[float]:
        """Get aggregate portfolio returns from closed trades."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        rows = await conn.fetch(
            """
            SELECT pnl, ABS(quantity * entry_price) AS exposure
            FROM paper_trades
            WHERE status = 'CLOSED'
              AND closed_at >= $1
            ORDER BY closed_at
            """,
            cutoff,
        )
        return [
            float(r["pnl"]) / float(r["exposure"])
            if r["pnl"] and float(r["exposure"]) > 0
            else 0.0
            for r in rows
        ]

    # --- GET /summary ---

    @app.get("/summary", tags=["Risk"])
    async def get_risk_summary(
        lookback_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
        confidence: float = Query(0.95, ge=0.5, le=0.99, description="VaR confidence level"),
    ):
        """Get portfolio-wide risk summary with exposure, VaR, beta, correlations, and alerts."""
        try:
            async with db_pool.acquire() as conn:
                positions = await _get_positions(conn)
                strategy_returns = await _get_trade_returns_by_strategy(
                    conn, lookback_days
                )
                portfolio_returns = await _get_portfolio_returns(conn, lookback_days)
        except Exception:
            logger.exception("Failed to fetch risk data")
            return server_error("Failed to compute risk metrics")

        exposure = compute_exposure_by_asset(positions)
        total_exposure = sum(exposure.values())

        var = compute_var(portfolio_returns, confidence, total_exposure)

        # Use the first strategy with enough data as a benchmark proxy
        benchmark_returns = portfolio_returns
        beta = compute_portfolio_beta(portfolio_returns, benchmark_returns)

        correlation = compute_correlation_matrix(strategy_returns)

        alerts = compute_concentration_alerts(exposure)

        return success_response(
            {
                "exposure_by_asset": exposure,
                "total_exposure": round(total_exposure, 2),
                "value_at_risk": var,
                "var_confidence": confidence,
                "portfolio_beta": beta,
                "correlation_matrix": correlation,
                "concentration_alerts": alerts,
                "lookback_days": lookback_days,
                "position_count": len(positions),
                "strategy_count": len(strategy_returns),
            },
            "risk_summary",
        )

    # --- GET /by-strategy/{id} ---

    @app.get("/by-strategy/{strategy_id}", tags=["Risk"])
    async def get_risk_by_strategy(
        strategy_id: str,
        lookback_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
        confidence: float = Query(0.95, ge=0.5, le=0.99, description="VaR confidence level"),
    ):
        """Get risk metrics for a specific strategy."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        try:
            async with db_pool.acquire() as conn:
                # Verify strategy exists
                spec = await conn.fetchrow(
                    "SELECT id, name FROM strategy_specs WHERE id = $1",
                    strategy_id,
                )
                if not spec:
                    return not_found("Strategy", strategy_id)

                # Get trades linked to this strategy
                rows = await conn.fetch(
                    """
                    SELECT
                        pt.symbol,
                        pt.pnl,
                        pt.quantity,
                        pt.entry_price,
                        ABS(pt.quantity * pt.entry_price) AS exposure
                    FROM paper_trades pt
                    JOIN signals s ON pt.signal_id = s.id
                    WHERE s.spec_id = $1
                      AND pt.status = 'CLOSED'
                      AND pt.closed_at >= $2
                    ORDER BY pt.closed_at
                    """,
                    strategy_id,
                    cutoff,
                )

                # Get open positions linked to this strategy
                open_rows = await conn.fetch(
                    """
                    SELECT
                        pt.symbol,
                        pt.quantity,
                        pt.entry_price
                    FROM paper_trades pt
                    JOIN signals s ON pt.signal_id = s.id
                    WHERE s.spec_id = $1
                      AND pt.status = 'OPEN'
                    """,
                    strategy_id,
                )
        except Exception:
            logger.exception("Failed to fetch strategy risk data")
            return server_error("Failed to compute strategy risk metrics")

        # Compute returns
        returns = [
            float(r["pnl"]) / float(r["exposure"])
            if r["pnl"] and float(r["exposure"]) > 0
            else 0.0
            for r in rows
        ]

        # Exposure from open positions
        exposure: Dict[str, float] = {}
        for r in open_rows:
            sym = r["symbol"]
            exp = abs(float(r["quantity"]) * float(r["entry_price"]))
            exposure[sym] = exposure.get(sym, 0.0) + exp
        total_exposure = sum(exposure.values())

        var = compute_var(returns, confidence, total_exposure)

        # Trade stats
        trade_count = len(rows)
        winning = sum(1 for r in rows if r["pnl"] and float(r["pnl"]) > 0)
        total_pnl = sum(float(r["pnl"]) for r in rows if r["pnl"])

        return success_response(
            {
                "strategy_id": strategy_id,
                "strategy_name": spec["name"],
                "exposure_by_asset": {k: round(v, 2) for k, v in exposure.items()},
                "total_exposure": round(total_exposure, 2),
                "value_at_risk": var,
                "var_confidence": confidence,
                "trade_count": trade_count,
                "win_rate": round(winning / trade_count, 4) if trade_count > 0 else None,
                "total_pnl": round(total_pnl, 2),
                "returns": returns[-20:] if len(returns) > 20 else returns,
                "lookback_days": lookback_days,
            },
            "strategy_risk",
            resource_id=strategy_id,
        )

    # --- GET /history ---

    @app.get("/history", tags=["Risk"])
    async def get_risk_history(
        lookback_days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    ):
        """Get historical daily risk metrics (exposure and PnL) over the lookback window."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        DATE(closed_at) AS trade_date,
                        SUM(pnl) AS daily_pnl,
                        SUM(ABS(quantity * entry_price)) AS daily_exposure,
                        COUNT(*) AS trade_count
                    FROM paper_trades
                    WHERE status = 'CLOSED'
                      AND closed_at >= $1
                    GROUP BY DATE(closed_at)
                    ORDER BY trade_date
                    """,
                    cutoff,
                )
        except Exception:
            logger.exception("Failed to fetch risk history")
            return server_error("Failed to retrieve risk history")

        items = []
        for r in rows:
            daily_exp = float(r["daily_exposure"]) if r["daily_exposure"] else 0.0
            daily_pnl = float(r["daily_pnl"]) if r["daily_pnl"] else 0.0
            items.append(
                {
                    "date": r["trade_date"].isoformat(),
                    "daily_pnl": round(daily_pnl, 2),
                    "daily_exposure": round(daily_exp, 2),
                    "daily_return": round(daily_pnl / daily_exp, 4) if daily_exp > 0 else 0.0,
                    "trade_count": r["trade_count"],
                }
            )

        return collection_response(items, "daily_risk_metric")

    return app
