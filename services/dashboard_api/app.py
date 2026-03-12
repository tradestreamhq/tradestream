"""
Strategy Performance Dashboard REST API — RMM Level 2.

Provides dashboard-focused endpoints for strategy performance metrics,
P&L history, trade history, and portfolio summaries.
"""

import logging
import math
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
    """Create the Dashboard API FastAPI application."""
    app = FastAPI(
        title="Dashboard API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/dashboard",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("dashboard-api", check_deps))

    strategies_router = APIRouter(prefix="/strategies", tags=["Strategies"])

    # --- GET /strategies/:id/performance ---

    @strategies_router.get("/{strategy_id}/performance")
    async def get_strategy_performance(
        strategy_id: str,
        period: str = Query(
            "30d", description="Time period", pattern="^(7d|30d|90d|all)$"
        ),
    ):
        """Return win rate, total P&L, Sharpe ratio, and max drawdown for a strategy."""
        # Verify strategy exists
        async with db_pool.acquire() as conn:
            spec = await conn.fetchrow(
                "SELECT id, name FROM strategy_specs WHERE id = $1::uuid",
                strategy_id,
            )
        if not spec:
            return not_found("Strategy", strategy_id)

        interval_map = {"7d": "7 days", "30d": "30 days", "90d": "90 days"}
        interval = interval_map.get(period)

        time_filter = (
            f"AND sp.period_start >= NOW() - INTERVAL '{interval}'" if interval else ""
        )

        perf_query = f"""
            SELECT COUNT(*) as total_records,
                   COALESCE(SUM(sp.total_trades), 0) as total_trades,
                   COALESCE(SUM(sp.winning_trades), 0) as winning_trades,
                   COALESCE(SUM(sp.losing_trades), 0) as losing_trades,
                   COALESCE(SUM(sp.total_return), 0) as total_pnl,
                   AVG(sp.sharpe_ratio) as avg_sharpe_ratio,
                   MIN(sp.max_drawdown) as max_drawdown,
                   AVG(sp.win_rate) as avg_win_rate,
                   AVG(sp.profit_factor) as avg_profit_factor,
                   AVG(sp.sortino_ratio) as avg_sortino_ratio,
                   AVG(sp.volatility) as avg_volatility
            FROM strategy_performance sp
            JOIN strategy_implementations si ON sp.implementation_id = si.id
            WHERE si.spec_id = $1::uuid
            {time_filter}
        """

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(perf_query, strategy_id)

        metrics = dict(row) if row else {}
        total_trades = int(metrics.get("total_trades") or 0)
        winning_trades = int(metrics.get("winning_trades") or 0)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        def _safe_float(val):
            if val is None:
                return None
            f = float(val)
            return None if (math.isnan(f) or math.isinf(f)) else f

        return success_response(
            {
                "strategy_id": strategy_id,
                "strategy_name": spec["name"],
                "period": period,
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": int(metrics.get("losing_trades") or 0),
                "win_rate": round(win_rate, 4),
                "total_pnl": _safe_float(metrics.get("total_pnl")),
                "sharpe_ratio": _safe_float(metrics.get("avg_sharpe_ratio")),
                "max_drawdown": _safe_float(metrics.get("max_drawdown")),
                "profit_factor": _safe_float(metrics.get("avg_profit_factor")),
                "sortino_ratio": _safe_float(metrics.get("avg_sortino_ratio")),
                "volatility": _safe_float(metrics.get("avg_volatility")),
            },
            "strategy_performance",
            resource_id=strategy_id,
        )

    # --- GET /strategies/:id/trades ---

    @strategies_router.get("/{strategy_id}/trades")
    async def get_strategy_trades(
        strategy_id: str,
        pagination: PaginationParams = Depends(),
        status: Optional[str] = Query(
            None, description="Filter by status", pattern="^(OPEN|CLOSED)$"
        ),
    ):
        """Return recent trade history with entry/exit prices for a strategy."""
        # Verify strategy exists
        async with db_pool.acquire() as conn:
            spec = await conn.fetchrow(
                "SELECT id FROM strategy_specs WHERE id = $1::uuid",
                strategy_id,
            )
        if not spec:
            return not_found("Strategy", strategy_id)

        conditions = [
            "do.decision_id IN ("
            "  SELECT ad.id FROM agent_decisions ad"
            "  JOIN signals s ON ad.signal_id = s.signal_id::text"
            "  JOIN strategy_implementations si ON si.spec_id = $1::uuid"
            ")"
        ]
        params = [strategy_id]
        idx = 1

        if status == "CLOSED":
            conditions.append("do.exit_price IS NOT NULL")
        elif status == "OPEN":
            conditions.append("do.exit_price IS NULL")

        where = " AND ".join(conditions)
        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT do.id, do.instrument, do.action,
                   do.entry_price, do.exit_price,
                   do.pnl_absolute, do.pnl_percent,
                   do.hold_duration, do.exit_reason,
                   do.created_at, do.exit_timestamp
            FROM decision_outcomes do
            WHERE {where}
            ORDER BY do.created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"SELECT COUNT(*) FROM decision_outcomes do WHERE {where}"

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            for ts_field in ("created_at", "exit_timestamp"):
                if item.get(ts_field):
                    item[ts_field] = item[ts_field].isoformat()
            if item.get("hold_duration"):
                item["hold_duration"] = str(item["hold_duration"])
            for decimal_field in (
                "entry_price",
                "exit_price",
                "pnl_absolute",
                "pnl_percent",
            ):
                if item.get(decimal_field) is not None:
                    item[decimal_field] = float(item[decimal_field])
            items.append(item)

        return collection_response(
            items,
            "trade",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # --- GET /portfolio/summary ---

    portfolio_router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

    @portfolio_router.get("/summary")
    async def get_portfolio_summary():
        """Return current positions, unrealized P&L, and allocation breakdown."""
        positions_query = """
            SELECT symbol, quantity, avg_entry_price, unrealized_pnl, updated_at
            FROM paper_portfolio
            WHERE quantity != 0
            ORDER BY symbol
        """
        trades_query = """
            SELECT COUNT(*) as total_trades,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                   SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades,
                   COALESCE(SUM(pnl), 0) as total_realized_pnl
            FROM paper_trades
            WHERE status = 'CLOSED'
        """
        open_trades_query = """
            SELECT COUNT(*) as open_count
            FROM paper_trades
            WHERE status = 'OPEN'
        """

        async with db_pool.acquire() as conn:
            positions = await conn.fetch(positions_query)
            trade_stats = await conn.fetchrow(trades_query)
            open_count = await conn.fetchrow(open_trades_query)

        pos_list = []
        total_unrealized = 0.0
        total_exposure = 0.0
        for row in positions:
            item = dict(row)
            if item.get("updated_at"):
                item["updated_at"] = item["updated_at"].isoformat()
            item["quantity"] = float(item["quantity"])
            item["avg_entry_price"] = float(item["avg_entry_price"])
            item["unrealized_pnl"] = float(item["unrealized_pnl"])
            exposure = abs(item["quantity"] * item["avg_entry_price"])
            item["exposure"] = exposure
            total_unrealized += item["unrealized_pnl"]
            total_exposure += exposure
            pos_list.append(item)

        # Compute allocation breakdown
        allocation = {}
        for pos in pos_list:
            pct = (
                round(pos["exposure"] / total_exposure, 4) if total_exposure > 0 else 0
            )
            allocation[pos["symbol"]] = pct

        stats = dict(trade_stats) if trade_stats else {}
        total_realized = float(stats.get("total_realized_pnl") or 0)

        return success_response(
            {
                "positions": pos_list,
                "position_count": len(pos_list),
                "open_trade_count": int(open_count["open_count"]) if open_count else 0,
                "total_unrealized_pnl": total_unrealized,
                "total_realized_pnl": total_realized,
                "total_pnl": total_realized + total_unrealized,
                "total_exposure": total_exposure,
                "allocation": allocation,
                "trade_stats": {
                    "total_trades": int(stats.get("total_trades") or 0),
                    "winning_trades": int(stats.get("winning_trades") or 0),
                    "losing_trades": int(stats.get("losing_trades") or 0),
                },
            },
            "portfolio_summary",
        )

    app.include_router(strategies_router)
    app.include_router(portfolio_router)
    return app
