"""
Data models for portfolio allocation optimization.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StrategyReturns(BaseModel):
    """Historical returns for a single strategy."""

    strategy_id: str = Field(..., description="Unique strategy identifier")
    returns: List[float] = Field(
        ..., description="Historical period returns (e.g. daily)"
    )


class OptimizationRequest(BaseModel):
    """Request payload for portfolio optimization."""

    strategies: List[StrategyReturns] = Field(
        ..., min_length=2, description="Historical returns per strategy (min 2)"
    )
    objective: str = Field(
        "max_sharpe",
        pattern="^(max_sharpe|min_variance|target_return)$",
        description="Optimization objective",
    )
    target_return: Optional[float] = Field(
        None, description="Required when objective is target_return"
    )
    risk_free_rate: float = Field(0.0, description="Annualized risk-free rate")
    min_weight: float = Field(
        0.0, ge=0.0, le=1.0, description="Min allocation per strategy"
    )
    max_weight: float = Field(
        1.0, ge=0.0, le=1.0, description="Max allocation per strategy"
    )


class OptimizationResult(BaseModel):
    """Result of a portfolio optimization."""

    weights: Dict[str, float] = Field(
        ..., description="Optimal allocation weights per strategy"
    )
    expected_return: float = Field(
        ..., description="Expected portfolio return (per period)"
    )
    volatility: float = Field(
        ..., description="Expected portfolio volatility (per period)"
    )
    sharpe_ratio: float = Field(..., description="Portfolio Sharpe ratio")


class EfficientFrontierPoint(BaseModel):
    """A single point on the efficient frontier."""

    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: Dict[str, float]


class EfficientFrontierResponse(BaseModel):
    """Full efficient frontier output."""

    points: List[EfficientFrontierPoint]
    optimal: OptimizationResult
