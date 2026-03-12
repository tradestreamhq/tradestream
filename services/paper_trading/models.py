"""Data models for the paper trading order execution simulator."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Order(BaseModel):
    """An order submitted to the simulator."""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float = Field(gt=0)
    limit_price: Optional[float] = Field(default=None, gt=0)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    status: OrderStatus = OrderStatus.PENDING


class Fill(BaseModel):
    """A completed fill for an order."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    filled_at: datetime = Field(default_factory=datetime.utcnow)
    commission: float = 0.0


class Position(BaseModel):
    """A virtual position in a single instrument."""

    symbol: str
    quantity: float = 0.0
    avg_cost_basis: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        """Compute market value given current price (requires external price)."""
        return 0.0  # Computed externally via virtual_portfolio

    def is_flat(self) -> bool:
        return abs(self.quantity) < 1e-12


class TradeRecord(BaseModel):
    """A record of a completed trade for the trade log."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    realized_pnl: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PerformanceSnapshot(BaseModel):
    """A daily performance snapshot."""

    date: str
    starting_equity: float
    ending_equity: float
    daily_pnl: float
    cumulative_return: float
    open_positions: int
    total_trades: int
