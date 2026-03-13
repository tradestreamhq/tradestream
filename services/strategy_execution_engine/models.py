"""Models for the Strategy Execution Engine."""

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SignalDirection(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


class StrategyStatus(enum.Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class PositionState(enum.Enum):
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class Signal:
    """A trading signal emitted by the execution engine."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    symbol: str = ""
    direction: SignalDirection = SignalDirection.NONE
    confidence: float = 0.0
    entry_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class StrategyState:
    """Tracks the current state of a running strategy."""

    strategy_id: str = ""
    status: StrategyStatus = StrategyStatus.IDLE
    position: PositionState = PositionState.FLAT
    entry_time: Optional[float] = None
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    last_signal_time: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "status": self.status.value,
            "position": self.position.value,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": (
                self.winning_trades / self.total_trades
                if self.total_trades > 0
                else 0.0
            ),
            "last_signal_time": self.last_signal_time,
            "error_message": self.error_message,
        }


@dataclass
class Candle:
    """A single OHLCV candle."""

    timestamp: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    symbol: str = ""


@dataclass
class IndicatorConfig:
    """Configuration for a single indicator."""

    id: str = ""
    type: str = ""
    input: str = "close"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConditionConfig:
    """Configuration for an entry or exit condition."""

    type: str = ""
    indicator: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParameterDef:
    """Definition of a strategy parameter."""

    name: str = ""
    type: str = "INTEGER"
    min: float = 0.0
    max: float = 100.0
    default_value: float = 0.0


@dataclass
class StrategyConfig:
    """Parsed strategy configuration from YAML or database."""

    name: str = ""
    description: str = ""
    complexity: str = "SIMPLE"
    indicators: List[IndicatorConfig] = field(default_factory=list)
    entry_conditions: List[ConditionConfig] = field(default_factory=list)
    exit_conditions: List[ConditionConfig] = field(default_factory=list)
    parameters: List[ParameterDef] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyConfig":
        """Parse a strategy config from a YAML-loaded dict."""
        indicators = [
            IndicatorConfig(
                id=ind.get("id", ""),
                type=ind.get("type", ""),
                input=ind.get("input", "close"),
                params=ind.get("params", {}),
            )
            for ind in data.get("indicators", [])
        ]
        entry_conditions = [
            ConditionConfig(
                type=cond.get("type", ""),
                indicator=cond.get("indicator", ""),
                params=cond.get("params", {}),
            )
            for cond in data.get("entryConditions", [])
        ]
        exit_conditions = [
            ConditionConfig(
                type=cond.get("type", ""),
                indicator=cond.get("indicator", ""),
                params=cond.get("params", {}),
            )
            for cond in data.get("exitConditions", [])
        ]
        parameters = [
            ParameterDef(
                name=p.get("name", ""),
                type=p.get("type", "INTEGER"),
                min=float(p.get("min", 0)),
                max=float(p.get("max", 100)),
                default_value=float(p.get("defaultValue", 0)),
            )
            for p in data.get("parameters", [])
        ]
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            complexity=data.get("complexity", "SIMPLE"),
            indicators=indicators,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            parameters=parameters,
        )


@dataclass
class ExecutionContext:
    """Context for a strategy execution session."""

    strategy_id: str = ""
    config: Optional[StrategyConfig] = None
    symbol: str = ""
    timeframe: str = "1m"
    parameter_values: Dict[str, float] = field(default_factory=dict)
    state: StrategyState = field(default_factory=StrategyState)
    signals: List[Signal] = field(default_factory=list)
    max_signals: int = 1000

    def add_signal(self, signal: Signal) -> None:
        self.signals.append(signal)
        if len(self.signals) > self.max_signals:
            self.signals = self.signals[-self.max_signals:]
        self.state.last_signal_time = signal.timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "parameter_values": self.parameter_values,
            "state": self.state.to_dict(),
            "recent_signals_count": len(self.signals),
        }
