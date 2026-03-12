"""
Tax Lot Tracking REST API — RMM Level 2.

Maintains cost basis records for positions and supports FIFO, LIFO,
and specific identification disposal methods for tax reporting.
"""

import logging
import uuid
from datetime import datetime, timezone

import asyncpg
from fastapi import FastAPI, Query
from pydantic import BaseModel

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware
from services.tax_lots.methods import dispose_fifo, dispose_lifo, dispose_specific
from services.tax_lots.models import (
    AccountingMethod,
    AddLotRequest,
    DisposalRequest,
)

logger = logging.getLogger(__name__)


def _serialize_lot(row) -> dict:
    item = dict(row)
    item["lot_id"] = str(item["lot_id"])
    item["quantity"] = float(item["quantity"])
    item["cost_basis"] = float(item["cost_basis"])
    item["remaining_quantity"] = float(item["remaining_quantity"])
    if item.get("acquisition_date"):
        item["acquisition_date"] = item["acquisition_date"].isoformat()
    if item.get("created_at"):
        item["created_at"] = item["created_at"].isoformat()
    return item


def _serialize_gain(row) -> dict:
    item = dict(row)
    item["gain_id"] = str(item["gain_id"])
    item["lot_id"] = str(item["lot_id"])
    item["quantity_disposed"] = float(item["quantity_disposed"])
    item["cost_basis"] = float(item["cost_basis"])
    item["sale_price"] = float(item["sale_price"])
    item["realized_gain"] = float(item["realized_gain"])
    if item.get("acquisition_date"):
        item["acquisition_date"] = item["acquisition_date"].isoformat()
    if item.get("disposal_date"):
        item["disposal_date"] = item["disposal_date"].isoformat()
    return item


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Tax Lots API FastAPI application."""
    app = FastAPI(
        title="Tax Lots API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/tax-lots",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("tax-lots-api", check_deps))

    # --- Tax Lots ---

    @app.get("/lots/{symbol}", tags=["Tax Lots"])
    async def get_lots(symbol: str):
        """Get all tax lots for a symbol."""
        query = """
            SELECT lot_id, symbol, quantity, cost_basis, acquisition_date,
                   remaining_quantity, created_at
            FROM tax_lots
            WHERE symbol = $1 AND remaining_quantity > 0
            ORDER BY acquisition_date
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, symbol)

        if not rows:
            return not_found("Tax lots", symbol)

        items = [_serialize_lot(row) for row in rows]
        return collection_response(items, "tax_lot")

    @app.post("/lots", tags=["Tax Lots"], status_code=201)
    async def add_lot(body: AddLotRequest):
        """Record a new tax lot from an acquisition."""
        lot_id = str(uuid.uuid4())
        acq_date = body.acquisition_date or datetime.now(timezone.utc)

        query = """
            INSERT INTO tax_lots (lot_id, symbol, quantity, cost_basis,
                                  acquisition_date, remaining_quantity)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING lot_id, symbol, quantity, cost_basis, acquisition_date,
                      remaining_quantity, created_at
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                lot_id,
                body.symbol,
                body.quantity,
                body.cost_basis,
                acq_date,
                body.quantity,
            )

        return success_response(
            _serialize_lot(row),
            "tax_lot",
            resource_id=lot_id,
        )

    # --- Disposals ---

    @app.post("/dispose", tags=["Disposals"])
    async def dispose_lots(body: DisposalRequest):
        """Dispose of lots using the specified accounting method."""
        if body.method == AccountingMethod.SPECIFIC_ID and not body.lot_id:
            return validation_error("lot_id is required when using SPECIFIC_ID method")

        fetch_query = """
            SELECT lot_id, symbol, quantity, cost_basis, acquisition_date,
                   remaining_quantity
            FROM tax_lots
            WHERE symbol = $1 AND remaining_quantity > 0
            ORDER BY acquisition_date
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(fetch_query, body.symbol)

        lots = [dict(row) for row in rows]
        if not lots:
            return not_found("Tax lots", body.symbol)

        now = datetime.now(timezone.utc)
        try:
            if body.method == AccountingMethod.FIFO:
                gains, updates = dispose_fifo(lots, body.quantity, body.sale_price, now)
            elif body.method == AccountingMethod.LIFO:
                gains, updates = dispose_lifo(lots, body.quantity, body.sale_price, now)
            else:
                gains, updates = dispose_specific(
                    lots, body.lot_id, body.quantity, body.sale_price, now
                )
        except ValueError as e:
            return validation_error(str(e))

        # Persist updates and gains
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                for upd in updates:
                    await conn.execute(
                        "UPDATE tax_lots SET remaining_quantity = $1 WHERE lot_id = $2",
                        upd["remaining_quantity"],
                        upd["lot_id"],
                    )
                for g in gains:
                    await conn.execute(
                        """INSERT INTO realized_gains
                           (gain_id, lot_id, symbol, quantity_disposed, cost_basis,
                            sale_price, realized_gain, acquisition_date, disposal_date,
                            holding_period)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                        str(uuid.uuid4()),
                        g.lot_id,
                        g.symbol,
                        g.quantity_disposed,
                        g.cost_basis,
                        g.sale_price,
                        g.realized_gain,
                        g.acquisition_date,
                        g.disposal_date,
                        g.holding_period,
                    )

        result = [g.model_dump() for g in gains]
        for item in result:
            item["acquisition_date"] = item["acquisition_date"].isoformat()
            item["disposal_date"] = item["disposal_date"].isoformat()

        total_gain = sum(g.realized_gain for g in gains)
        return success_response(
            {"disposals": result, "total_realized_gain": round(total_gain, 8)},
            "disposal_result",
        )

    # --- Realized Gains ---

    @app.get("/gains", tags=["Gains"])
    async def get_gains(
        symbol: str = Query(None, description="Filter by symbol"),
        holding_period: str = Query(None, description="SHORT_TERM or LONG_TERM"),
    ):
        """Get realized gains/losses, optionally filtered."""
        conditions = []
        params = []
        idx = 1

        if symbol:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1
        if holding_period:
            conditions.append(f"holding_period = ${idx}")
            params.append(holding_period)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT gain_id, lot_id, symbol, quantity_disposed, cost_basis,
                   sale_price, realized_gain, acquisition_date, disposal_date,
                   holding_period
            FROM realized_gains
            {where}
            ORDER BY disposal_date DESC
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = [_serialize_gain(row) for row in rows]
        total_gain = sum(float(r["realized_gain"]) for r in items)

        return success_response(
            {
                "gains": items,
                "total_realized_gain": round(total_gain, 8),
                "count": len(items),
            },
            "realized_gains",
        )

    return app
