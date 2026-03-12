"""Data models for the volatility regime classifier."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class VolatilityRegime(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Annualized volatility thresholds (percentage)
REGIME_THRESHOLDS = {
    "low_upper": 15.0,
    "high_lower": 25.0,
}


class RegimeTransition(BaseModel):
    previous_regime: Optional[VolatilityRegime] = None
    current_regime: VolatilityRegime
    transitioned_at: str = Field(description="ISO 8601 timestamp of the transition")


class VolatilityMetrics(BaseModel):
    realized_vol_20d: Optional[float] = Field(
        None, description="20-day realized volatility (annualized %)"
    )
    realized_vol_60d: Optional[float] = Field(
        None, description="60-day realized volatility (annualized %)"
    )


class RegimeClassification(BaseModel):
    symbol: str
    regime: VolatilityRegime
    volatility: VolatilityMetrics
    recent_transitions: list[RegimeTransition] = Field(
        default_factory=list,
        description="Recent regime transitions, most recent first",
    )
