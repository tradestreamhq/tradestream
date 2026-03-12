"""Liquidity scoring engine.

Scores assets on a 0-100 scale based on four components:
- 30-day average daily volume (35%)
- Average bid-ask spread (25%)
- Order book depth in USD (25%)
- Trade frequency per hour (15%)
"""

import math

from services.liquidity_scoring.models import LiquidityCategory, LiquidityMetrics

# Component weights (must sum to 1.0)
WEIGHT_VOLUME = 0.35
WEIGHT_SPREAD = 0.25
WEIGHT_DEPTH = 0.25
WEIGHT_FREQUENCY = 0.15

# Reference values for normalization (based on top-tier crypto assets)
REF_VOLUME_USD = 1_000_000_000  # $1B daily volume = perfect score
REF_SPREAD_PCT = 0.01  # 0.01% spread = perfect score
REF_DEPTH_USD = 10_000_000  # $10M order book depth = perfect score
REF_FREQUENCY_PER_HOUR = 5000  # 5000 trades/hour = perfect score


def _log_normalize(value: float, reference: float) -> float:
    """Normalize a value to 0-100 using log scale relative to a reference.

    Values at or above the reference score 100. Values approach 0
    as they decrease by orders of magnitude below the reference.
    """
    if value <= 0:
        return 0.0
    ratio = value / reference
    if ratio >= 1.0:
        return 100.0
    # log10(ratio) ranges from -inf to 0; we clamp at -3 (0.001x reference)
    log_val = max(math.log10(ratio), -3.0)
    return round(max(0.0, (log_val + 3.0) / 3.0 * 100.0), 2)


def _spread_score(spread_pct: float) -> float:
    """Score spread inversely: tighter spreads score higher.

    A spread at or below the reference is 100. Wider spreads score lower.
    """
    if spread_pct <= 0:
        return 100.0
    if spread_pct <= REF_SPREAD_PCT:
        return 100.0
    # Ratio > 1 means spread is wider than ideal
    ratio = REF_SPREAD_PCT / spread_pct
    if ratio <= 0.001:
        return 0.0
    log_val = max(math.log10(ratio), -3.0)
    return round(max(0.0, (log_val + 3.0) / 3.0 * 100.0), 2)


def compute_score(metrics: LiquidityMetrics) -> tuple[float, float, float, float, float]:
    """Compute the overall liquidity score and individual components.

    Returns:
        Tuple of (total_score, volume_component, spread_component,
                  depth_component, frequency_component)
    """
    volume_score = _log_normalize(metrics.avg_daily_volume_30d, REF_VOLUME_USD)
    spread_score_val = _spread_score(metrics.avg_spread_pct)
    depth_score = _log_normalize(metrics.order_book_depth_usd, REF_DEPTH_USD)
    freq_score = _log_normalize(metrics.trade_frequency_per_hour, REF_FREQUENCY_PER_HOUR)

    total = (
        volume_score * WEIGHT_VOLUME
        + spread_score_val * WEIGHT_SPREAD
        + depth_score * WEIGHT_DEPTH
        + freq_score * WEIGHT_FREQUENCY
    )
    total = round(min(100.0, max(0.0, total)), 2)

    return total, volume_score, spread_score_val, depth_score, freq_score
