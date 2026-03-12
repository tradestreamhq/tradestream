"""
Fee Calculator REST API — RMM Level 2.

Provides endpoints for fee schedule management and fee calculation
across different venue types (maker/taker, flat, tiered volume-based).
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Fee Calculation Logic ---


def calculate_maker_taker_fee(
    size: Decimal, price: Decimal, is_maker: bool, schedule: Dict[str, Any]
) -> tuple[Decimal, Decimal]:
    """Calculate fee for maker/taker percentage model. Returns (fee_amount, fee_rate)."""
    rate = Decimal(str(schedule["maker_rate"] if is_maker else schedule["taker_rate"]))
    notional = size * price
    return (notional * rate, rate)


def calculate_flat_fee(schedule: Dict[str, Any]) -> tuple[Decimal, Decimal]:
    """Calculate fee for flat per-trade model. Returns (fee_amount, fee_rate=0)."""
    return (Decimal(str(schedule["flat_fee"])), Decimal("0"))


def calculate_tiered_fee(
    size: Decimal,
    price: Decimal,
    monthly_volume: Decimal,
    schedule: Dict[str, Any],
) -> tuple[Decimal, Decimal]:
    """Calculate fee for tiered volume-based model. Returns (fee_amount, fee_rate).

    Tiers are a JSON array sorted by min_volume ascending:
    [{"min_volume": 0, "max_volume": 100000, "rate": "0.001"},
     {"min_volume": 100000, "max_volume": null, "rate": "0.0005"}]
    """
    tiers = schedule["tiers"]
    if isinstance(tiers, str):
        tiers = json.loads(tiers)

    rate = Decimal("0")
    for tier in tiers:
        min_vol = Decimal(str(tier["min_volume"]))
        max_vol = tier.get("max_volume")
        if monthly_volume >= min_vol and (
            max_vol is None or monthly_volume < Decimal(str(max_vol))
        ):
            rate = Decimal(str(tier["rate"]))
            break

    notional = size * price
    return (notional * rate, rate)


def calculate_fee(
    size: Decimal,
    price: Decimal,
    is_maker: bool,
    schedule: Dict[str, Any],
    monthly_volume: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    """Route to the correct fee model and return (fee_amount, fee_rate)."""
    model = schedule["fee_model"]
    if model == "MAKER_TAKER":
        return calculate_maker_taker_fee(size, price, is_maker, schedule)
    elif model == "FLAT":
        return calculate_flat_fee(schedule)
    elif model == "TIERED":
        return calculate_tiered_fee(size, price, monthly_volume, schedule)
    else:
        raise ValueError(f"Unknown fee model: {model}")


# --- Request DTOs ---


class FeeCalculationRequest(BaseModel):
    exchange: str = Field(..., description="Exchange/venue name")
    side: str = Field(..., description="BUY or SELL", pattern="^(BUY|SELL)$")
    size: float = Field(..., gt=0, description="Trade size")
    price: float = Field(..., gt=0, description="Trade price")
    is_maker: bool = Field(False, description="Whether order is a maker order")
    symbol: str = Field("", description="Trading pair symbol")
    strategy_id: Optional[str] = Field(None, description="Strategy ID for tracking")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Fee Calculator API FastAPI application."""
    app = FastAPI(
        title="Fee Calculator API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/fees",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("fee-api", check_deps))

    # --- Fee Schedules ---

    @app.get("/schedule", tags=["Fee Schedules"])
    async def list_fee_schedules():
        """List all configured fee schedules."""
        query = """
            SELECT id, exchange, fee_model, maker_rate, taker_rate,
                   flat_fee, tiers, fee_currency, is_active,
                   created_at, updated_at
            FROM fee_schedules
            ORDER BY exchange
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            for field in ("maker_rate", "taker_rate", "flat_fee"):
                if item.get(field) is not None:
                    item[field] = float(item[field])
            if item.get("tiers") and isinstance(item["tiers"], str):
                item["tiers"] = json.loads(item["tiers"])
            for ts_field in ("created_at", "updated_at"):
                if item.get(ts_field):
                    item[ts_field] = item[ts_field].isoformat()
            items.append(item)

        return collection_response(items, "fee_schedule")

    # --- Fee Calculation ---

    @app.post("/calculate", tags=["Fee Calculation"])
    async def calculate_trade_fee(body: FeeCalculationRequest):
        """Calculate fee for a given trade and optionally record it."""
        query = """
            SELECT id, exchange, fee_model, maker_rate, taker_rate,
                   flat_fee, tiers, fee_currency, is_active
            FROM fee_schedules
            WHERE exchange = $1 AND is_active = TRUE
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, body.exchange)

        if not row:
            return not_found("Fee schedule", body.exchange)

        schedule = dict(row)

        # For tiered model, get monthly volume
        monthly_volume = Decimal("0")
        if schedule["fee_model"] == "TIERED":
            vol_query = """
                SELECT COALESCE(SUM(size * price), 0) as volume
                FROM trade_fees
                WHERE exchange = $1
                  AND date_trunc('month', created_at) = date_trunc('month', NOW())
            """
            async with db_pool.acquire() as conn:
                vol_row = await conn.fetchrow(vol_query, body.exchange)
            monthly_volume = Decimal(str(vol_row["volume"]))

        size = Decimal(str(body.size))
        price = Decimal(str(body.price))
        fee_amount, fee_rate = calculate_fee(
            size, price, body.is_maker, schedule, monthly_volume
        )

        # Record the fee
        insert_query = """
            INSERT INTO trade_fees
                (strategy_id, exchange, symbol, side, size, price,
                 is_maker, fee_amount, fee_rate, fee_currency, fee_model)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id
        """
        strategy_id = None
        if body.strategy_id:
            import uuid

            strategy_id = uuid.UUID(body.strategy_id)

        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                insert_query,
                strategy_id,
                body.exchange,
                body.symbol,
                body.side,
                size,
                price,
                body.is_maker,
                fee_amount,
                fee_rate,
                schedule["fee_currency"],
                schedule["fee_model"],
            )

        return success_response(
            {
                "fee_amount": float(fee_amount),
                "fee_rate": float(fee_rate),
                "fee_currency": schedule["fee_currency"],
                "fee_model": schedule["fee_model"],
                "notional_value": float(size * price),
            },
            "fee_calculation",
            resource_id=str(result["id"]),
        )

    # --- Monthly Fee Summary ---

    @app.get("/summary", tags=["Fee Summary"])
    async def get_fee_summary(
        strategy_id: Optional[str] = Query(None, description="Filter by strategy ID"),
        month: Optional[str] = Query(
            None, description="Month in YYYY-MM format (defaults to current month)"
        ),
    ):
        """Get monthly fee breakdown by strategy and exchange."""
        # Parse month or default to current
        if month:
            try:
                month_start = datetime.strptime(month, "%Y-%m").replace(day=1)
            except ValueError:
                return validation_error("month must be in YYYY-MM format")
        else:
            month_start = None

        conditions = []
        params = []
        param_idx = 1

        if month_start:
            conditions.append(
                f"date_trunc('month', created_at) = date_trunc('month', ${param_idx}::timestamp)"
            )
            params.append(month_start)
            param_idx += 1
        else:
            conditions.append(
                "date_trunc('month', created_at) = date_trunc('month', NOW())"
            )

        if strategy_id:
            import uuid as uuid_mod

            conditions.append(f"strategy_id = ${param_idx}")
            params.append(uuid_mod.UUID(strategy_id))
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        query = f"""
            SELECT
                exchange,
                strategy_id,
                fee_model,
                fee_currency,
                COUNT(*) as trade_count,
                SUM(fee_amount) as total_fees,
                AVG(fee_rate) as avg_fee_rate,
                SUM(size * price) as total_volume
            FROM trade_fees
            WHERE {where_clause}
            GROUP BY exchange, strategy_id, fee_model, fee_currency
            ORDER BY exchange, total_fees DESC
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        grand_total = Decimal("0")
        for row in rows:
            item = dict(row)
            item["strategy_id"] = (
                str(item["strategy_id"]) if item["strategy_id"] else None
            )
            item["trade_count"] = int(item["trade_count"])
            item["total_fees"] = float(item["total_fees"])
            item["avg_fee_rate"] = float(item["avg_fee_rate"])
            item["total_volume"] = float(item["total_volume"])
            grand_total += Decimal(str(item["total_fees"]))
            items.append(item)

        return success_response(
            {
                "month": month or datetime.utcnow().strftime("%Y-%m"),
                "breakdowns": items,
                "grand_total_fees": float(grand_total),
            },
            "fee_summary",
        )

    return app
