"""
Margin Calculator REST API — RMM Level 2.

Provides endpoints for computing margin requirements, buying power,
and margin utilization for trading orders.
"""

import logging

from fastapi import APIRouter, FastAPI, Query

from services.margin_calculator.calculator import MarginCalculator
from services.margin_calculator.models import (
    MarginRequirementRequest,
    OrderSide,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(calculator: MarginCalculator | None = None) -> FastAPI:
    """Create the Margin Calculator API FastAPI application."""
    calc = calculator or MarginCalculator()

    app = FastAPI(
        title="Margin Calculator API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/margin",
    )
    fastapi_auth_middleware(app)
    app.include_router(create_health_router("margin-calculator"))

    @app.get("/requirements", tags=["Margin"])
    async def get_margin_requirements(
        symbol: str = Query(..., description="Trading instrument symbol"),
        qty: float = Query(..., gt=0, description="Order quantity"),
        side: str = Query(..., description="Order side: BUY or SELL"),
        price: float = Query(..., gt=0, description="Current or limit price"),
        exchange: str = Query("default", description="Exchange identifier"),
        account_equity: float = Query(..., gt=0, description="Total account equity"),
        existing_margin_used: float = Query(0.0, ge=0, description="Margin already in use"),
    ):
        """Compute margin requirements for a proposed order."""
        side_upper = side.upper()
        if side_upper not in ("BUY", "SELL"):
            return validation_error(
                "Invalid side", [{"field": "side", "message": "Must be BUY or SELL"}]
            )

        req = MarginRequirementRequest(
            symbol=symbol,
            quantity=qty,
            side=OrderSide(side_upper),
            price=price,
            exchange=exchange,
            account_equity=account_equity,
            existing_margin_used=existing_margin_used,
        )
        result = calc.calculate(req)
        return success_response(result.model_dump(), "margin_requirement")

    @app.post("/requirements", tags=["Margin"])
    async def post_margin_requirements(body: MarginRequirementRequest):
        """Compute margin requirements from a JSON request body."""
        result = calc.calculate(body)
        return success_response(result.model_dump(), "margin_requirement")

    @app.get("/exchanges", tags=["Margin"])
    async def list_exchanges():
        """List supported exchanges and their margin rates."""
        exchanges = {}
        for name, rates in calc._rates.items():
            exchanges[name] = {
                "initial_rate": rates.initial_rate,
                "maintenance_rate": rates.maintenance_rate,
                "portfolio_rate": rates.portfolio_rate,
            }
        return success_response(exchanges, "exchange_rates")

    return app
