"""Data models for the Opportunity Scoring Engine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class OpportunityTier(str, Enum):
    """Tier classification for scored opportunities."""

    HOT = "HOT"
    GOOD = "GOOD"
    NEUTRAL = "NEUTRAL"
    LOW = "LOW"


class MarketRegime(str, Enum):
    """Market volatility regime."""

    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    EXTREME = "extreme"


class SignalDirection(str, Enum):
    """Trading signal direction."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OpportunityStatus(str, Enum):
    """Lifecycle status of an opportunity."""

    SCORED = "scored"
    SIGNALED = "signaled"
    ENTERED = "entered"
    CLOSED = "closed"
    EXPIRED = "expired"


@dataclass
class RegimeCaps:
    """Normalization caps adjusted by market regime."""

    max_return: float
    max_volatility: float


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how each factor contributed to the score."""

    confidence_value: float
    confidence_contribution: float

    expected_return_value: float
    expected_return_stddev: float
    risk_adjusted_return: float
    expected_return_contribution: float

    consensus_value: float
    consensus_contribution: float

    volatility_value: float
    volatility_percentile: float
    volatility_contribution: float

    freshness_value: int  # minutes_ago at scoring time
    freshness_contribution: float

    market_regime: str


@dataclass
class ContributingSignal:
    """A signal from one source contributing to an opportunity."""

    source: str  # e.g. "technical", "sentiment", "prediction_market"
    signal_id: str
    direction: str
    confidence: float
    strategy_name: Optional[str] = None
    expected_return: Optional[float] = None
    return_stddev: Optional[float] = None
    timestamp: Optional[datetime] = None


@dataclass
class ScoredOpportunity:
    """A scored and ranked trading opportunity."""

    opportunity_id: str
    symbol: str
    direction: str
    opportunity_score: float
    tier: str
    score_breakdown: ScoreBreakdown
    contributing_signals: list
    strategies_analyzed: int
    strategies_agreeing: int
    top_strategy: Optional[str]
    market_regime: str
    reasoning: str = ""
    status: str = OpportunityStatus.SCORED.value
    scored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    entered_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    outcome_return: Optional[float] = None

    @property
    def display_age_minutes(self) -> int:
        """Signal age for UI display only — does not affect cached score."""
        delta = datetime.now(timezone.utc) - self.scored_at
        return int(delta.total_seconds() / 60)

    @property
    def is_stale(self) -> bool:
        """Signal is stale if older than 60 minutes."""
        return self.display_age_minutes >= 60

    def to_dict(self) -> dict:
        """Serialize to dict for API responses.

        Field names follow the spec (opportunity_tier, opportunity_score_cached_at).
        """
        return {
            "opportunity_id": self.opportunity_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "opportunity_score": self.opportunity_score,
            "opportunity_tier": self.tier,
            "opportunity_score_cached_at": self.scored_at.isoformat(),
            "status": self.status,
            "market_regime": self.market_regime,
            "strategies_analyzed": self.strategies_analyzed,
            "strategies_agreeing": self.strategies_agreeing,
            "top_strategy": self.top_strategy,
            "reasoning": self.reasoning,
            "display_age_minutes": self.display_age_minutes,
            "is_stale": self.is_stale,
            "opportunity_factors": {
                "confidence": {
                    "value": self.score_breakdown.confidence_value,
                    "contribution": self.score_breakdown.confidence_contribution,
                },
                "expected_return": {
                    "value": self.score_breakdown.expected_return_value,
                    "stddev": self.score_breakdown.expected_return_stddev,
                    "risk_adjusted": self.score_breakdown.risk_adjusted_return,
                    "contribution": self.score_breakdown.expected_return_contribution,
                },
                "consensus": {
                    "value": self.score_breakdown.consensus_value,
                    "contribution": self.score_breakdown.consensus_contribution,
                },
                "volatility": {
                    "value": self.score_breakdown.volatility_value,
                    "percentile": self.score_breakdown.volatility_percentile,
                    "contribution": self.score_breakdown.volatility_contribution,
                },
                "freshness": {
                    "value": self.score_breakdown.freshness_value,
                    "contribution": self.score_breakdown.freshness_contribution,
                    "cached": True,
                },
                "market_regime": self.score_breakdown.market_regime,
            },
            "contributing_signals": [
                {
                    "source": s.source,
                    "signal_id": s.signal_id,
                    "direction": s.direction,
                    "confidence": s.confidence,
                    "strategy_name": s.strategy_name,
                }
                for s in self.contributing_signals
            ],
        }
