"""
Sentiment analysis engine.

Computes market sentiment scores from technical indicators, volume analysis,
and price momentum. Aggregates across multiple timeframes.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

TIMEFRAMES = ["1h", "4h", "1d", "1w"]

# Weights for aggregating timeframe scores (longer = more weight)
TIMEFRAME_WEIGHTS = {"1h": 0.1, "4h": 0.2, "1d": 0.35, "1w": 0.35}


@dataclass
class SentimentBreakdown:
    rsi: float = 0.0
    macd_trend: float = 0.0
    volume: float = 0.0
    price_momentum: float = 0.0


@dataclass
class TimeframeSentiment:
    timeframe: str
    score: float
    breakdown: SentimentBreakdown


@dataclass
class SentimentResult:
    symbol: str
    score: float
    label: str
    timeframe_scores: List[TimeframeSentiment]
    breakdown: SentimentBreakdown


@dataclass
class SentimentHistoryPoint:
    timestamp: str
    score: float
    label: str


@dataclass
class DivergenceSignal:
    symbol: str
    sentiment_score: float
    price_change_pct: float
    divergence_type: str  # "bullish_divergence" or "bearish_divergence"
    strength: float


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _sentiment_label(score: float) -> str:
    if score >= 0.6:
        return "strongly_bullish"
    if score >= 0.2:
        return "bullish"
    if score > -0.2:
        return "neutral"
    if score > -0.6:
        return "bearish"
    return "strongly_bearish"


def compute_rsi_sentiment(rsi: float) -> float:
    """Convert RSI (0-100) to sentiment score (-1 to +1).

    RSI < 30 is oversold (bullish), RSI > 70 is overbought (bearish).
    """
    if rsi <= 0 or rsi >= 100:
        return 0.0
    # Map 0-100 -> +1 to -1 with neutral zone around 50
    return _clamp((50 - rsi) / 50)


def compute_macd_sentiment(macd: float, signal: float, histogram: float) -> float:
    """Compute sentiment from MACD components.

    Positive histogram with MACD above signal is bullish.
    """
    if histogram == 0 and macd == 0:
        return 0.0
    # Histogram direction is primary signal
    hist_sign = 1.0 if histogram > 0 else -1.0
    # Crossover boost: MACD vs signal line
    crossover = 1.0 if macd > signal else -1.0
    # Combine with histogram as primary, crossover as secondary
    raw = 0.6 * hist_sign + 0.4 * crossover
    return _clamp(raw)


def compute_volume_sentiment(
    current_volume: float, avg_volume: float, price_change_pct: float
) -> float:
    """Compute sentiment from volume analysis.

    High volume confirming price direction is directional;
    high volume against trend suggests reversal.
    """
    if avg_volume <= 0:
        return 0.0
    volume_ratio = current_volume / avg_volume
    # Volume spike detection (> 1.5x average)
    volume_factor = min(volume_ratio / 1.5, 2.0) - 1.0  # -1 to +1 range
    # Volume confirms price direction
    direction = 1.0 if price_change_pct > 0 else (-1.0 if price_change_pct < 0 else 0.0)
    return _clamp(volume_factor * direction)


def compute_momentum_sentiment(price_changes: Sequence[float]) -> float:
    """Compute sentiment from price momentum (sequence of % changes).

    Uses weighted average of recent price changes, with more weight
    on recent data.
    """
    if not price_changes:
        return 0.0
    n = len(price_changes)
    weights = [i + 1 for i in range(n)]
    total_weight = sum(weights)
    weighted_sum = sum(w * c for w, c in zip(weights, price_changes))
    avg_change = weighted_sum / total_weight
    # Scale: 5% move maps to ~1.0 score
    return _clamp(avg_change / 5.0)


def compute_timeframe_sentiment(
    candles: List[Dict[str, Any]],
) -> Optional[TimeframeSentiment]:
    """Compute sentiment for a single timeframe from OHLCV candles.

    Expects candles sorted oldest-to-newest with keys:
    time, open, high, low, close, volume
    """
    if len(candles) < 14:
        return None

    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]

    # RSI calculation (14-period)
    rsi = _calculate_rsi(closes, 14)

    # MACD (12, 26, 9)
    macd, signal, histogram = _calculate_macd(closes, 12, 26, 9)

    # Volume analysis
    avg_volume = sum(volumes[-20:]) / min(len(volumes), 20)
    current_volume = volumes[-1]
    latest_change = (
        ((closes[-1] - closes[-2]) / closes[-2]) * 100 if closes[-2] != 0 else 0
    )

    # Price momentum (last 5 period changes)
    price_changes = []
    lookback = min(5, len(closes) - 1)
    for i in range(lookback):
        idx = -(lookback - i)
        prev_idx = idx - 1
        if closes[prev_idx] != 0:
            pct = ((closes[idx] - closes[prev_idx]) / closes[prev_idx]) * 100
            price_changes.append(pct)

    rsi_score = compute_rsi_sentiment(rsi)
    macd_score = compute_macd_sentiment(macd, signal, histogram)
    vol_score = compute_volume_sentiment(current_volume, avg_volume, latest_change)
    mom_score = compute_momentum_sentiment(price_changes)

    breakdown = SentimentBreakdown(
        rsi=round(rsi_score, 4),
        macd_trend=round(macd_score, 4),
        volume=round(vol_score, 4),
        price_momentum=round(mom_score, 4),
    )

    # Weighted combination
    score = 0.3 * rsi_score + 0.25 * macd_score + 0.2 * vol_score + 0.25 * mom_score
    return TimeframeSentiment(
        timeframe="",  # Set by caller
        score=round(_clamp(score), 4),
        breakdown=breakdown,
    )


def compute_sentiment(
    symbol: str, candles_by_timeframe: Dict[str, List[Dict[str, Any]]]
) -> Optional[SentimentResult]:
    """Compute aggregated sentiment across multiple timeframes."""
    tf_results: List[TimeframeSentiment] = []

    for tf in TIMEFRAMES:
        candles = candles_by_timeframe.get(tf, [])
        if not candles:
            continue
        result = compute_timeframe_sentiment(candles)
        if result:
            result.timeframe = tf
            tf_results.append(result)

    if not tf_results:
        return None

    # Weighted aggregation across timeframes
    total_weight = 0.0
    weighted_score = 0.0
    agg_breakdown = SentimentBreakdown()

    for tf_result in tf_results:
        w = TIMEFRAME_WEIGHTS.get(tf_result.timeframe, 0.1)
        total_weight += w
        weighted_score += w * tf_result.score
        agg_breakdown.rsi += w * tf_result.breakdown.rsi
        agg_breakdown.macd_trend += w * tf_result.breakdown.macd_trend
        agg_breakdown.volume += w * tf_result.breakdown.volume
        agg_breakdown.price_momentum += w * tf_result.breakdown.price_momentum

    if total_weight > 0:
        final_score = weighted_score / total_weight
        agg_breakdown.rsi = round(agg_breakdown.rsi / total_weight, 4)
        agg_breakdown.macd_trend = round(agg_breakdown.macd_trend / total_weight, 4)
        agg_breakdown.volume = round(agg_breakdown.volume / total_weight, 4)
        agg_breakdown.price_momentum = round(
            agg_breakdown.price_momentum / total_weight, 4
        )
    else:
        final_score = 0.0

    final_score = round(_clamp(final_score), 4)

    return SentimentResult(
        symbol=symbol,
        score=final_score,
        label=_sentiment_label(final_score),
        timeframe_scores=tf_results,
        breakdown=agg_breakdown,
    )


def detect_divergences(
    sentiment_results: List[SentimentResult],
    price_changes: Dict[str, float],
    threshold: float = 0.3,
) -> List[DivergenceSignal]:
    """Detect symbols where price and sentiment diverge.

    A bullish divergence: price falling but sentiment is positive.
    A bearish divergence: price rising but sentiment is negative.
    """
    divergences: List[DivergenceSignal] = []

    for result in sentiment_results:
        price_chg = price_changes.get(result.symbol, 0.0)
        score = result.score

        # Bullish divergence: price down, sentiment up
        if price_chg < -threshold and score > threshold:
            strength = min(abs(price_chg) + abs(score), 2.0) / 2.0
            divergences.append(
                DivergenceSignal(
                    symbol=result.symbol,
                    sentiment_score=score,
                    price_change_pct=round(price_chg, 4),
                    divergence_type="bullish_divergence",
                    strength=round(strength, 4),
                )
            )
        # Bearish divergence: price up, sentiment down
        elif price_chg > threshold and score < -threshold:
            strength = min(abs(price_chg) + abs(score), 2.0) / 2.0
            divergences.append(
                DivergenceSignal(
                    symbol=result.symbol,
                    sentiment_score=score,
                    price_change_pct=round(price_chg, 4),
                    divergence_type="bearish_divergence",
                    strength=round(strength, 4),
                )
            )

    divergences.sort(key=lambda d: d.strength, reverse=True)
    return divergences


# ---------------------------------------------------------------------------
# Technical indicator helpers
# ---------------------------------------------------------------------------


def _calculate_rsi(closes: List[float], period: int = 14) -> float:
    """Calculate RSI using exponential moving average method."""
    if len(closes) < period + 1:
        return 50.0  # Neutral default

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _ema(values: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average."""
    if not values:
        return []
    k = 2.0 / (period + 1)
    result = [values[0]]
    for i in range(1, len(values)):
        result.append(values[i] * k + result[-1] * (1 - k))
    return result


def _calculate_macd(
    closes: List[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple:
    """Calculate MACD, signal line, and histogram."""
    if len(closes) < slow + signal_period:
        return 0.0, 0.0, 0.0

    fast_ema = _ema(closes, fast)
    slow_ema = _ema(closes, slow)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = _ema(macd_line, signal_period)

    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    histogram = macd_val - signal_val
    return macd_val, signal_val, histogram
