"""Data models for drawdown tracking and recovery estimation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class DrawdownState(str, Enum):
    IN_DRAWDOWN = "IN_DRAWDOWN"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"
    AT_PEAK = "AT_PEAK"


@dataclass
class DrawdownEvent:
    """A historical drawdown episode from peak to recovery."""

    start_date: datetime
    trough_date: datetime
    recovery_date: Optional[datetime]
    peak_equity: float
    trough_equity: float
    depth_pct: float
    duration_days: int
    recovery_days: Optional[int]
    state: DrawdownState

    def to_dict(self) -> dict:
        return {
            "start_date": self.start_date.isoformat(),
            "trough_date": self.trough_date.isoformat(),
            "recovery_date": self.recovery_date.isoformat() if self.recovery_date else None,
            "peak_equity": self.peak_equity,
            "trough_equity": self.trough_equity,
            "depth_pct": round(self.depth_pct, 4),
            "duration_days": self.duration_days,
            "recovery_days": self.recovery_days,
            "state": self.state.value,
        }


@dataclass
class CurrentDrawdown:
    """Snapshot of a strategy's current drawdown status."""

    state: DrawdownState
    peak_equity: float
    current_equity: float
    trough_equity: float
    drawdown_pct: float
    recovery_pct: float
    drawdown_start: Optional[datetime]
    estimated_recovery_days: Optional[int]

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "peak_equity": self.peak_equity,
            "current_equity": self.current_equity,
            "trough_equity": self.trough_equity,
            "drawdown_pct": round(self.drawdown_pct, 4),
            "recovery_pct": round(self.recovery_pct, 4),
            "drawdown_start": self.drawdown_start.isoformat() if self.drawdown_start else None,
            "estimated_recovery_days": self.estimated_recovery_days,
        }


@dataclass
class DrawdownSummary:
    """Aggregate drawdown statistics for a strategy."""

    strategy_id: str
    current: CurrentDrawdown
    historical_events: List[DrawdownEvent] = field(default_factory=list)
    max_drawdown_pct: float = 0.0
    avg_drawdown_pct: float = 0.0
    avg_recovery_days: Optional[float] = None
    total_drawdown_events: int = 0

    def to_dict(self) -> dict:
        completed = [e for e in self.historical_events if e.recovery_days is not None]
        avg_recovery = (
            round(sum(e.recovery_days for e in completed) / len(completed), 1)
            if completed
            else None
        )
        return {
            "strategy_id": self.strategy_id,
            "current": self.current.to_dict(),
            "historical_events": [e.to_dict() for e in self.historical_events],
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "avg_drawdown_pct": round(self.avg_drawdown_pct, 4),
            "avg_recovery_days": avg_recovery,
            "total_drawdown_events": self.total_drawdown_events,
        }
