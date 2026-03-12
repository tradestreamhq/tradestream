"""
PnL Attribution data models.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Period(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class StrategyAttribution(BaseModel):
    strategy_type: str
    total_pnl: float
    trade_count: int
    winning_trades: int
    losing_trades: int
    hit_rate: float
    avg_win: float
    avg_loss: float
    contribution_pct: float = Field(
        description="Percentage contribution to total portfolio return"
    )


class AssetAttribution(BaseModel):
    symbol: str
    total_pnl: float
    trade_count: int
    contribution_pct: float


class DirectionAttribution(BaseModel):
    side: str
    total_pnl: float
    trade_count: int
    contribution_pct: float


class RealizationAttribution(BaseModel):
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float


class TimeBucket(BaseModel):
    period: str
    total_pnl: float
    trade_count: int
    winning_trades: int
    losing_trades: int


class AttributionSummary(BaseModel):
    total_pnl: float
    total_trades: int
    by_strategy: List[StrategyAttribution]
    by_asset: List[AssetAttribution]
    by_direction: List[DirectionAttribution]
    realization: RealizationAttribution
    by_time: List[TimeBucket]
