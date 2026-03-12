"""
Pydantic models for slippage analysis request/response DTOs.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class SlippageRecord(BaseModel):
    trade_id: str = Field(..., description="Unique trade identifier")
    symbol: str = Field(..., description="Trading instrument symbol")
    side: str = Field(..., description="BUY or SELL")
    expected_price: float = Field(..., description="Price at signal time")
    fill_price: float = Field(..., description="Actual execution price")
    order_size: float = Field(..., gt=0, description="Order size in base units")
    slippage_bps: float = Field(..., description="Slippage in basis points")
    filled_at: str = Field(..., description="ISO 8601 fill timestamp")
    hour_of_day: int = Field(..., ge=0, le=23, description="Hour when trade was filled")
    size_bucket: str = Field(..., description="Order size category: small, medium, large")


class SlippageSummary(BaseModel):
    total_trades: int = Field(..., description="Number of trades analyzed")
    avg_slippage_bps: float = Field(..., description="Average slippage in basis points")
    median_slippage_bps: float = Field(..., description="Median slippage in basis points")
    worst_slippage_bps: float = Field(..., description="Worst single-trade slippage in bps")
    total_slippage_cost: float = Field(
        ..., description="Total dollar cost of slippage across all trades"
    )


class SymbolSlippage(BaseModel):
    symbol: str
    trade_count: int
    avg_slippage_bps: float
    total_slippage_cost: float


class HourlySlippage(BaseModel):
    hour: int
    trade_count: int
    avg_slippage_bps: float


class SizeBucketSlippage(BaseModel):
    bucket: str
    trade_count: int
    avg_slippage_bps: float


class AdversePattern(BaseModel):
    pattern_type: str = Field(..., description="Type of adverse pattern detected")
    description: str = Field(..., description="Human-readable description")
    severity: str = Field(..., description="low, medium, or high")
    affected_trades: int = Field(..., description="Number of trades affected")
    avg_slippage_bps: float = Field(..., description="Average slippage for affected trades")


class SlippageReport(BaseModel):
    summary: SlippageSummary
    by_symbol: List[SymbolSlippage]
    by_hour: List[HourlySlippage]
    by_size_bucket: List[SizeBucketSlippage]
    adverse_patterns: List[AdversePattern]
