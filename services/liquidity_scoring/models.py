"""Data models for the liquidity scoring service."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class LiquidityCategory(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class LiquidityMetrics:
    """Raw liquidity metrics for an asset."""

    symbol: str
    avg_daily_volume_30d: float
    avg_spread_pct: float
    order_book_depth_usd: float
    trade_frequency_per_hour: float


@dataclass
class LiquidityScore:
    """Computed liquidity score for an asset."""

    symbol: str
    score: float
    category: LiquidityCategory
    volume_component: float
    spread_component: float
    depth_component: float
    frequency_component: float
    scored_at: datetime

    @staticmethod
    def categorize(score: float) -> LiquidityCategory:
        if score >= 80:
            return LiquidityCategory.HIGH
        elif score >= 40:
            return LiquidityCategory.MEDIUM
        return LiquidityCategory.LOW


@dataclass
class LiquidityScoreHistory:
    """A historical liquidity score entry."""

    symbol: str
    score: float
    category: str
    scored_at: datetime
