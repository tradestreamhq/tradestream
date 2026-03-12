"""Fee tracking data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FeeType(str, Enum):
    COMMISSION = "commission"
    EXCHANGE = "exchange"
    FUNDING = "funding"
    SPREAD = "spread"


class FeeRecord(BaseModel):
    """A single fee event associated with a trade and strategy."""

    id: Optional[int] = None
    trade_id: str = Field(..., description="Identifier of the originating trade")
    strategy_id: str = Field(..., description="Strategy that triggered the trade")
    fee_type: FeeType = Field(..., description="Category of fee")
    amount: float = Field(..., description="Fee amount (positive = cost)")
    currency: str = Field("USD", description="Fee currency")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When the fee was incurred",
    )


class FeeRecordCreate(BaseModel):
    """Request body for recording a fee."""

    trade_id: str
    strategy_id: str
    fee_type: FeeType
    amount: float
    currency: str = "USD"
