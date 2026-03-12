"""Tax lot data models."""

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AccountingMethod(str, enum.Enum):
    FIFO = "FIFO"
    LIFO = "LIFO"
    SPECIFIC_ID = "SPECIFIC_ID"


class TaxLot(BaseModel):
    lot_id: str = Field(..., description="Unique identifier for the tax lot")
    symbol: str = Field(..., description="Trading instrument symbol")
    quantity: float = Field(..., gt=0, description="Number of units in the lot")
    cost_basis: float = Field(..., gt=0, description="Per-unit cost basis")
    acquisition_date: datetime = Field(..., description="Date the lot was acquired")
    remaining_quantity: float = Field(
        ..., ge=0, description="Units remaining in the lot"
    )


class DisposalRequest(BaseModel):
    symbol: str = Field(..., description="Trading instrument symbol")
    quantity: float = Field(..., gt=0, description="Number of units to dispose")
    sale_price: float = Field(..., gt=0, description="Per-unit sale price")
    method: AccountingMethod = Field(
        AccountingMethod.FIFO, description="Accounting method for lot selection"
    )
    lot_id: Optional[str] = Field(
        None, description="Specific lot ID (required for SPECIFIC_ID method)"
    )


class RealizedGain(BaseModel):
    lot_id: str
    symbol: str
    quantity_disposed: float
    cost_basis: float
    sale_price: float
    realized_gain: float
    acquisition_date: datetime
    disposal_date: datetime
    holding_period: str = Field(..., description="SHORT_TERM or LONG_TERM (>1 year)")


class AddLotRequest(BaseModel):
    symbol: str = Field(..., description="Trading instrument symbol")
    quantity: float = Field(..., gt=0, description="Number of units")
    cost_basis: float = Field(..., gt=0, description="Per-unit cost basis")
    acquisition_date: Optional[datetime] = Field(
        None, description="Acquisition date (defaults to now)"
    )
