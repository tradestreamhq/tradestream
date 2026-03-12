"""Models for the signal replay service."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalAction(Enum):
    """Action type from a trade signal."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STOP_LOSS = "STOP_LOSS"
    NONE = "NONE"


@dataclass
class HistoricalSignal:
    """A historical trade signal to be replayed."""

    timestamp_ms: int
    symbol: str
    strategy_name: str
    action: SignalAction
    price: float
    confidence: float = 0.0
    reason: str = ""
    stop_loss: float = 0.0
    take_profit: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyState:
    """Snapshot of strategy state at a point in time."""

    position: str  # "LONG", "SHORT", "FLAT"
    entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    trade_count: int = 0
    current_size: float = 0.0


class ReplayDecision(Enum):
    """Decision made by the strategy in response to a signal."""

    ENTER_LONG = "ENTER_LONG"
    EXIT_LONG = "EXIT_LONG"
    HOLD = "HOLD"
    SKIP = "SKIP"
    STOP_OUT = "STOP_OUT"


@dataclass
class DecisionLogEntry:
    """A single entry in the replay decision log."""

    step: int
    signal: HistoricalSignal
    state_before: StrategyState
    decision: ReplayDecision
    state_after: StrategyState
    pnl_delta: float = 0.0
    notes: str = ""


@dataclass
class ReplayResult:
    """Complete result of a signal replay session."""

    strategy_name: str
    symbol: str
    total_signals: int
    decision_log: list[DecisionLogEntry] = field(default_factory=list)
    total_pnl: float = 0.0
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.win_count / self.total_trades


@dataclass
class ReplayConfig:
    """Configuration for a replay session."""

    strategy_name: str
    symbol: str
    start_timestamp_ms: int = 0
    end_timestamp_ms: int = 0
    initial_capital: float = 10000.0
    position_size: float = 1.0
