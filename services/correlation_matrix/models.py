"""
Pydantic models for the Correlation Matrix service.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CorrelationPair(BaseModel):
    symbol_a: str = Field(..., description="First asset symbol")
    symbol_b: str = Field(..., description="Second asset symbol")
    correlation_30d: Optional[float] = Field(
        None, description="30-day rolling correlation"
    )
    correlation_90d: Optional[float] = Field(
        None, description="90-day rolling correlation"
    )
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


class CorrelationBreakdown(BaseModel):
    symbol_a: str = Field(..., description="First asset symbol")
    symbol_b: str = Field(..., description="Second asset symbol")
    previous_correlation: float = Field(
        ..., description="Historical average correlation"
    )
    current_correlation: float = Field(..., description="Current correlation")
    change: float = Field(..., description="Absolute change in correlation")
    window: str = Field(..., description="Time window (30d or 90d)")
    detected_at: Optional[str] = Field(None, description="Detection timestamp")


class CorrelationMatrix(BaseModel):
    symbols: List[str] = Field(..., description="Symbols in the matrix")
    window: str = Field(..., description="Time window (30d or 90d)")
    matrix: Dict[str, Dict[str, Optional[float]]] = Field(
        ..., description="Correlation matrix as nested dict"
    )
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
