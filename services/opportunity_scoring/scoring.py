"""Core scoring engine — deterministic opportunity scoring per spec."""

from .models import MarketRegime, OpportunityTier, RegimeCaps, ScoreBreakdown

# Default scoring weights
WEIGHTS = {
    "confidence": 0.25,
    "expected_return": 0.30,
    "consensus": 0.20,
    "volatility": 0.15,
    "freshness": 0.10,
}

# Default values when data is missing
DEFAULTS = {
    "expected_return": 0.01,
    "return_stddev": 0.0,
    "volatility": 0.015,
    "market_regime": MarketRegime.NORMAL.value,
}

# Sharpe adjustment config
SHARPE_MAX_FACTOR = 2.0


def get_regime_caps(regime: str) -> RegimeCaps:
    """Return normalization caps based on current market regime.

    During extreme conditions, standard caps would cause all signals to
    max out volatility scores. Regime-adjusted caps maintain differentiation.

    Args:
        regime: One of "normal", "high_volatility", "extreme".

    Returns:
        RegimeCaps with max_return and max_volatility.
    """
    if regime == MarketRegime.EXTREME.value:
        return RegimeCaps(max_return=0.15, max_volatility=0.10)
    elif regime == MarketRegime.HIGH_VOLATILITY.value:
        return RegimeCaps(max_return=0.08, max_volatility=0.05)
    else:
        return RegimeCaps(max_return=0.05, max_volatility=0.03)


def apply_sharpe_adjustment(expected_return: float, return_stddev: float) -> float:
    """Apply Sharpe-like adjustment to expected return.

    Rewards strategies with consistent returns over volatile ones.

    Args:
        expected_return: Historical average return (e.g. 0.032 for 3.2%).
        return_stddev: Standard deviation of returns.

    Returns:
        Risk-adjusted return value.
    """
    if return_stddev <= 0:
        return expected_return

    sharpe_factor = expected_return / return_stddev
    adjustment_multiplier = min(sharpe_factor, SHARPE_MAX_FACTOR) / SHARPE_MAX_FACTOR
    return expected_return * (0.5 + 0.5 * adjustment_multiplier)


def detect_regime(volatility_percentile: float) -> str:
    """Detect market regime from volatility percentile.

    Args:
        volatility_percentile: 30-day volatility percentile (0.0–1.0).

    Returns:
        Market regime string.
    """
    if volatility_percentile >= 0.95:
        return MarketRegime.EXTREME.value
    elif volatility_percentile >= 0.80:
        return MarketRegime.HIGH_VOLATILITY.value
    else:
        return MarketRegime.NORMAL.value


def assign_tier(score: float) -> str:
    """Map a numeric score to a tier.

    Args:
        score: Numeric score 0–100.

    Returns:
        Tier string: HOT, GOOD, NEUTRAL, or LOW.
    """
    if score >= 80:
        return OpportunityTier.HOT.value
    elif score >= 60:
        return OpportunityTier.GOOD.value
    elif score >= 40:
        return OpportunityTier.NEUTRAL.value
    else:
        return OpportunityTier.LOW.value


def calculate_opportunity_score(
    confidence: float,
    expected_return: float,
    return_stddev: float,
    consensus_pct: float,
    volatility: float,
    minutes_ago: int,
    market_regime: str = "normal",
    volatility_percentile: float = 0.5,
) -> tuple[float, ScoreBreakdown]:
    """Calculate opportunity score (0–100) for a trading signal.

    Scores are deterministic: same inputs always produce the same score.

    Args:
        confidence: Signal confidence 0.0–1.0.
        expected_return: Percentage return, e.g. 0.032 for 3.2%.
        return_stddev: Standard deviation of strategy returns.
        consensus_pct: Fraction of strategies agreeing, 0.0–1.0.
        volatility: Hourly volatility, e.g. 0.021.
        minutes_ago: Signal age in minutes (locked at creation for caching).
        market_regime: "normal", "high_volatility", or "extreme".
        volatility_percentile: 30-day volatility percentile (0.0–1.0).

    Returns:
        Tuple of (score, ScoreBreakdown).
    """
    caps = get_regime_caps(market_regime)

    # Risk-adjusted return
    risk_adjusted = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = (
        min(risk_adjusted / caps.max_return, 1.0) if caps.max_return > 0 else 0.0
    )

    # Normalize volatility
    vol_score = (
        min(volatility / caps.max_volatility, 1.0) if caps.max_volatility > 0 else 0.0
    )

    # Freshness decay: 100% at 0 min, 50% at 30 min, 0% at 60 min
    freshness_score = max(0.0, 1.0 - (minutes_ago / 60))

    # Weighted sum
    conf_contribution = WEIGHTS["confidence"] * confidence * 100
    ret_contribution = WEIGHTS["expected_return"] * return_score * 100
    cons_contribution = WEIGHTS["consensus"] * consensus_pct * 100
    vol_contribution = WEIGHTS["volatility"] * vol_score * 100
    fresh_contribution = WEIGHTS["freshness"] * freshness_score * 100

    total = (
        conf_contribution
        + ret_contribution
        + cons_contribution
        + vol_contribution
        + fresh_contribution
    )
    total = round(total, 1)

    breakdown = ScoreBreakdown(
        confidence_value=confidence,
        confidence_contribution=round(conf_contribution, 1),
        expected_return_value=expected_return,
        expected_return_stddev=return_stddev,
        risk_adjusted_return=round(risk_adjusted, 6),
        expected_return_contribution=round(ret_contribution, 1),
        consensus_value=consensus_pct,
        consensus_contribution=round(cons_contribution, 1),
        volatility_value=volatility,
        volatility_percentile=volatility_percentile,
        volatility_contribution=round(vol_contribution, 1),
        freshness_value=minutes_ago,
        freshness_contribution=round(fresh_contribution, 1),
        market_regime=market_regime,
    )

    return total, breakdown
