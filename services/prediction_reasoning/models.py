"""Data models for signal reasoning."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ContributingFactor:
    """A single indicator that contributed to a signal decision."""

    indicator_name: str
    value: float
    threshold: float
    condition: str  # crossed_above, crossed_below, exceeded, below
    weight: float  # 0.0-1.0
    description: str


@dataclass
class MarketContext:
    """Market context snapshot at signal generation time."""

    trend_direction: str  # bullish, bearish, neutral
    trend_strength: float  # 0.0-1.0
    volatility_percentile: float  # 0.0-1.0
    volume_ratio: float  # vs 20-day average
    market_regime: str  # trending, ranging, volatile
    sentiment: str  # bullish, bearish, neutral


@dataclass
class ConfidenceBreakdown:
    """Confidence breakdown by component."""

    indicator_agreement: float
    volume_confirmation: float
    trend_alignment: float
    volatility_context: float
    overall_confidence: float
    quality_grade: str


@dataclass
class HistoricalPattern:
    """Historical pattern match for context."""

    similar_signals_count: int
    win_rate: float
    avg_return: float
    lookback_days: int
    description: str


@dataclass
class RiskFactor:
    """Risk factor that may affect signal outcome."""

    category: str  # market, volatility, strategy, validation
    severity: str  # low, medium, high
    description: str
    impact_estimate: float  # e.g. -0.12 = -12%


@dataclass
class SignalReasoning:
    """Complete reasoning for a signal."""

    signal_id: str
    strategy_name: str
    symbol: str
    signal_type: str  # BUY, SELL
    contributing_factors: List[ContributingFactor]
    indicator_values: Dict[str, float]
    market_context: MarketContext
    confidence_breakdown: ConfidenceBreakdown
    explanation_text: str
    historical_pattern: Optional[HistoricalPattern] = None
    risk_factors: List[RiskFactor] = field(default_factory=list)
    validation_level: str = "candidate"
    expected_return: Optional[float] = None
    expected_return_ci_lower: Optional[float] = None
    expected_return_ci_upper: Optional[float] = None
    predicted_timeframe_hours: Optional[int] = None
    id: Optional[str] = None
