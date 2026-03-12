"""Data models for portfolio snapshots."""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class SnapshotPosition:
    """A single position captured in a portfolio snapshot."""

    symbol: str
    quantity: float
    market_value: float


@dataclass
class PortfolioSnapshot:
    """A point-in-time capture of portfolio state."""

    snapshot_date: date
    total_equity: float
    cash_balance: float
    margin_used: float
    positions: List[SnapshotPosition] = field(default_factory=list)
    daily_change: Optional[float] = None
    daily_change_pct: Optional[float] = None
    id: Optional[str] = None
