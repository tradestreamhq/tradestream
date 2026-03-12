"""Health check models for strategy performance monitoring."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADING = "degrading"
    CRITICAL = "critical"
    DISABLED = "disabled"


class MetricSnapshot(BaseModel):
    rolling_sharpe: Optional[float] = Field(
        None, description="Rolling Sharpe ratio over recent window"
    )
    sharpe_90d_avg: Optional[float] = Field(
        None, description="90-day average Sharpe ratio"
    )
    win_rate: Optional[float] = Field(
        None, description="Current win rate (0-1)"
    )
    win_rate_trend: Optional[float] = Field(
        None, description="Win rate change over trailing period"
    )
    avg_trade_duration_seconds: Optional[float] = Field(
        None, description="Average trade duration in seconds"
    )
    drawdown_depth: Optional[float] = Field(
        None, description="Current drawdown depth as a fraction (0-1)"
    )
    historical_max_drawdown: Optional[float] = Field(
        None, description="Historical maximum drawdown"
    )


class HealthTransition(BaseModel):
    from_state: HealthState
    to_state: HealthState
    reason: str
    timestamp: str


class StrategyHealthReport(BaseModel):
    strategy_id: str
    state: HealthState
    metrics: MetricSnapshot
    reasons: List[str] = Field(
        default_factory=list, description="Reasons for current state"
    )
    last_transition: Optional[HealthTransition] = None
    checked_at: str
