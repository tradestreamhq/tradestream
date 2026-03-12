"""
Backtesting REST API — provides endpoints for running and retrieving backtests.

Stores results in PostgreSQL for comparison across strategies and configurations.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

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


class CommissionConfig(BaseModel):
    flat_fee: float = Field(0.0, description="Flat fee per trade")
    percentage: float = Field(0.001, description="Percentage commission (0.001 = 0.1%)")
    min_commission: float = Field(0.0, description="Minimum commission per trade")


class BacktestRequest(BaseModel):
    strategy_name: str = Field(..., description="Name of the strategy to backtest")
    strategy_params: Dict[str, Any] = Field(
        default_factory=dict, description="Strategy-specific parameters"
    )
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")
    initial_capital: float = Field(10000.0, ge=0, description="Initial capital")
    commission: Optional[CommissionConfig] = Field(
        None, description="Commission model configuration"
    )
    position_size_pct: float = Field(
        1.0, ge=0.01, le=1.0, description="Fraction of capital per trade"
    )
    candles: List[Dict[str, float]] = Field(
        ...,
        description="List of OHLCV candle dicts with open, high, low, close, volume",
    )


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Backtesting REST API FastAPI application."""
    app = FastAPI(
        title="Backtesting API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/backtesting",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("backtesting-api", check_deps))

    router = APIRouter(prefix="/backtests", tags=["Backtests"])

    @router.post("", status_code=201)
    async def run_backtest(body: BacktestRequest):
        """Run a backtest and store results."""
        import numpy as np
        import pandas as pd

        from services.backtesting.engine import (
            BacktestConfig,
            BacktestEngine,
            CommissionModel,
        )
        from services.backtesting.vectorbt_runner import VectorBTRunner

        if len(body.candles) < 2:
            return validation_error("At least 2 candles are required")

        # Build OHLCV DataFrame
        ohlcv = pd.DataFrame(body.candles)
        required_cols = {"open", "high", "low", "close", "volume"}
        if not required_cols.issubset(ohlcv.columns):
            missing = required_cols - set(ohlcv.columns)
            return validation_error(f"Missing columns: {missing}")

        ohlcv.index = pd.date_range(start="2020-01-01", periods=len(ohlcv), freq="1min")

        # Generate signals using the existing VectorBT runner
        runner = VectorBTRunner()
        try:
            entry_signals, exit_signals = runner._generate_signals(
                ohlcv, body.strategy_name, body.strategy_params
            )
        except ValueError as e:
            return validation_error(str(e))

        # Configure and run engine
        commission = CommissionModel(
            flat_fee=body.commission.flat_fee if body.commission else 0.0,
            percentage=body.commission.percentage if body.commission else 0.001,
            min_commission=(body.commission.min_commission if body.commission else 0.0),
        )
        config = BacktestConfig(
            start_date=body.start_date,
            end_date=body.end_date,
            initial_capital=body.initial_capital,
            commission=commission,
            position_size_pct=body.position_size_pct,
        )
        engine = BacktestEngine(config)
        summary = engine.run(
            ohlcv,
            entry_signals,
            exit_signals,
            strategy_name=body.strategy_name,
            strategy_params=body.strategy_params,
        )

        # Store in DB
        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO backtest_results (
                        backtest_id, strategy_name, config, start_date,
                        end_date, initial_capital, final_capital,
                        total_return, annualized_return, sharpe_ratio,
                        sortino_ratio, max_drawdown,
                        max_drawdown_duration_bars, number_of_trades,
                        win_rate, profit_factor,
                        avg_holding_period_bars, avg_win, avg_loss,
                        total_commission, trades, created_at
                    ) VALUES (
                        $1, $2, $3::jsonb, $4, $5,
                        $6, $7, $8, $9, $10, $11,
                        $12, $13, $14, $15, $16,
                        $17, $18, $19, $20, $21::jsonb, $22
                    )
                    """,
                    summary.backtest_id,
                    summary.strategy_name,
                    json.dumps(summary.config),
                    summary.start_date,
                    summary.end_date,
                    summary.initial_capital,
                    summary.final_capital,
                    summary.total_return,
                    summary.annualized_return,
                    summary.sharpe_ratio,
                    summary.sortino_ratio,
                    summary.max_drawdown,
                    summary.max_drawdown_duration_bars,
                    summary.number_of_trades,
                    summary.win_rate,
                    summary.profit_factor,
                    summary.avg_holding_period_bars,
                    summary.avg_win,
                    summary.avg_loss,
                    summary.total_commission,
                    json.dumps(summary.trades),
                    summary.created_at,
                )
        except Exception as e:
            logger.error("Failed to store backtest result: %s", e)
            return server_error(f"Backtest ran successfully but storage failed: {e}")

        result = summary.to_dict()
        # Omit equity_curve from response to keep payload small
        result.pop("equity_curve", None)

        return success_response(
            result,
            "backtest_result",
            resource_id=summary.backtest_id,
            status_code=201,
        )

    @router.get("")
    async def list_backtests(
        pagination: PaginationParams = Depends(),
        strategy_name: Optional[str] = Query(
            None, description="Filter by strategy name"
        ),
        min_sharpe: Optional[float] = Query(
            None, description="Minimum Sharpe ratio filter"
        ),
        order_by: Optional[str] = Query(
            "created_at",
            description="Sort field",
            pattern=("^(created_at|total_return|sharpe_ratio|number_of_trades)$"),
        ),
    ):
        """List stored backtest results with optional filters."""
        conditions = ["1=1"]
        params: list = []
        idx = 0

        if strategy_name is not None:
            idx += 1
            conditions.append(f"strategy_name = ${idx}")
            params.append(strategy_name)

        if min_sharpe is not None:
            idx += 1
            conditions.append(f"sharpe_ratio >= ${idx}")
            params.append(min_sharpe)

        order_map = {
            "created_at": "created_at DESC",
            "total_return": "total_return DESC",
            "sharpe_ratio": "sharpe_ratio DESC",
            "number_of_trades": "number_of_trades DESC",
        }
        order_clause = order_map.get(order_by, "created_at DESC")

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        where = " AND ".join(conditions)
        query = f"""
            SELECT backtest_id, strategy_name, config, start_date,
                   end_date, initial_capital, final_capital,
                   total_return, annualized_return, sharpe_ratio,
                   sortino_ratio, max_drawdown,
                   max_drawdown_duration_bars, number_of_trades,
                   win_rate, profit_factor, avg_holding_period_bars,
                   avg_win, avg_loss, total_commission, created_at
            FROM backtest_results
            WHERE {where}
            ORDER BY {order_clause}
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"""
            SELECT COUNT(*) FROM backtest_results WHERE {where}
        """

        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                total = await conn.fetchval(count_query, *params[:-2])
        except Exception as e:
            logger.error("Failed to list backtests: %s", e)
            return server_error(str(e))

        items = []
        for row in rows:
            item = dict(row)
            if item.get("created_at") and hasattr(item["created_at"], "isoformat"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)

        return collection_response(
            items,
            "backtest_result",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @router.get("/{backtest_id}")
    async def get_backtest(backtest_id: str):
        """Retrieve a specific backtest result."""
        query = """
            SELECT backtest_id, strategy_name, config, start_date,
                   end_date, initial_capital, final_capital,
                   total_return, annualized_return, sharpe_ratio,
                   sortino_ratio, max_drawdown,
                   max_drawdown_duration_bars, number_of_trades,
                   win_rate, profit_factor, avg_holding_period_bars,
                   avg_win, avg_loss, total_commission, trades,
                   created_at
            FROM backtest_results
            WHERE backtest_id = $1
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(query, backtest_id)
        except Exception as e:
            logger.error("Failed to get backtest: %s", e)
            return server_error(str(e))

        if not row:
            return not_found("Backtest", backtest_id)

        item = dict(row)
        if item.get("created_at") and hasattr(item["created_at"], "isoformat"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(item, "backtest_result", resource_id=backtest_id)

    @router.delete("/{backtest_id}", status_code=204)
    async def delete_backtest(backtest_id: str):
        """Delete a backtest result."""
        query = (
            "DELETE FROM backtest_results "
            "WHERE backtest_id = $1 RETURNING backtest_id"
        )
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(query, backtest_id)
        except Exception as e:
            logger.error("Failed to delete backtest: %s", e)
            return server_error(str(e))

        if not row:
            return not_found("Backtest", backtest_id)
        return None

    app.include_router(router)
    return app
