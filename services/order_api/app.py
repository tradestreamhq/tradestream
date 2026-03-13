"""
Order Management REST API — RMM Level 2.

Provides endpoints for placing, listing, viewing, modifying,
and cancelling orders with full lifecycle management.

Order status lifecycle: PENDING -> OPEN -> PARTIAL_FILL -> FILLED / CANCELLED / EXPIRED
"""

import logging
from enum import Enum
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Enums ---


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


TERMINAL_STATUSES = {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED}
MODIFIABLE_STATUSES = {OrderStatus.PENDING, OrderStatus.OPEN}


# --- Request DTOs ---


class PlaceOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, description="Trading instrument symbol")
    side: OrderSide = Field(..., description="BUY or SELL")
    order_type: OrderType = Field(..., description="MARKET, LIMIT, or STOP")
    quantity: float = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(
        None, gt=0, description="Limit price (required for LIMIT orders)"
    )
    stop_price: Optional[float] = Field(
        None, gt=0, description="Stop price (required for STOP orders)"
    )


class ModifyOrderRequest(BaseModel):
    price: Optional[float] = Field(None, gt=0, description="New limit price")
    quantity: Optional[float] = Field(None, gt=0, description="New quantity")


# --- Helpers ---


def _serialize_order(row) -> dict:
    """Convert a database row to a serializable dict."""
    item = dict(row)
    for key in ("created_at", "updated_at"):
        if item.get(key):
            item[key] = item[key].isoformat()
    for key in ("quantity", "filled_quantity", "price", "stop_price", "avg_fill_price"):
        if item.get(key) is not None:
            item[key] = float(item[key])
    if item.get("id"):
        item["id"] = str(item["id"])
    return item


def _serialize_fill(row) -> dict:
    """Convert a fill row to a serializable dict."""
    item = dict(row)
    if item.get("filled_at"):
        item["filled_at"] = item["filled_at"].isoformat()
    for key in ("quantity", "price"):
        if item.get(key) is not None:
            item[key] = float(item[key])
    if item.get("id"):
        item["id"] = str(item["id"])
    if item.get("order_id"):
        item["order_id"] = str(item["order_id"])
    return item


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Order Management API FastAPI application."""
    app = FastAPI(
        title="Order Management API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/orders",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("order-api", check_deps))

    # --- Place Order ---

    @app.post("", tags=["Orders"], status_code=201)
    async def place_order(body: PlaceOrderRequest):
        """Place a new order."""
        if body.order_type == OrderType.LIMIT and body.price is None:
            return validation_error("price is required for LIMIT orders")
        if body.order_type == OrderType.STOP and body.stop_price is None:
            return validation_error("stop_price is required for STOP orders")

        query = """
            INSERT INTO orders (symbol, side, order_type, quantity, price, stop_price)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, symbol, side, order_type, quantity, price, stop_price,
                      filled_quantity, avg_fill_price, status, created_at, updated_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    body.symbol,
                    body.side.value,
                    body.order_type.value,
                    body.quantity,
                    body.price,
                    body.stop_price,
                )
        except Exception:
            logger.exception("Failed to place order")
            return server_error("Failed to place order")

        order = _serialize_order(row)
        return success_response(
            order, "order", resource_id=order["id"], status_code=201
        )

    # --- List Orders ---

    @app.get("", tags=["Orders"])
    async def list_orders(
        pagination: PaginationParams = Depends(),
        status: Optional[OrderStatus] = Query(None, description="Filter by status"),
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        side: Optional[OrderSide] = Query(None, description="Filter by side"),
        start_date: Optional[str] = Query(
            None, description="Filter from date (ISO format)"
        ),
        end_date: Optional[str] = Query(
            None, description="Filter to date (ISO format)"
        ),
    ):
        """List orders with optional filters."""
        conditions = []
        params = []
        idx = 1

        if status is not None:
            conditions.append(f"status = ${idx}")
            params.append(status.value)
            idx += 1
        if symbol is not None:
            conditions.append(f"symbol = ${idx}")
            params.append(symbol)
            idx += 1
        if side is not None:
            conditions.append(f"side = ${idx}")
            params.append(side.value)
            idx += 1
        if start_date is not None:
            conditions.append(f"created_at >= ${idx}::timestamptz")
            params.append(start_date)
            idx += 1
        if end_date is not None:
            conditions.append(f"created_at <= ${idx}::timestamptz")
            params.append(end_date)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_query = f"SELECT COUNT(*) FROM orders {where}"
        list_query = f"""
            SELECT id, symbol, side, order_type, quantity, price, stop_price,
                   filled_quantity, avg_fill_price, status, created_at, updated_at
            FROM orders {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([pagination.limit, pagination.offset])

        try:
            async with db_pool.acquire() as conn:
                total = await conn.fetchval(count_query, *params[:-2])
                rows = await conn.fetch(list_query, *params)
        except Exception:
            logger.exception("Failed to list orders")
            return server_error("Failed to list orders")

        items = [_serialize_order(row) for row in rows]
        return collection_response(
            items,
            "order",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # --- Get Order Detail ---

    @app.get("/{order_id}", tags=["Orders"])
    async def get_order(order_id: str):
        """Get order detail with fill history."""
        order_query = """
            SELECT id, symbol, side, order_type, quantity, price, stop_price,
                   filled_quantity, avg_fill_price, status, created_at, updated_at
            FROM orders WHERE id = $1::uuid
        """
        fills_query = """
            SELECT id, order_id, quantity, price, filled_at
            FROM order_fills WHERE order_id = $1::uuid
            ORDER BY filled_at ASC
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(order_query, order_id)
                if not row:
                    return not_found("Order", order_id)
                fills = await conn.fetch(fills_query, order_id)
        except Exception:
            logger.exception("Failed to get order %s", order_id)
            return server_error("Failed to retrieve order")

        order = _serialize_order(row)
        order["fills"] = [_serialize_fill(f) for f in fills]
        return success_response(order, "order", resource_id=order["id"])

    # --- Cancel Order ---

    @app.delete("/{order_id}", tags=["Orders"], status_code=200)
    async def cancel_order(order_id: str):
        """Cancel a pending or open order."""
        query = """
            UPDATE orders SET status = 'CANCELLED', updated_at = NOW()
            WHERE id = $1::uuid AND status IN ('PENDING', 'OPEN', 'PARTIAL_FILL')
            RETURNING id, symbol, side, order_type, quantity, price, stop_price,
                      filled_quantity, avg_fill_price, status, created_at, updated_at
        """
        try:
            async with db_pool.acquire() as conn:
                # Check if order exists first
                exists = await conn.fetchrow(
                    "SELECT id, status FROM orders WHERE id = $1::uuid", order_id
                )
                if not exists:
                    return not_found("Order", order_id)
                if exists["status"] in ("FILLED", "CANCELLED", "EXPIRED"):
                    return error_response(
                        "ORDER_NOT_CANCELLABLE",
                        f"Order is already {exists['status'].lower()}",
                        status_code=409,
                    )
                row = await conn.fetchrow(query, order_id)
        except Exception:
            logger.exception("Failed to cancel order %s", order_id)
            return server_error("Failed to cancel order")

        order = _serialize_order(row)
        return success_response(order, "order", resource_id=order["id"])

    # --- Modify Order ---

    @app.put("/{order_id}", tags=["Orders"])
    async def modify_order(order_id: str, body: ModifyOrderRequest):
        """Modify a pending or open order (price and/or quantity)."""
        if body.price is None and body.quantity is None:
            return validation_error(
                "At least one of price or quantity must be provided"
            )

        try:
            async with db_pool.acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT id, status, order_type FROM orders WHERE id = $1::uuid",
                    order_id,
                )
                if not existing:
                    return not_found("Order", order_id)
                if existing["status"] not in ("PENDING", "OPEN"):
                    return error_response(
                        "ORDER_NOT_MODIFIABLE",
                        f"Cannot modify order with status {existing['status'].lower()}",
                        status_code=409,
                    )

                set_clauses = ["updated_at = NOW()"]
                params = []
                idx = 1

                if body.price is not None:
                    set_clauses.append(f"price = ${idx}")
                    params.append(body.price)
                    idx += 1
                if body.quantity is not None:
                    set_clauses.append(f"quantity = ${idx}")
                    params.append(body.quantity)
                    idx += 1

                params.append(order_id)
                update_query = f"""
                    UPDATE orders SET {', '.join(set_clauses)}
                    WHERE id = ${idx}::uuid
                    RETURNING id, symbol, side, order_type, quantity, price, stop_price,
                              filled_quantity, avg_fill_price, status, created_at, updated_at
                """
                row = await conn.fetchrow(update_query, *params)
        except Exception:
            logger.exception("Failed to modify order %s", order_id)
            return server_error("Failed to modify order")

        order = _serialize_order(row)
        return success_response(order, "order", resource_id=order["id"])

    return app
