"""
Data Export and Reporting REST API — RMM Level 2.

Provides endpoints for exporting trade history, signals, performance metrics,
and candle data in CSV/JSON formats, plus report generation endpoints.
"""

import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query

from services.export_api.formatters import to_csv_response, to_json_export_response
from services.export_api.report_generator import (
    risk_exposure_report,
    strategy_performance_summary,
    trade_recap,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

_VALID_FORMATS = ("csv", "json")


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Export API FastAPI application."""
    app = FastAPI(
        title="Data Export & Reporting API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/export",
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

    export_router = APIRouter(tags=["Export"])
    report_router = APIRouter(prefix="/reports", tags=["Reports"])

    # --- Export endpoints ---

    @export_router.get("/trades")
    async def export_trades(
        pagination: PaginationParams = Depends(),
        format: str = Query("json", description="Output format: csv or json"),
        start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
        end_date: Optional[str] = Query(None, description="End date (ISO format)"),
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        status: Optional[str] = Query(
            None, description="Filter by status (OPEN/CLOSED)"
        ),
    ):
        """Export trade history (paper_trades) as CSV or JSON."""
        if format not in _VALID_FORMATS:
            return validation_error(
                f"Invalid format '{format}'. Must be one of: {', '.join(_VALID_FORMATS)}"
            )

        conditions = ["1=1"]
        params = []
        idx = 0

        if start_date:
            idx += 1
            conditions.append(f"opened_at >= ${idx}::timestamp")
            params.append(start_date)
        if end_date:
            idx += 1
            conditions.append(f"opened_at <= ${idx}::timestamp")
            params.append(end_date)
        if symbol:
            idx += 1
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
        if status:
            idx += 1
            conditions.append(f"status = ${idx}")
            params.append(status)

        where = " AND ".join(conditions)
        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT id, signal_id, symbol, side, entry_price, exit_price,
                   quantity, pnl, opened_at, closed_at, status
            FROM paper_trades
            WHERE {where}
            ORDER BY opened_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"SELECT COUNT(*) FROM paper_trades WHERE {where}"

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                total = await conn.fetchval(count_query, *params[:-2])
        except Exception as e:
            logger.error("Failed to export trades: %s", e)
            return server_error(str(e))

        items = [_row_to_dict(row) for row in rows]

        if format == "csv":
            return to_csv_response(items, "trades.csv")
        return to_json_export_response(
            items, total, pagination.limit, pagination.offset
        )

    @export_router.get("/signals")
    async def export_signals(
        pagination: PaginationParams = Depends(),
        format: str = Query("json", description="Output format: csv or json"),
        start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
        end_date: Optional[str] = Query(None, description="End date (ISO format)"),
        instrument: Optional[str] = Query(None, description="Filter by instrument"),
        signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    ):
        """Export signal history as CSV or JSON."""
        if format not in _VALID_FORMATS:
            return validation_error(
                f"Invalid format '{format}'. Must be one of: {', '.join(_VALID_FORMATS)}"
            )

        conditions = ["1=1"]
        params = []
        idx = 0

        if start_date:
            idx += 1
            conditions.append(f"created_at >= ${idx}::timestamp")
            params.append(start_date)
        if end_date:
            idx += 1
            conditions.append(f"created_at <= ${idx}::timestamp")
            params.append(end_date)
        if instrument:
            idx += 1
            conditions.append(f"instrument = ${idx}")
            params.append(instrument)
        if signal_type:
            idx += 1
            conditions.append(f"signal_type = ${idx}")
            params.append(signal_type)

        where = " AND ".join(conditions)
        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT id, spec_id, implementation_id, instrument, signal_type,
                   strength, price, stop_loss, take_profit, position_size,
                   outcome, exit_price, pnl, pnl_percent, timeframe, created_at
            FROM signals
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"SELECT COUNT(*) FROM signals WHERE {where}"

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                total = await conn.fetchval(count_query, *params[:-2])
        except Exception as e:
            logger.error("Failed to export signals: %s", e)
            return server_error(str(e))

        items = [_row_to_dict(row) for row in rows]

        if format == "csv":
            return to_csv_response(items, "signals.csv")
        return to_json_export_response(
            items, total, pagination.limit, pagination.offset
        )

    @export_router.get("/performance")
    async def export_performance(
        pagination: PaginationParams = Depends(),
        format: str = Query("json", description="Output format: csv or json"),
        start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
        end_date: Optional[str] = Query(None, description="End date (ISO format)"),
        implementation_id: Optional[str] = Query(
            None, description="Filter by implementation"
        ),
        environment: Optional[str] = Query(
            None, description="Filter by environment (BACKTEST/PAPER/LIVE)"
        ),
        instrument: Optional[str] = Query(None, description="Filter by instrument"),
    ):
        """Export performance metrics as CSV or JSON."""
        if format not in _VALID_FORMATS:
            return validation_error(
                f"Invalid format '{format}'. Must be one of: {', '.join(_VALID_FORMATS)}"
            )

        conditions = ["1=1"]
        params = []
        idx = 0

        if start_date:
            idx += 1
            conditions.append(f"period_start >= ${idx}::timestamp")
            params.append(start_date)
        if end_date:
            idx += 1
            conditions.append(f"period_end <= ${idx}::timestamp")
            params.append(end_date)
        if implementation_id:
            idx += 1
            conditions.append(f"implementation_id = ${idx}::uuid")
            params.append(implementation_id)
        if environment:
            idx += 1
            conditions.append(f"environment = ${idx}")
            params.append(environment)
        if instrument:
            idx += 1
            conditions.append(f"instrument = ${idx}")
            params.append(instrument)

        where = " AND ".join(conditions)
        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT id, implementation_id, period_start, period_end,
                   sharpe_ratio, sortino_ratio, calmar_ratio, win_rate, profit_factor,
                   max_drawdown, avg_drawdown, volatility, var_95,
                   total_trades, winning_trades, losing_trades,
                   avg_trade_duration_seconds, avg_profit_per_trade,
                   total_return, annualized_return,
                   environment, instrument, timeframe, created_at
            FROM strategy_performance
            WHERE {where}
            ORDER BY period_start DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"SELECT COUNT(*) FROM strategy_performance WHERE {where}"

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                total = await conn.fetchval(count_query, *params[:-2])
        except Exception as e:
            logger.error("Failed to export performance: %s", e)
            return server_error(str(e))

        items = [_row_to_dict(row) for row in rows]

        if format == "csv":
            return to_csv_response(items, "performance.csv")
        return to_json_export_response(
            items, total, pagination.limit, pagination.offset
        )

    @export_router.get("/candles")
    async def export_candles(
        pagination: PaginationParams = Depends(),
        format: str = Query("json", description="Output format: csv or json"),
        start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
        end_date: Optional[str] = Query(None, description="End date (ISO format)"),
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        timeframe: Optional[str] = Query(None, description="Filter by timeframe"),
    ):
        """Export candle data as CSV or JSON.

        Note: Candle data is sourced from InfluxDB in production. This endpoint
        queries the candle_cache table which stores recent candle snapshots in
        PostgreSQL for export convenience.
        """
        if format not in _VALID_FORMATS:
            return validation_error(
                f"Invalid format '{format}'. Must be one of: {', '.join(_VALID_FORMATS)}"
            )

        conditions = ["1=1"]
        params = []
        idx = 0

        if start_date:
            idx += 1
            conditions.append(f"timestamp >= ${idx}::timestamp")
            params.append(start_date)
        if end_date:
            idx += 1
            conditions.append(f"timestamp <= ${idx}::timestamp")
            params.append(end_date)
        if symbol:
            idx += 1
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
        if timeframe:
            idx += 1
            conditions.append(f"timeframe = ${idx}")
            params.append(timeframe)

        where = " AND ".join(conditions)
        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        query = f"""
            SELECT symbol, timeframe, timestamp, open, high, low, close, volume
            FROM candle_cache
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"SELECT COUNT(*) FROM candle_cache WHERE {where}"

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                total = await conn.fetchval(count_query, *params[:-2])
        except Exception as e:
            logger.error("Failed to export candles: %s", e)
            return server_error(str(e))

        items = [_row_to_dict(row) for row in rows]

        if format == "csv":
            return to_csv_response(items, "candles.csv")
        return to_json_export_response(
            items, total, pagination.limit, pagination.offset
        )

    # --- Report endpoints ---

    @report_router.get("/performance-summary/{implementation_id}")
    async def get_performance_summary(implementation_id: str):
        """Generate a strategy performance summary report (PDF-ready JSON)."""
        try:
            async with db_pool.acquire() as conn:
                perf_rows = await conn.fetch(
                    """
                    SELECT period_start, period_end, sharpe_ratio, sortino_ratio,
                           win_rate, profit_factor, max_drawdown, total_trades,
                           winning_trades, losing_trades, total_return
                    FROM strategy_performance
                    WHERE implementation_id = $1::uuid
                    ORDER BY period_start DESC
                    """,
                    implementation_id,
                )
                signal_rows = await conn.fetch(
                    """
                    SELECT pnl FROM signals
                    WHERE implementation_id = $1::uuid AND pnl IS NOT NULL
                    """,
                    implementation_id,
                )
        except Exception as e:
            logger.error("Failed to generate performance summary: %s", e)
            return server_error(str(e))

        if not perf_rows:
            return not_found("Performance data for implementation", implementation_id)

        report = strategy_performance_summary(
            implementation_id,
            [dict(r) for r in perf_rows],
            [dict(r) for r in signal_rows],
        )
        return success_response(report, "report", resource_id=implementation_id)

    @report_router.get("/trade-recap")
    async def get_trade_recap(
        start_date: str = Query(..., description="Period start date (ISO format)"),
        end_date: str = Query(..., description="Period end date (ISO format)"),
        period_label: str = Query(
            ..., description="Period label (e.g. '2026-W10', '2026-02')"
        ),
        instrument: Optional[str] = Query(None, description="Filter by instrument"),
    ):
        """Generate a periodic trade recap report."""
        conditions = ["created_at >= $1::timestamp", "created_at <= $2::timestamp"]
        params = [start_date, end_date]
        idx = 2

        if instrument:
            idx += 1
            conditions.append(f"instrument = ${idx}")
            params.append(instrument)

        where = " AND ".join(conditions)
        query = f"""
            SELECT id, instrument, signal_type, price, exit_price,
                   pnl, outcome, created_at
            FROM signals
            WHERE {where}
            ORDER BY created_at DESC
        """

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
        except Exception as e:
            logger.error("Failed to generate trade recap: %s", e)
            return server_error(str(e))

        report = trade_recap([dict(r) for r in rows], period_label)
        return success_response(report, "report")

    @report_router.get("/risk-exposure")
    async def get_risk_exposure(
        implementation_id: Optional[str] = Query(
            None, description="Filter by implementation"
        ),
    ):
        """Generate a risk exposure report."""
        try:
            async with db_pool.acquire() as conn:
                perf_conditions = "1=1"
                perf_params = []
                if implementation_id:
                    perf_conditions = "implementation_id = $1::uuid"
                    perf_params = [implementation_id]

                perf_rows = await conn.fetch(
                    f"""
                    SELECT max_drawdown, volatility, var_95
                    FROM strategy_performance
                    WHERE {perf_conditions}
                    ORDER BY created_at DESC
                    LIMIT 100
                    """,
                    *perf_params,
                )
                open_trades = await conn.fetch(
                    """
                    SELECT symbol, quantity, entry_price
                    FROM paper_trades
                    WHERE status = 'OPEN'
                    """
                )
        except Exception as e:
            logger.error("Failed to generate risk exposure report: %s", e)
            return server_error(str(e))

        report = risk_exposure_report(
            [dict(r) for r in perf_rows],
            [dict(r) for r in open_trades],
        )
        return success_response(report, "report")

    app.include_router(export_router)
    app.include_router(report_router)
    return app


def _row_to_dict(row) -> dict:
    """Convert an asyncpg Record to a serializable dict."""
    d = dict(row)
    for key, value in d.items():
        if hasattr(value, "isoformat"):
            d[key] = value.isoformat()
        elif isinstance(value, (bytes, bytearray)):
            d[key] = value.hex()
    # Convert UUIDs to strings
    for key in ("id", "signal_id", "spec_id", "implementation_id"):
        if key in d and d[key] is not None:
            d[key] = str(d[key])
    return d
