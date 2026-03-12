"""Data models for position reconciliation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class DiscrepancyType(str, Enum):
    """Types of position discrepancies."""

    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    MISSING_INTERNAL = "MISSING_INTERNAL"  # On exchange but not tracked internally
    PHANTOM_POSITION = "PHANTOM_POSITION"  # Tracked internally but not on exchange


@dataclass
class PositionSnapshot:
    """A point-in-time view of a position from a single source."""

    symbol: str
    quantity: float
    avg_entry_price: float


@dataclass
class Discrepancy:
    """A single reconciliation discrepancy."""

    symbol: str
    type: DiscrepancyType
    internal_quantity: Optional[float]
    exchange_quantity: Optional[float]
    difference: float
    auto_reconciled: bool = False

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "type": self.type.value,
            "internal_quantity": self.internal_quantity,
            "exchange_quantity": self.exchange_quantity,
            "difference": self.difference,
            "auto_reconciled": self.auto_reconciled,
        }


@dataclass
class ReconciliationReport:
    """Result of a reconciliation run."""

    run_id: str
    timestamp: str
    status: str  # "MATCHED", "DISCREPANCIES_FOUND", "ERROR"
    total_positions_checked: int
    discrepancies: List[Discrepancy] = field(default_factory=list)
    auto_reconciled_count: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "total_positions_checked": self.total_positions_checked,
            "discrepancies": [d.to_dict() for d in self.discrepancies],
            "auto_reconciled_count": self.auto_reconciled_count,
            "error": self.error,
        }
