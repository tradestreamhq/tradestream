"""
Order Execution Simulator REST API — RMM Level 2.

Provides endpoints for placing, listing, and cancelling simulated orders,
as well as querying simulated account balance and positions.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from services.order_simulator.models import (
    FeeSchedule,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    SlippageConfig,
    SlippageModel,
)
from services.order_simulator.simulator import OrderSimulator
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)

logger = logging.getLogger(__name__)


class TickRequest(BaseModel):
    instrument: str
    bid: float = Field(..., gt=0)
    ask: float = Field(..., gt=0)
    volume: float = Field(default=1_000_000.0, gt=0)
    volatility: float = Field(default=0.02, ge=0)


def create_app(
    initial_balance: float = 100_000.0,
    slippage_config: Optional[SlippageConfig] = None,
    fee_schedule: Optional[FeeSchedule] = None,
) -> FastAPI:
    """Create the Order Simulator FastAPI application."""
    app = FastAPI(
        title="Order Execution Simulator",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/simulator",
    )

    simulator = OrderSimulator(
        initial_balance=initial_balance,
        slippage_config=slippage_config,
        fee_schedule=fee_schedule,
    )

    app.include_router(create_health_router("order-simulator"))

    @app.post("/orders", tags=["Orders"], status_code=201)
    async def place_order(body: OrderRequest):
        """Place a simulated order."""
        if body.order_type != OrderType.MARKET and body.price is None:
            return validation_error(
                f"{body.order_type.value} orders require a price"
            )

        order = SimulatedOrder(
            instrument=body.instrument,
            order_type=body.order_type,
            side=body.side,
            quantity=body.quantity,
            price=body.price,
            expires_at=body.expires_at,
        )

        try:
            placed = simulator.place_order(order)
        except ValueError as exc:
            return validation_error(str(exc))

        return success_response(
            placed.model_dump(),
            "simulated_order",
            resource_id=placed.id,
            status_code=201,
        )

    @app.get("/orders", tags=["Orders"])
    async def list_orders(
        instrument: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
    ):
        """List orders, optionally filtered by instrument or status."""
        if status and status.upper() in ("OPEN", "PARTIALLY_FILLED"):
            orders = simulator.get_open_orders(instrument=instrument)
        else:
            orders = simulator.get_all_orders(instrument=instrument)

        if status and status.upper() not in ("OPEN", "PARTIALLY_FILLED"):
            try:
                filter_status = OrderStatus(status.upper())
                orders = [o for o in orders if o.status == filter_status]
            except ValueError:
                return validation_error(f"Invalid status: {status}")

        items = [o.model_dump() for o in orders]
        return collection_response(items, "simulated_order")

    @app.get("/orders/{order_id}", tags=["Orders"])
    async def get_order(order_id: str):
        """Get a specific order by ID."""
        order = simulator.orders.get(order_id)
        if not order:
            return not_found("Order", order_id)
        return success_response(
            order.model_dump(),
            "simulated_order",
            resource_id=order.id,
        )

    @app.delete("/orders/{order_id}", tags=["Orders"])
    async def cancel_order(order_id: str):
        """Cancel an open order."""
        order = simulator.orders.get(order_id)
        if not order:
            return not_found("Order", order_id)

        cancelled = simulator.cancel_order(order_id)
        if cancelled is None:
            return validation_error(
                f"Order {order_id} cannot be cancelled (status: {order.status.value})"
            )

        return success_response(
            cancelled.model_dump(),
            "simulated_order",
            resource_id=cancelled.id,
        )

    @app.get("/balance", tags=["Account"])
    async def get_balance():
        """Get simulated account balance and positions."""
        summary = simulator.get_balance_summary()
        return success_response(summary, "balance")

    @app.post("/tick", tags=["Simulation"])
    async def process_tick(body: TickRequest):
        """Process a market tick to trigger order fills."""
        fills = simulator.process_market_tick(
            instrument=body.instrument,
            bid=body.bid,
            ask=body.ask,
            volume=body.volume,
            volatility=body.volatility,
        )
        items = [f.model_dump() for f in fills]
        return collection_response(items, "order_fill")

    return app
