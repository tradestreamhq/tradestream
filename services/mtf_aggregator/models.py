"""
Data models for the Multi-Timeframe Signal Aggregator.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SignalDirection(str, Enum):
    """Direction of a trade signal."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Timeframe(str, Enum):
    """Supported trading timeframes, ordered from shortest to longest."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


# Default weights: higher timeframes carry more weight.
DEFAULT_TIMEFRAME_WEIGHTS: Dict[Timeframe, float] = {
    Timeframe.M1: 0.05,
    Timeframe.M5: 0.08,
    Timeframe.M15: 0.10,
    Timeframe.H1: 0.17,
    Timeframe.H4: 0.20,
    Timeframe.D1: 0.25,
    Timeframe.W1: 0.15,
}


@dataclass
class TimeframeSignal:
    """A signal tagged with its originating timeframe."""

    symbol: str
    timeframe: Timeframe
    direction: SignalDirection
    confidence: float  # 0.0 to 1.0
    strategy_type: Optional[str] = None
    signal_id: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class AggregationResult:
    """Result of aggregating signals across multiple timeframes."""

    symbol: str
    conviction_score: float  # -1.0 (strong sell) to +1.0 (strong buy)
    alignment_score: float  # 0.0 (full disagreement) to 1.0 (full agreement)
    direction: SignalDirection
    timeframe_count: int
    timeframe_details: Dict[str, Dict] = field(default_factory=dict)
    contributing_signals: List[TimeframeSignal] = field(default_factory=list)

    @property
    def conviction_tier(self) -> str:
        """Map conviction score to a human-readable tier."""
        abs_score = abs(self.conviction_score)
        if abs_score >= 0.75:
            return "STRONG"
        elif abs_score >= 0.50:
            return "MODERATE"
        elif abs_score >= 0.25:
            return "WEAK"
        return "NEUTRAL"
