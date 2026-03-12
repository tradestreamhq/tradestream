"""Sentiment analysis data models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class SentimentRecord:
    """A single sentiment measurement from a text source."""

    source: str
    symbol: str
    timestamp: datetime
    score: float  # -1.0 (bearish) to +1.0 (bullish)
    confidence: float  # 0.0 to 1.0
    raw_text_snippet: str

    def __post_init__(self):
        if not -1.0 <= self.score <= 1.0:
            raise ValueError(f"score must be between -1 and 1, got {self.score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0 and 1, got {self.confidence}"
            )

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "raw_text_snippet": self.raw_text_snippet,
        }


@dataclass
class AggregatedSentiment:
    """Rolling sentiment summary for a symbol."""

    symbol: str
    average_score: float
    record_count: int
    velocity: float  # change in average score per hour
    from_time: datetime
    to_time: datetime
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "average_score": round(self.average_score, 4),
            "record_count": self.record_count,
            "velocity": round(self.velocity, 4),
            "from_time": self.from_time.isoformat(),
            "to_time": self.to_time.isoformat(),
            "sources": self.sources,
        }
