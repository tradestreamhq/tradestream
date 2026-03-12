"""Circuit breaker data models for portfolio drawdown protection."""

import enum
import time
from dataclasses import dataclass, field
from typing import Optional


class BreakerLevel(str, enum.Enum):
    """Severity levels for circuit breaker thresholds."""

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    HALT = "HALT"
    EMERGENCY = "EMERGENCY"


@dataclass
class ThresholdConfig:
    """Configurable drawdown thresholds as decimal fractions (e.g. 0.05 = 5%)."""

    warning: float = 0.05
    halt: float = 0.10
    emergency: float = 0.20

    def __post_init__(self):
        if not (0 < self.warning < self.halt < self.emergency <= 1.0):
            raise ValueError(
                "Thresholds must satisfy: 0 < warning < halt < emergency <= 1.0"
            )


@dataclass
class BreakerEvent:
    """Recorded circuit breaker event."""

    level: BreakerLevel
    drawdown_pct: float
    peak_equity: float
    current_equity: float
    timestamp: float = field(default_factory=time.time)
    message: str = ""


@dataclass
class BreakerState:
    """Current state of the circuit breaker."""

    level: BreakerLevel = BreakerLevel.NORMAL
    drawdown_pct: float = 0.0
    peak_equity: float = 0.0
    current_equity: float = 0.0
    is_halted: bool = False
    halted_strategies: list = field(default_factory=list)
    last_triggered_at: Optional[float] = None
    reset_acknowledged: bool = True
    events: list = field(default_factory=list)
