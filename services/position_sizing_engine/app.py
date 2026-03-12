"""
Position Sizing Engine — REST API.

Provides endpoints for computing position sizes using various methods
and listing available sizing methods.
"""

import logging
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from services.position_sizing_engine.engine import (
    SIZING_METHOD_DESCRIPTIONS,
    PortfolioConstraints,
    SizingMethod,
    SizingRequest,
    calculate_position_size,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    success_response,
    validation_error,
)

logger = logging.getLogger(__name__)


class SizingRequestBody(BaseModel):
    """Request body for position size calculation."""

    strategy_id: str = Field(..., description="Strategy identifier")
    signal_strength: float = Field(
        ..., ge=0.0, le=1.0, description="Signal strength (0.0 to 1.0)"
    )
    entry_price: float = Field(..., gt=0, description="Planned entry price")
    stop_loss_price: Optional[float] = Field(
        None, description="Stop loss price (required for fixed_fractional)"
    )
    current_equity: float = Field(..., gt=0, description="Current account equity")
    max_position_pct: float = Field(
        0.20,
        gt=0.0,
        le=1.0,
        description="Max position size as fraction of equity",
    )
    method: SizingMethod = Field(
        SizingMethod.FIXED_FRACTIONAL, description="Sizing method to use"
    )
    risk_pct: float = Field(0.02, gt=0.0, le=1.0, description="Risk % of equity")
    win_rate: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Win rate for Kelly"
    )
    payoff_ratio: Optional[float] = Field(
        None, gt=0.0, description="Avg win / avg loss for Kelly"
    )
    atr: Optional[float] = Field(None, gt=0.0, description="ATR value")
    atr_multiplier: float = Field(2.0, gt=0.0, description="ATR multiplier")
    num_positions: int = Field(10, gt=0, description="Target positions for equal weight")
    kelly_fraction: float = Field(
        0.5, gt=0.0, le=1.0, description="Fraction of full Kelly"
    )
    # Portfolio constraints
    max_total_exposure_pct: float = Field(
        1.0, gt=0.0, le=5.0, description="Max total portfolio exposure"
    )
    max_single_position_pct: float = Field(
        0.20, gt=0.0, le=1.0, description="Max single position % of equity"
    )
    max_correlated_exposure_pct: float = Field(
        0.40, gt=0.0, le=1.0, description="Max correlated exposure"
    )
    current_exposure: float = Field(
        0.0, ge=0.0, description="Current total exposure in dollars"
    )
    current_correlated_exposure: float = Field(
        0.0, ge=0.0, description="Current correlated exposure in dollars"
    )


def create_app() -> FastAPI:
    """Create the Position Sizing Engine FastAPI application."""
    app = FastAPI(
        title="Position Sizing Engine",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/sizing",
    )

    async def check_deps():
        return {"status": "ok"}

    app.include_router(create_health_router("position-sizing-engine", check_deps))

    @app.get("/methods", tags=["Sizing"])
    async def list_methods():
        """List available sizing methods with descriptions."""
        items = []
        for method_key, info in SIZING_METHOD_DESCRIPTIONS.items():
            items.append(
                {
                    "id": method_key,
                    "name": info["name"],
                    "description": info["description"],
                }
            )
        return collection_response(items, "sizing_method")

    @app.post("/calculate", tags=["Sizing"])
    async def calculate(body: SizingRequestBody):
        """Compute position size for a trade setup."""
        # Validate method-specific requirements
        if (
            body.method == SizingMethod.FIXED_FRACTIONAL
            and body.stop_loss_price is None
        ):
            return validation_error(
                "stop_loss_price is required for fixed_fractional method"
            )

        if body.method == SizingMethod.VOLATILITY_ADJUSTED and body.atr is None:
            return validation_error("atr is required for volatility_adjusted method")

        req = SizingRequest(
            strategy_id=body.strategy_id,
            signal_strength=body.signal_strength,
            entry_price=body.entry_price,
            stop_loss_price=body.stop_loss_price,
            current_equity=body.current_equity,
            max_position_pct=body.max_position_pct,
            method=body.method,
            risk_pct=body.risk_pct,
            win_rate=body.win_rate,
            payoff_ratio=body.payoff_ratio,
            atr=body.atr,
            atr_multiplier=body.atr_multiplier,
            num_positions=body.num_positions,
            kelly_fraction=body.kelly_fraction,
        )

        constraints = PortfolioConstraints(
            max_total_exposure_pct=body.max_total_exposure_pct,
            max_single_position_pct=body.max_single_position_pct,
            max_correlated_exposure_pct=body.max_correlated_exposure_pct,
            current_exposure=body.current_exposure,
            current_correlated_exposure=body.current_correlated_exposure,
        )

        result = calculate_position_size(req, constraints)

        return success_response(
            {
                "strategy_id": result.strategy_id,
                "method": result.method,
                "signal_strength": result.signal_strength,
                "shares": round(result.shares, 8),
                "dollar_amount": round(result.dollar_amount, 2),
                "risk_amount": round(result.risk_amount, 2),
                "risk_pct": round(result.risk_pct, 6),
                "constrained": result.constrained,
            },
            "position_size",
            resource_id=result.strategy_id,
        )

    return app
