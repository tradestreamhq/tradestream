"""Market sentiment data aggregator.

Collects and normalises sentiment data from multiple external sources:
- Fear & Greed Index (crypto / traditional)
- Social media mention volume and sentiment
- News headline sentiment scores
- Crypto-specific: funding rates, long/short ratios

All scores are normalised to the range [-1, +1] where:
  -1 = extreme fear / bearish
   0 = neutral
  +1 = extreme greed / bullish
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class SentimentSourceType(str, Enum):
    FEAR_GREED = "fear_greed"
    SOCIAL_MEDIA = "social_media"
    NEWS = "news"
    FUNDING_RATE = "funding_rate"
    LONG_SHORT_RATIO = "long_short_ratio"


@dataclass
class SentimentDataPoint:
    """A single sentiment reading from one source."""

    source: SentimentSourceType
    raw_value: float  # original value from the source
    normalised_score: float  # mapped to [-1, +1]
    timestamp: float  # epoch seconds
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregatedSentiment:
    """Aggregated sentiment across all sources for a symbol."""

    symbol: str
    composite_score: float  # weighted average [-1, +1]
    label: str  # extreme_fear / fear / neutral / greed / extreme_greed
    source_scores: List[SentimentDataPoint] = field(default_factory=list)
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

# Default weights when computing composite score
SOURCE_WEIGHTS: Dict[SentimentSourceType, float] = {
    SentimentSourceType.FEAR_GREED: 0.30,
    SentimentSourceType.SOCIAL_MEDIA: 0.20,
    SentimentSourceType.NEWS: 0.25,
    SentimentSourceType.FUNDING_RATE: 0.15,
    SentimentSourceType.LONG_SHORT_RATIO: 0.10,
}


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def sentiment_label(score: float) -> str:
    """Map a [-1, +1] score to a human-readable label."""
    if score <= -0.6:
        return "extreme_fear"
    if score <= -0.2:
        return "fear"
    if score < 0.2:
        return "neutral"
    if score < 0.6:
        return "greed"
    return "extreme_greed"


def normalise_fear_greed(value: float) -> float:
    """Normalise 0-100 Fear & Greed Index to [-1, +1].

    0 = extreme fear -> -1,  50 = neutral -> 0,  100 = extreme greed -> +1.
    """
    return _clamp((value - 50.0) / 50.0)


def normalise_funding_rate(rate: float) -> float:
    """Normalise funding rate to sentiment score.

    Positive funding = longs pay shorts = bullish bias -> positive score.
    Typical range: -0.01 to +0.01 (as a fraction).
    Scale by 100 so ±0.01 maps to ±1.
    """
    return _clamp(rate * 100.0)


def normalise_long_short_ratio(ratio: float) -> float:
    """Normalise long/short ratio to sentiment score.

    ratio > 1 = more longs = bullish, ratio < 1 = more shorts = bearish.
    Use log-like scaling:  (ratio - 1) capped at [-1, +1].
    """
    return _clamp(ratio - 1.0)


def normalise_social_score(mentions: float, avg_mentions: float) -> float:
    """Normalise social media mention volume as deviation from average.

    Higher than average = more buzz = greed-leaning, lower = fear-leaning.
    """
    if avg_mentions <= 0:
        return 0.0
    deviation = (mentions - avg_mentions) / avg_mentions
    return _clamp(deviation)


def normalise_news_score(score: float) -> float:
    """Normalise news sentiment score.

    Expects input already in [-1, +1] range from NLP model.
    """
    return _clamp(score)


# ---------------------------------------------------------------------------
# Source fetchers
# ---------------------------------------------------------------------------


class SentimentDataFetcher:
    """Fetches sentiment data from external APIs.

    Each fetch method returns a SentimentDataPoint or None on failure.
    Methods accept an optional httpx.Client for testability.
    """

    def __init__(
        self,
        fear_greed_url: str = "https://api.alternative.me/fng/",
        timeout: float = 10.0,
    ):
        self._fear_greed_url = fear_greed_url
        self._timeout = timeout

    def fetch_fear_greed(
        self, client: Optional[httpx.Client] = None
    ) -> Optional[SentimentDataPoint]:
        """Fetch the current Crypto Fear & Greed Index."""
        try:
            c = client or httpx.Client(timeout=self._timeout)
            resp = c.get(self._fear_greed_url, params={"limit": "1"})
            resp.raise_for_status()
            data = resp.json()
            entry = data["data"][0]
            raw = float(entry["value"])
            return SentimentDataPoint(
                source=SentimentSourceType.FEAR_GREED,
                raw_value=raw,
                normalised_score=normalise_fear_greed(raw),
                timestamp=float(entry.get("timestamp", time.time())),
                metadata={"classification": entry.get("value_classification", "")},
            )
        except Exception:
            logger.warning("Failed to fetch Fear & Greed Index", exc_info=True)
            return None

    def fetch_funding_rate(
        self,
        symbol: str,
        rate: float,
    ) -> SentimentDataPoint:
        """Create a sentiment data point from a funding rate value.

        In production the rate is fetched from an exchange API; this method
        accepts the pre-fetched value for flexibility.
        """
        return SentimentDataPoint(
            source=SentimentSourceType.FUNDING_RATE,
            raw_value=rate,
            normalised_score=normalise_funding_rate(rate),
            timestamp=time.time(),
            metadata={"symbol": symbol},
        )

    def fetch_long_short_ratio(
        self,
        symbol: str,
        ratio: float,
    ) -> SentimentDataPoint:
        """Create a sentiment data point from a long/short ratio."""
        return SentimentDataPoint(
            source=SentimentSourceType.LONG_SHORT_RATIO,
            raw_value=ratio,
            normalised_score=normalise_long_short_ratio(ratio),
            timestamp=time.time(),
            metadata={"symbol": symbol},
        )

    def fetch_social_sentiment(
        self,
        mentions: float,
        avg_mentions: float,
    ) -> SentimentDataPoint:
        """Create a data point from social media mention data."""
        return SentimentDataPoint(
            source=SentimentSourceType.SOCIAL_MEDIA,
            raw_value=mentions,
            normalised_score=normalise_social_score(mentions, avg_mentions),
            timestamp=time.time(),
            metadata={"avg_mentions": avg_mentions},
        )

    def fetch_news_sentiment(
        self,
        score: float,
        headline_count: int = 0,
    ) -> SentimentDataPoint:
        """Create a data point from news sentiment analysis."""
        return SentimentDataPoint(
            source=SentimentSourceType.NEWS,
            raw_value=score,
            normalised_score=normalise_news_score(score),
            timestamp=time.time(),
            metadata={"headline_count": headline_count},
        )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_sentiment(
    symbol: str,
    data_points: List[SentimentDataPoint],
    weights: Optional[Dict[SentimentSourceType, float]] = None,
) -> AggregatedSentiment:
    """Compute a weighted composite sentiment score from multiple sources.

    Args:
        symbol: The trading symbol.
        data_points: Individual source readings.
        weights: Per-source weight overrides (defaults to SOURCE_WEIGHTS).

    Returns:
        AggregatedSentiment with the composite score and breakdown.
    """
    w = weights or SOURCE_WEIGHTS
    now = time.time()

    if not data_points:
        return AggregatedSentiment(
            symbol=symbol,
            composite_score=0.0,
            label="neutral",
            source_scores=[],
            timestamp=now,
        )

    total_weight = 0.0
    weighted_sum = 0.0
    for dp in data_points:
        source_w = w.get(dp.source, 0.1)
        total_weight += source_w
        weighted_sum += source_w * dp.normalised_score

    composite = _clamp(weighted_sum / total_weight) if total_weight > 0 else 0.0
    composite = round(composite, 4)

    return AggregatedSentiment(
        symbol=symbol,
        composite_score=composite,
        label=sentiment_label(composite),
        source_scores=data_points,
        timestamp=now,
    )
