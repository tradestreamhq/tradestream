"""
Data Export and Report Generation API.

Provides endpoints for exporting trade history and portfolio data
as CSV or JSON, and generating performance reports with summary
statistics, equity curve data, and drawdown analysis.
"""

import csv
import io
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    success_response,
    server_error,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class PerformanceReportRequest(BaseModel):
    start_date: date = Field(..., description="Start date for the report period")
    end_date: date = Field(..., description="End date for the report period")
    strategy_id: Optional[str] = Field(
        None, description="Filter by strategy spec ID"
    )


# --- Helpers ---


def _float(val: Any) -> float:
    """Safely convert a DB value to float."""
    if val is None:
        return 0.0
    return float(val)


def _serialize_row(row: dict) -> dict:
    """Convert date/datetime values to ISO strings for JSON serialization."""
    out = {}
    for k, v in row.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, float):
            out[k] = v
        else:
            out[k] = v
    return out


def _rows_to_csv(rows: List[dict]) -> str:
    """Convert a list of dicts to a CSV string."""
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# --- Queries ---

TRADES_QUERY = """
    SELECT
        t.id, t.symbol, t.side, t.quantity, t.entry_price, t.exit_price,
        t.pnl, t.status, t.opened_at, t.closed_at, t.signal_id
    FROM paper_trades t
    WHERE 1=1
"""

TRADES_DATE_FILTER = """
    AND t.opened_at >= $%d AND t.opened_at < ($%d::date + interval '1 day')
"""

TRADES_STRATEGY_FILTER = """
    AND t.signal_id IN (
        SELECT s.id FROM signals s WHERE s.spec_id = $%d::uuid
    )
"""

PORTFOLIO_QUERY = """
    SELECT symbol, quantity, avg_entry_price, unrealized_pnl, updated_at
    FROM paper_portfolio
    ORDER BY symbol
"""

SUMMARY_STATS_QUERY = """
    SELECT
        COUNT(*)                                          AS total_trades,
        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)        AS winning_trades,
        SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END)       AS losing_trades,
        COALESCE(SUM(pnl), 0)                            AS total_pnl,
        COALESCE(AVG(pnl), 0)                            AS avg_pnl,
        COALESCE(MAX(pnl), 0)                            AS best_trade,
        COALESCE(MIN(pnl), 0)                            AS worst_trade
    FROM paper_trades
    WHERE status = 'CLOSED'
"""

EQUITY_CURVE_QUERY = """
    SELECT
        closed_at::date AS trade_date,
        SUM(pnl) OVER (ORDER BY closed_at) AS cumulative_pnl,
        pnl
    FROM paper_trades
    WHERE status = 'CLOSED'
"""


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Export & Report API FastAPI application."""
    app = FastAPI(
        title="Export & Report API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("export-api", check_deps))

    # ------------------------------------------------------------------ #
    #  Export trades                                                       #
    # ------------------------------------------------------------------ #

    @app.get("/export/trades", tags=["Export"])
    async def export_trades(
        format: str = Query("json", pattern="^(csv|json)$"),
        start_date: Optional[date] = Query(None),
        end_date: Optional[date] = Query(None),
        strategy_id: Optional[str] = Query(None),
    ):
        """Export trade history as CSV or JSON."""
        query = TRADES_QUERY
        params: list = []
        idx = 1

        if start_date:
            params.append(start_date)
            params.append(end_date or date.today())
            query += TRADES_DATE_FILTER % (idx, idx + 1)
            idx += 2

        if strategy_id:
            params.append(strategy_id)
            query += TRADES_STRATEGY_FILTER % idx
            idx += 1

        query += "\n    ORDER BY t.opened_at DESC"

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        records = []
        for row in rows:
            item = dict(row)
            for key in ("quantity", "entry_price", "exit_price", "pnl"):
                if item.get(key) is not None:
                    item[key] = float(item[key])
            item = _serialize_row(item)
            if item.get("id"):
                item["id"] = str(item["id"])
            if item.get("signal_id"):
                item["signal_id"] = str(item["signal_id"])
            records.append(item)

        if format == "csv":
            csv_content = _rows_to_csv(records)
            return StreamingResponse(
                iter([csv_content]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=trades.csv"
                },
            )

        return success_response(
            {"trades": records, "count": len(records)},
            "trade_export",
        )

    # ------------------------------------------------------------------ #
    #  Export portfolio                                                    #
    # ------------------------------------------------------------------ #

    @app.get("/export/portfolio", tags=["Export"])
    async def export_portfolio(
        format: str = Query("json", pattern="^(csv|json)$"),
    ):
        """Export current portfolio positions as CSV or JSON."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(PORTFOLIO_QUERY)

        records = []
        for row in rows:
            item = dict(row)
            for key in ("quantity", "avg_entry_price", "unrealized_pnl"):
                if item.get(key) is not None:
                    item[key] = float(item[key])
            item = _serialize_row(item)
            records.append(item)

        if format == "csv":
            csv_content = _rows_to_csv(records)
            return StreamingResponse(
                iter([csv_content]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=portfolio.csv"
                },
            )

        return success_response(
            {"positions": records, "count": len(records)},
            "portfolio_export",
        )

    # ------------------------------------------------------------------ #
    #  Performance report                                                 #
    # ------------------------------------------------------------------ #

    @app.post("/reports/performance", tags=["Reports"])
    async def generate_performance_report(body: PerformanceReportRequest):
        """Generate a performance report for the given date range."""
        if body.end_date < body.start_date:
            return validation_error("end_date must be on or after start_date")

        date_filter = (
            " AND closed_at >= $1 AND closed_at < ($2::date + interval '1 day')"
        )
        strategy_filter = ""
        params: list = [body.start_date, body.end_date]

        if body.strategy_id:
            strategy_filter = (
                " AND signal_id IN "
                "(SELECT id FROM signals WHERE spec_id = $3::uuid)"
            )
            params.append(body.strategy_id)

        # --- summary stats ---
        stats_q = SUMMARY_STATS_QUERY + date_filter + strategy_filter
        async with db_pool.acquire() as conn:
            stats_row = await conn.fetchrow(stats_q, *params)

        total_trades = int(stats_row["total_trades"]) if stats_row["total_trades"] else 0
        winning = int(stats_row["winning_trades"]) if stats_row["winning_trades"] else 0
        losing = int(stats_row["losing_trades"]) if stats_row["losing_trades"] else 0

        summary = {
            "total_trades": total_trades,
            "winning_trades": winning,
            "losing_trades": losing,
            "win_rate": round(winning / total_trades, 4) if total_trades > 0 else 0,
            "total_pnl": _float(stats_row["total_pnl"]),
            "avg_pnl": round(_float(stats_row["avg_pnl"]), 4),
            "best_trade": _float(stats_row["best_trade"]),
            "worst_trade": _float(stats_row["worst_trade"]),
        }

        # --- trade log ---
        trades_q = (
            TRADES_QUERY
            + " AND t.status = 'CLOSED'"
            + date_filter.replace("closed_at", "t.closed_at")
        )
        if body.strategy_id:
            trades_q += TRADES_STRATEGY_FILTER % (3,)

        trades_q += "\n    ORDER BY t.closed_at ASC"

        async with db_pool.acquire() as conn:
            trade_rows = await conn.fetch(trades_q, *params)

        trade_log = []
        for row in trade_rows:
            item = dict(row)
            for key in ("quantity", "entry_price", "exit_price", "pnl"):
                if item.get(key) is not None:
                    item[key] = float(item[key])
            item = _serialize_row(item)
            if item.get("id"):
                item["id"] = str(item["id"])
            if item.get("signal_id"):
                item["signal_id"] = str(item["signal_id"])
            trade_log.append(item)

        # --- equity curve ---
        equity_q = (
            EQUITY_CURVE_QUERY
            + date_filter.replace("closed_at", "closed_at")
        )
        if body.strategy_id:
            equity_q += strategy_filter.replace("$3", "$3")

        equity_q += "\n    ORDER BY closed_at ASC"

        async with db_pool.acquire() as conn:
            equity_rows = await conn.fetch(equity_q, *params)

        equity_curve = []
        for row in equity_rows:
            equity_curve.append(
                {
                    "date": row["trade_date"].isoformat()
                    if row["trade_date"]
                    else None,
                    "cumulative_pnl": _float(row["cumulative_pnl"]),
                    "pnl": _float(row["pnl"]),
                }
            )

        # --- drawdown analysis ---
        peak = 0.0
        max_drawdown = 0.0
        max_drawdown_pct = 0.0
        drawdown_periods = []
        current_dd_start = None

        for point in equity_curve:
            cum = point["cumulative_pnl"]
            if cum > peak:
                if current_dd_start is not None:
                    drawdown_periods.append(
                        {
                            "start": current_dd_start,
                            "end": point["date"],
                        }
                    )
                    current_dd_start = None
                peak = cum
            else:
                dd = peak - cum
                if dd > max_drawdown:
                    max_drawdown = dd
                    max_drawdown_pct = (
                        round(dd / peak, 4) if peak > 0 else 0
                    )
                if current_dd_start is None and dd > 0:
                    current_dd_start = point["date"]

        if current_dd_start is not None:
            drawdown_periods.append(
                {"start": current_dd_start, "end": None}
            )

        drawdown = {
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown_pct,
            "drawdown_periods": drawdown_periods,
        }

        return success_response(
            {
                "period": {
                    "start_date": body.start_date.isoformat(),
                    "end_date": body.end_date.isoformat(),
                },
                "strategy_id": body.strategy_id,
                "summary": summary,
                "trade_log": trade_log,
                "equity_curve": equity_curve,
                "drawdown": drawdown,
            },
            "performance_report",
        )

    return app
