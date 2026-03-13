"""Position manager domain models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class SizingMethod(str, Enum):
    FIXED_FRACTION = "FIXED_FRACTION"
    KELLY = "KELLY"


class RiskParams(BaseModel):
    """Risk parameters for position sizing."""

    capital: float = Field(..., gt=0, description="Total available capital")
    risk_pct: float = Field(
        0.02, gt=0, le=1.0, description="Fraction of capital to risk per trade"
    )
    max_position_pct: float = Field(
        0.1, gt=0, le=1.0, description="Max fraction of capital in a single position"
    )
    default_stop_loss_pct: float = Field(
        0.05, gt=0, le=1.0, description="Default stop-loss distance as fraction of entry"
    )


class PositionSizing(BaseModel):
    """Result of a position sizing calculation."""

    method: SizingMethod
    quantity: float = Field(..., ge=0)
    risk_amount: float = Field(..., ge=0)
    position_value: float = Field(..., ge=0)


class Position(BaseModel):
    """A tracked position."""

    id: Optional[str] = None
    strategy_id: Optional[str] = None
    symbol: str
    side: Side
    entry_price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: Optional[float] = None
    status: PositionStatus = PositionStatus.OPEN
    sizing_method: SizingMethod = SizingMethod.FIXED_FRACTION
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    close_reason: Optional[str] = None
    current_price: Optional[float] = None


class CloseRequest(BaseModel):
    """Request body for closing a position."""

    exit_price: float = Field(..., gt=0, description="Price at which to close")
    reason: Optional[str] = Field(None, description="Reason for closing")
