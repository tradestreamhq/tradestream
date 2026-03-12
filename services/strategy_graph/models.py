"""
Data models for the strategy dependency graph.

Defines strategy nodes, edges (relationships), signals, and conflict results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RelationshipType(str, Enum):
    """Types of relationships between strategies."""

    SAME_SYMBOL = "SAME_SYMBOL"
    CORRELATED = "CORRELATED"
    HEDGING = "HEDGING"


@dataclass
class StrategyNode:
    """A strategy in the dependency graph."""

    strategy_id: str
    name: str
    symbols: List[str]
    sharpe_ratio: float = 0.0

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "symbols": self.symbols,
            "sharpe_ratio": self.sharpe_ratio,
        }


@dataclass
class StrategyEdge:
    """A relationship between two strategies."""

    source_id: str
    target_id: str
    relationship: RelationshipType
    shared_symbols: List[str] = field(default_factory=list)
    correlation: float = 0.0

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship.value,
            "shared_symbols": self.shared_symbols,
            "correlation": self.correlation,
        }


@dataclass
class Signal:
    """A trading signal from a strategy."""

    strategy_id: str
    symbol: str
    direction: SignalDirection
    timestamp: datetime
    strength: float = 1.0

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "timestamp": self.timestamp.isoformat(),
            "strength": self.strength,
        }


@dataclass
class Conflict:
    """A detected conflict between signals."""

    symbol: str
    signals: List[Signal]
    winner_strategy_id: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "signals": [s.to_dict() for s in self.signals],
            "winner_strategy_id": self.winner_strategy_id,
            "reason": self.reason,
        }
