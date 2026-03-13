"""
Models for the Order Execution Simulator.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class SlippageModel(str, enum.Enum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    VOLATILITY = "VOLATILITY"


class SlippageConfig(BaseModel):
    model: SlippageModel = SlippageModel.PERCENTAGE
    value: float = Field(
        default=0.001, description="Slippage value (absolute for FIXED, fraction for PERCENTAGE/VOLATILITY)"
    )


class FeeSchedule(BaseModel):
    maker_fee: float = Field(default=0.001, ge=0, description="Maker fee as fraction")
    taker_fee: float = Field(default=0.002, ge=0, description="Taker fee as fraction")


class OrderFill(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    fill_price: float
    quantity: float
    fee: float
    fee_currency: str = "USD"
    slippage: float = 0.0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SimulatedOrder(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instrument: str
    order_type: OrderType
    side: OrderSide
    quantity: float = Field(gt=0)
    price: Optional[float] = Field(
        default=None, description="Limit/stop price (required for LIMIT, STOP_LOSS, TAKE_PROFIT)"
    )
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    total_fees: float = 0.0
    fills: List[OrderFill] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: Optional[str] = None


class OrderRequest(BaseModel):
    instrument: str = Field(..., description="Trading instrument symbol")
    order_type: OrderType
    side: OrderSide
    quantity: float = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(
        default=None, description="Limit/stop price"
    )
    expires_at: Optional[str] = Field(
        default=None, description="ISO 8601 expiration timestamp"
    )
