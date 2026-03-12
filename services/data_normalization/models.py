"""Unified candle data models for cross-exchange normalization."""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class NormalizedCandle(BaseModel):
    """Unified candle representation across all exchanges."""

    symbol: str
    exchange: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @field_validator("open", "high", "low", "close")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Price must be non-negative, got {v}")
        return v

    @field_validator("volume")
    @classmethod
    def volume_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Volume must be non-negative, got {v}")
        return v

    @model_validator(mode="after")
    def high_gte_low(self) -> "NormalizedCandle":
        if self.high < self.low:
            raise ValueError(
                f"High ({self.high}) must be >= low ({self.low})"
            )
        return self
