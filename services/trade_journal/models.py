"""Data models for trade journal entries."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class Outcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"
    OPEN = "OPEN"


@dataclass
class JournalEntry:
    """A single trade journal entry capturing full decision context."""

    trade_id: str
    strategy: str
    symbol: str
    side: Side
    entry_price: float
    entry_rationale: str
    signals_at_entry: dict[str, Any] = field(default_factory=dict)
    exit_price: Optional[float] = None
    exit_rationale: Optional[str] = None
    outcome: Outcome = Outcome.OPEN
    pnl: Optional[float] = None
    lessons: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "trade_id": self.trade_id,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": self.entry_price,
            "entry_rationale": self.entry_rationale,
            "signals_at_entry": self.signals_at_entry,
            "exit_price": self.exit_price,
            "exit_rationale": self.exit_rationale,
            "outcome": self.outcome.value,
            "pnl": self.pnl,
            "lessons": self.lessons,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            trade_id=data["trade_id"],
            strategy=data["strategy"],
            symbol=data["symbol"],
            side=Side(data["side"]),
            entry_price=float(data["entry_price"]),
            entry_rationale=data["entry_rationale"],
            signals_at_entry=data.get("signals_at_entry", {}),
            exit_price=float(data["exit_price"]) if data.get("exit_price") is not None else None,
            exit_rationale=data.get("exit_rationale"),
            outcome=Outcome(data.get("outcome", "OPEN")),
            pnl=float(data["pnl"]) if data.get("pnl") is not None else None,
            lessons=data.get("lessons"),
            tags=data.get("tags", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
        )
