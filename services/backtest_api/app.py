"""
Backtest REST API — RMM Level 2.

Provides endpoints for creating, retrieving, and listing backtests.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.backtest_api.engine import (
    BacktestResult,
    Candle,
    run_backtest,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class BacktestRequest(BaseModel):
    strategy_id: str = Field(..., description="Strategy identifier")
    symbol: str = Field(..., description="Trading instrument symbol")
    timeframe: str = Field(
        ..., description="Candle timeframe (e.g. 1h, 4h, 1d)", pattern="^[0-9]+[mhd]$"
    )
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Backtest API FastAPI application."""
    app = FastAPI(
        title="Backtest API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/backtest",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("backtest-api", check_deps))

    # --- Create backtest ---

    @app.post("", tags=["Backtest"])
    async def create_backtest(body: BacktestRequest):
        """Run a backtest for a strategy against historical data."""
        if body.end_date <= body.start_date:
            return validation_error("end_date must be after start_date")

        # Fetch historical OHLCV data from the candles table
        candle_query = """
            SELECT timestamp, open, high, low, close, volume
            FROM candles
            WHERE symbol = $1 AND timeframe = $2
              AND timestamp >= $3 AND timestamp <= $4
            ORDER BY timestamp
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    candle_query,
                    body.symbol,
                    body.timeframe,
                    body.start_date,
                    body.end_date,
                )
        except Exception as e:
            logger.exception("Failed to fetch candles")
            return server_error(f"Failed to fetch market data: {e}")

        if not rows:
            return validation_error(
                f"No OHLCV data found for {body.symbol} ({body.timeframe}) "
                f"between {body.start_date.isoformat()} and {body.end_date.isoformat()}"
            )

        candles = [
            Candle(
                timestamp=row["timestamp"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            for row in rows
        ]

        # Run the backtest engine
        result = run_backtest(candles, body.strategy_id)

        # Persist results
        backtest_id = str(uuid.uuid4())
        try:
            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO backtests
                            (id, strategy_id, symbol, timeframe, start_date, end_date,
                             status, total_return, sharpe_ratio, max_drawdown,
                             win_rate, profit_factor, total_trades, completed_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        """,
                        uuid.UUID(backtest_id),
                        body.strategy_id,
                        body.symbol,
                        body.timeframe,
                        body.start_date,
                        body.end_date,
                        "COMPLETED",
                        result.total_return,
                        result.sharpe_ratio,
                        result.max_drawdown,
                        result.win_rate,
                        result.profit_factor,
                        result.total_trades,
                        datetime.now(timezone.utc),
                    )

                    # Insert equity curve points (sample if too many)
                    curve = result.equity_curve
                    max_points = 500
                    if len(curve) > max_points:
                        step = len(curve) / max_points
                        curve = [curve[int(i * step)] for i in range(max_points)]

                    if curve:
                        eq_records = [
                            (
                                uuid.UUID(backtest_id),
                                pt.timestamp,
                                pt.equity,
                                pt.drawdown,
                            )
                            for pt in curve
                        ]
                        await conn.executemany(
                            """
                            INSERT INTO backtest_equity_curve
                                (backtest_id, timestamp, equity, drawdown)
                            VALUES ($1, $2, $3, $4)
                            """,
                            eq_records,
                        )

                    # Insert trades
                    if result.trades:
                        trade_records = [
                            (
                                uuid.UUID(backtest_id),
                                t.side,
                                t.entry_time,
                                t.exit_time,
                                t.entry_price,
                                t.exit_price,
                                t.quantity,
                                t.pnl,
                            )
                            for t in result.trades
                        ]
                        await conn.executemany(
                            """
                            INSERT INTO backtest_trades
                                (backtest_id, side, entry_time, exit_time,
                                 entry_price, exit_price, quantity, pnl)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """,
                            trade_records,
                        )
        except Exception as e:
            logger.exception("Failed to persist backtest results")
            return server_error(f"Failed to save backtest results: {e}")

        return success_response(
            {
                "strategy_id": body.strategy_id,
                "symbol": body.symbol,
                "timeframe": body.timeframe,
                "start_date": body.start_date.isoformat(),
                "end_date": body.end_date.isoformat(),
                "status": "COMPLETED",
                "total_return": result.total_return,
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": result.max_drawdown,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "total_trades": result.total_trades,
            },
            resource_type="backtest",
            resource_id=backtest_id,
            status_code=201,
        )

    # --- Get backtest by ID ---

    @app.get("/{backtest_id}", tags=["Backtest"])
    async def get_backtest(backtest_id: str):
        """Retrieve backtest results including equity curve data points."""
        try:
            bt_uuid = uuid.UUID(backtest_id)
        except ValueError:
            return validation_error(f"Invalid backtest ID format: {backtest_id}")

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, strategy_id, symbol, timeframe, start_date, end_date,
                       status, total_return, sharpe_ratio, max_drawdown,
                       win_rate, profit_factor, total_trades,
                       created_at, completed_at
                FROM backtests WHERE id = $1
                """,
                bt_uuid,
            )
            if not row:
                return not_found("Backtest", backtest_id)

            equity_rows = await conn.fetch(
                """
                SELECT timestamp, equity, drawdown
                FROM backtest_equity_curve
                WHERE backtest_id = $1
                ORDER BY timestamp
                """,
                bt_uuid,
            )

            trade_rows = await conn.fetch(
                """
                SELECT side, entry_time, exit_time, entry_price, exit_price,
                       quantity, pnl
                FROM backtest_trades
                WHERE backtest_id = $1
                ORDER BY entry_time
                """,
                bt_uuid,
            )

        backtest = dict(row)
        backtest["id"] = str(backtest["id"])
        for ts_field in ("start_date", "end_date", "created_at", "completed_at"):
            if backtest.get(ts_field):
                backtest[ts_field] = backtest[ts_field].isoformat()
        for num_field in (
            "total_return",
            "sharpe_ratio",
            "max_drawdown",
            "win_rate",
            "profit_factor",
        ):
            if backtest.get(num_field) is not None:
                backtest[num_field] = float(backtest[num_field])

        backtest["equity_curve"] = [
            {
                "timestamp": r["timestamp"].isoformat(),
                "equity": float(r["equity"]),
                "drawdown": float(r["drawdown"]),
            }
            for r in equity_rows
        ]

        backtest["trades"] = [
            {
                "side": r["side"],
                "entry_time": r["entry_time"].isoformat(),
                "exit_time": r["exit_time"].isoformat() if r["exit_time"] else None,
                "entry_price": float(r["entry_price"]),
                "exit_price": float(r["exit_price"]) if r["exit_price"] else None,
                "quantity": float(r["quantity"]),
                "pnl": float(r["pnl"]) if r["pnl"] is not None else None,
            }
            for r in trade_rows
        ]

        return success_response(backtest, "backtest", resource_id=backtest_id)

    # --- List backtests ---

    @app.get("", tags=["Backtest"])
    async def list_backtests(
        pagination: PaginationParams = Depends(),
        strategy_id: Optional[str] = Query(None, description="Filter by strategy ID"),
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        status: Optional[str] = Query(None, description="Filter by status"),
    ):
        """List backtests with pagination and optional filters."""
        conditions = []
        params = []
        idx = 1

        if strategy_id:
            conditions.append(f"strategy_id = ${idx}")
            params.append(strategy_id)
            idx += 1
        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        count_query = f"SELECT COUNT(*) FROM backtests {where}"
        list_query = f"""
            SELECT id, strategy_id, symbol, timeframe, start_date, end_date,
                   status, total_return, sharpe_ratio, max_drawdown,
                   win_rate, profit_factor, total_trades, created_at
            FROM backtests {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([pagination.limit, pagination.offset])

        async with db_pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params[: idx - 1])
            rows = await conn.fetch(list_query, *params)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            for ts_field in ("start_date", "end_date", "created_at"):
                if item.get(ts_field):
                    item[ts_field] = item[ts_field].isoformat()
            for num_field in (
                "total_return",
                "sharpe_ratio",
                "max_drawdown",
                "win_rate",
                "profit_factor",
            ):
                if item.get(num_field) is not None:
                    item[num_field] = float(item[num_field])
            items.append(item)

        return collection_response(
            items,
            "backtest",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    return app
