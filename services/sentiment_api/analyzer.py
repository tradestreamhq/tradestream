"""Keyword-based sentiment analyzer for financial text."""

import re
from datetime import datetime
from typing import Optional

from services.sentiment_api.models import SentimentRecord

# Financial sentiment word lists
POSITIVE_WORDS = frozenset(
    [
        "bullish",
        "surge",
        "rally",
        "gain",
        "gains",
        "profit",
        "profits",
        "growth",
        "uptrend",
        "breakout",
        "moon",
        "soar",
        "soaring",
        "pump",
        "buy",
        "long",
        "support",
        "recovery",
        "bounce",
        "accumulate",
        "accumulation",
        "outperform",
        "upgrade",
        "optimistic",
        "positive",
        "strong",
        "strength",
        "high",
        "higher",
        "rise",
        "rising",
        "up",
        "boom",
        "hot",
        "demand",
        "opportunity",
    ]
)

NEGATIVE_WORDS = frozenset(
    [
        "bearish",
        "crash",
        "dump",
        "sell",
        "short",
        "loss",
        "losses",
        "decline",
        "downtrend",
        "breakdown",
        "plunge",
        "plummet",
        "drop",
        "dropping",
        "tank",
        "tanking",
        "weak",
        "weakness",
        "fear",
        "panic",
        "risk",
        "bubble",
        "scam",
        "fraud",
        "hack",
        "exploit",
        "liquidation",
        "capitulation",
        "resistance",
        "downgrade",
        "pessimistic",
        "negative",
        "low",
        "lower",
        "fall",
        "falling",
        "red",
        "oversold",
        "warning",
    ]
)

_WORD_RE = re.compile(r"[a-z]+")


def analyze_text(
    text: str,
    symbol: str,
    source: str,
    timestamp: Optional[datetime] = None,
) -> SentimentRecord:
    """Score a text snippet for financial sentiment.

    Uses keyword matching to produce a score between -1 and +1.
    Confidence is based on the proportion of sentiment words found.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()

    words = _WORD_RE.findall(text.lower())
    if not words:
        return SentimentRecord(
            source=source,
            symbol=symbol,
            timestamp=timestamp,
            score=0.0,
            confidence=0.0,
            raw_text_snippet=text[:280],
        )

    pos_count = sum(1 for w in words if w in POSITIVE_WORDS)
    neg_count = sum(1 for w in words if w in NEGATIVE_WORDS)
    sentiment_count = pos_count + neg_count

    if sentiment_count == 0:
        score = 0.0
        confidence = 0.0
    else:
        score = (pos_count - neg_count) / sentiment_count
        # Confidence scales with how many sentiment words appear relative to total
        confidence = min(sentiment_count / max(len(words), 1), 1.0)

    snippet = text[:280]

    return SentimentRecord(
        source=source,
        symbol=symbol,
        timestamp=timestamp,
        score=max(-1.0, min(1.0, score)),
        confidence=round(confidence, 4),
        raw_text_snippet=snippet,
    )
