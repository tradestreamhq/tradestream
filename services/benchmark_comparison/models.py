"""Data models for the benchmark comparison service."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TimePeriod(str, Enum):
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
    THREE_MONTHS = "3m"
    YTD = "ytd"
    ALL_TIME = "all"


class BenchmarkType(str, Enum):
    SPY = "SPY"
    QQQ = "QQQ"
    BTC = "BTC"
    CUSTOM = "CUSTOM"


class ReturnSeries(BaseModel):
    timestamps: List[datetime]
    values: List[float]


class BenchmarkMetrics(BaseModel):
    alpha: float = Field(..., description="Excess return vs benchmark (annualized)")
    beta: float = Field(..., description="Sensitivity to benchmark movements")
    information_ratio: float = Field(
        ..., description="Risk-adjusted excess return vs benchmark"
    )
    tracking_error: float = Field(
        ..., description="Std dev of return differences (annualized)"
    )
    strategy_return: float = Field(..., description="Total strategy return (%)")
    benchmark_return: float = Field(..., description="Total benchmark return (%)")
    excess_return: float = Field(
        ..., description="Strategy return minus benchmark return (%)"
    )
    correlation: float = Field(
        ..., description="Correlation between strategy and benchmark"
    )


class BenchmarkComparison(BaseModel):
    strategy_id: str
    benchmark: str
    period: TimePeriod
    metrics: BenchmarkMetrics
    computed_at: datetime


class BenchmarkComparisonResponse(BaseModel):
    strategy_id: str
    comparisons: List[BenchmarkComparison]
