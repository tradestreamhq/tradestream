"""
Margin calculator data models.

Defines margin types, exchange margin rates, and request/response DTOs
for margin requirement calculations.
"""

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class MarginType(str, Enum):
    INITIAL = "initial"
    MAINTENANCE = "maintenance"
    PORTFOLIO = "portfolio"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExchangeMarginRates(BaseModel):
    """Configurable margin rates for an exchange."""

    exchange: str = Field(..., description="Exchange identifier")
    initial_rate: float = Field(
        ..., gt=0, le=1, description="Initial margin rate (e.g. 0.5 = 50%)"
    )
    maintenance_rate: float = Field(
        ..., gt=0, le=1, description="Maintenance margin rate (e.g. 0.25 = 25%)"
    )
    portfolio_rate: float = Field(
        ..., gt=0, le=1, description="Portfolio margin rate (e.g. 0.15 = 15%)"
    )


# Default margin rates per exchange
DEFAULT_EXCHANGE_RATES: Dict[str, ExchangeMarginRates] = {
    "coinbase": ExchangeMarginRates(
        exchange="coinbase",
        initial_rate=0.50,
        maintenance_rate=0.25,
        portfolio_rate=0.15,
    ),
    "binance": ExchangeMarginRates(
        exchange="binance",
        initial_rate=0.50,
        maintenance_rate=0.25,
        portfolio_rate=0.10,
    ),
    "kraken": ExchangeMarginRates(
        exchange="kraken",
        initial_rate=0.50,
        maintenance_rate=0.30,
        portfolio_rate=0.20,
    ),
    "default": ExchangeMarginRates(
        exchange="default",
        initial_rate=0.50,
        maintenance_rate=0.25,
        portfolio_rate=0.15,
    ),
}


class MarginRequirementRequest(BaseModel):
    symbol: str = Field(..., description="Trading instrument symbol")
    quantity: float = Field(..., gt=0, description="Order quantity")
    side: OrderSide = Field(..., description="Order side: BUY or SELL")
    price: float = Field(..., gt=0, description="Current or limit price")
    exchange: str = Field("default", description="Exchange identifier")
    account_equity: float = Field(..., gt=0, description="Total account equity")
    existing_margin_used: float = Field(
        0.0, ge=0, description="Margin already in use"
    )


class MarginRequirementResult(BaseModel):
    symbol: str
    side: str
    quantity: float
    price: float
    notional_value: float
    exchange: str
    initial_margin: float
    maintenance_margin: float
    portfolio_margin: float
    buying_power: float
    margin_available: float
    margin_utilization_pct: float
    can_execute: bool
    reason: Optional[str] = None
