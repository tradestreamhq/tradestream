"""Deterministic opportunity scoring engine per specs/opportunity-scoring/SPEC.md.

Implements the spec's weighted scoring formula with:
- Sharpe-like risk adjustment for expected returns
- Market regime detection with dynamic normalization caps
- Score caching at creation time (immutable after computation)
- Tier assignment (HOT/GOOD/NEUTRAL/LOW)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional


@dataclass(frozen=True)
class RegimeCaps:
    """Normalization caps for a given market regime."""

    max_return: float
    max_volatility: float


# Default scoring weights from spec
DEFAULT_WEIGHTS = {
    "confidence": 0.25,
    "expected_return": 0.30,
    "consensus": 0.20,
    "volatility": 0.15,
    "freshness": 0.10,
}

# Default values when data is missing (per spec constraints)
DEFAULTS = {
    "expected_return": 0.01,
    "return_stddev": 0.0,
    "volatility": 0.015,
    "market_regime": "normal",
}

# Regime percentile thresholds
EXTREME_PERCENTILE = 0.95
HIGH_VOL_PERCENTILE = 0.80

# Sharpe adjustment cap
MAX_SHARPE_FACTOR = 2.0

# Freshness window in minutes
FRESHNESS_WINDOW_MIN = 60


def get_regime_adjusted_caps(regime: str) -> RegimeCaps:
    """Return normalization caps based on current market regime.

    During extreme conditions, standard caps would cause all signals to max out
    volatility scores. Regime-adjusted caps maintain meaningful differentiation.
    """
    if regime == "extreme":
        return RegimeCaps(max_return=0.15, max_volatility=0.10)
    elif regime == "high_volatility":
        return RegimeCaps(max_return=0.08, max_volatility=0.05)
    else:
        return RegimeCaps(max_return=0.05, max_volatility=0.03)


def apply_sharpe_adjustment(expected_return: float, return_stddev: float) -> float:
    """Apply Sharpe-like adjustment to expected return.

    Rewards strategies with consistent returns over volatile ones.
    A strategy with 3% return and 1% stddev scores higher than
    a strategy with 3% return and 3% stddev.

    Args:
        expected_return: Historical average return (e.g., 0.032 for 3.2%).
        return_stddev: Standard deviation of returns.

    Returns:
        Risk-adjusted return value.
    """
    if return_stddev <= 0:
        return expected_return

    sharpe_factor = expected_return / return_stddev
    adjustment_multiplier = min(sharpe_factor, MAX_SHARPE_FACTOR) / MAX_SHARPE_FACTOR
    return expected_return * (0.5 + 0.5 * adjustment_multiplier)


def detect_regime_from_percentile(volatility_percentile: float) -> str:
    """Detect market regime from a volatility percentile.

    Args:
        volatility_percentile: 30-day volatility percentile (0.0 - 1.0).

    Returns:
        One of "normal", "high_volatility", or "extreme".
    """
    if volatility_percentile >= EXTREME_PERCENTILE:
        return "extreme"
    elif volatility_percentile >= HIGH_VOL_PERCENTILE:
        return "high_volatility"
    else:
        return "normal"


def calculate_opportunity_score(
    confidence: float,
    expected_return: float,
    return_stddev: float,
    consensus_pct: float,
    volatility: float,
    minutes_ago: int,
    market_regime: str = "normal",
    weights: Optional[dict] = None,
) -> float:
    """Calculate opportunity score (0-100) for a trading signal.

    Uses the spec formula with regime-adjusted caps and Sharpe adjustment.

    Args:
        confidence: Signal confidence 0.0-1.0.
        expected_return: Weighted average return (e.g. 0.032 for 3.2%).
        return_stddev: Standard deviation of strategy returns.
        consensus_pct: Fraction of strategies agreeing 0.0-1.0.
        volatility: Hourly volatility (e.g. 0.021 for 2.1%).
        minutes_ago: Signal age in minutes.
        market_regime: One of "normal", "high_volatility", "extreme".
        weights: Override default weights dict.

    Returns:
        Float between 0 and 100.
    """
    w = weights or DEFAULT_WEIGHTS
    caps = get_regime_adjusted_caps(market_regime)

    # Risk-adjusted return (Sharpe-like normalization)
    risk_adjusted_return = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = (
        min(risk_adjusted_return / caps.max_return, 1.0) if caps.max_return > 0 else 0.0
    )

    # Normalize volatility with regime-adjusted cap
    volatility_score = (
        min(volatility / caps.max_volatility, 1.0) if caps.max_volatility > 0 else 0.0
    )

    # Freshness decay: 100% at 0 min, 50% at 30 min, 0% at 60 min
    freshness_score = max(0.0, 1.0 - (minutes_ago / FRESHNESS_WINDOW_MIN))

    score = (
        w["confidence"] * confidence
        + w["expected_return"] * return_score
        + w["consensus"] * consensus_pct
        + w["volatility"] * volatility_score
        + w["freshness"] * freshness_score
    ) * 100

    return round(score, 1)


def calculate_expected_return(
    strategy_returns: List[tuple],
) -> tuple:
    """Calculate weighted expected return and stddev from strategy data.

    Args:
        strategy_returns: List of (avg_return, stddev, weight) tuples for
            agreeing strategies.

    Returns:
        Tuple of (weighted_avg_return, weighted_stddev).
    """
    if not strategy_returns:
        return 0.0, 0.0

    total_weight = sum(w for _, _, w in strategy_returns)
    if total_weight <= 0:
        return 0.0, 0.0

    weighted_return = sum(r * w for r, _, w in strategy_returns) / total_weight
    weighted_stddev = sum(s * w for _, s, w in strategy_returns) / total_weight
    return weighted_return, weighted_stddev


def assign_tier(score: float) -> str:
    """Map a score to a tier label.

    Args:
        score: Numeric score 0-100.

    Returns:
        HOT (80+), GOOD (60-79), NEUTRAL (40-59), or LOW (0-39).
    """
    if score >= 80:
        return "HOT"
    elif score >= 60:
        return "GOOD"
    elif score >= 40:
        return "NEUTRAL"
    else:
        return "LOW"


def compute_score_breakdown(
    confidence: float,
    expected_return: float,
    return_stddev: float,
    consensus_pct: float,
    volatility: float,
    volatility_percentile: float,
    minutes_ago: int,
    market_regime: str = "normal",
) -> dict:
    """Compute opportunity score with full factor breakdown.

    Returns a dict containing the score, tier, and per-factor contributions
    suitable for the scored signal format in the spec.

    Args:
        confidence: Signal confidence 0.0-1.0.
        expected_return: Expected return percentage.
        return_stddev: Standard deviation of returns.
        consensus_pct: Strategy consensus 0.0-1.0.
        volatility: Hourly volatility.
        volatility_percentile: 30-day volatility percentile.
        minutes_ago: Signal age in minutes.
        market_regime: Market regime string.

    Returns:
        Dict with score, tier, market_regime, and per-factor breakdown.
    """
    caps = get_regime_adjusted_caps(market_regime)
    risk_adjusted = apply_sharpe_adjustment(expected_return, return_stddev)
    return_score = (
        min(risk_adjusted / caps.max_return, 1.0) if caps.max_return > 0 else 0.0
    )
    volatility_score = (
        min(volatility / caps.max_volatility, 1.0) if caps.max_volatility > 0 else 0.0
    )
    freshness_score = max(0.0, 1.0 - (minutes_ago / FRESHNESS_WINDOW_MIN))

    w = DEFAULT_WEIGHTS
    contributions = {
        "confidence": round(w["confidence"] * confidence * 100, 1),
        "expected_return": round(w["expected_return"] * return_score * 100, 1),
        "consensus": round(w["consensus"] * consensus_pct * 100, 1),
        "volatility": round(w["volatility"] * volatility_score * 100, 1),
        "freshness": round(w["freshness"] * freshness_score * 100, 1),
    }

    total = round(sum(contributions.values()), 1)
    tier = assign_tier(total)

    return {
        "opportunity_score": total,
        "opportunity_tier": tier,
        "market_regime": market_regime,
        "opportunity_factors": {
            "confidence": {
                "value": confidence,
                "contribution": contributions["confidence"],
            },
            "expected_return": {
                "value": expected_return,
                "stddev": return_stddev,
                "risk_adjusted": round(risk_adjusted, 6),
                "contribution": contributions["expected_return"],
            },
            "consensus": {
                "value": consensus_pct,
                "contribution": contributions["consensus"],
            },
            "volatility": {
                "value": volatility,
                "percentile": volatility_percentile,
                "contribution": contributions["volatility"],
            },
            "freshness": {
                "value": minutes_ago,
                "contribution": contributions["freshness"],
                "cached": True,
            },
        },
    }


@dataclass
class ScoredSignal:
    """A signal with its opportunity score cached at creation time.

    Scores are immutable once computed at signal creation. This ensures:
    1. Deterministic behavior (same signal = same score always)
    2. No score drift as signals age
    3. Fair comparison between signals of different ages
    """

    signal_id: str
    symbol: str
    action: str
    confidence: float
    opportunity_score: float
    opportunity_tier: str
    market_regime: str
    opportunity_factors: dict
    scored_at: datetime
    strategies_analyzed: int
    strategies_agreeing: int

    @property
    def display_age_minutes(self) -> int:
        """For UI display only - does not affect score."""
        delta = datetime.now(timezone.utc) - self.scored_at
        return int(delta.total_seconds() / 60)

    @property
    def is_stale(self) -> bool:
        """Signal is stale if older than freshness window (60 min)."""
        return self.display_age_minutes >= FRESHNESS_WINDOW_MIN

    @classmethod
    def from_signal(
        cls,
        signal_id: str,
        symbol: str,
        action: str,
        confidence: float,
        expected_return: float,
        return_stddev: float,
        consensus_pct: float,
        volatility: float,
        volatility_percentile: float,
        strategies_analyzed: int,
        strategies_agreeing: int,
        market_regime: Optional[str] = None,
    ) -> "ScoredSignal":
        """Create a ScoredSignal with score computed and cached at creation.

        If market_regime is not provided, it is detected from the
        volatility_percentile.
        """
        if market_regime is None:
            market_regime = detect_regime_from_percentile(volatility_percentile)

        breakdown = compute_score_breakdown(
            confidence=confidence,
            expected_return=expected_return,
            return_stddev=return_stddev,
            consensus_pct=consensus_pct,
            volatility=volatility,
            volatility_percentile=volatility_percentile,
            minutes_ago=0,  # Always fresh at creation — score is cached
            market_regime=market_regime,
        )

        return cls(
            signal_id=signal_id,
            symbol=symbol,
            action=action,
            confidence=confidence,
            opportunity_score=breakdown["opportunity_score"],
            opportunity_tier=breakdown["opportunity_tier"],
            market_regime=breakdown["market_regime"],
            opportunity_factors=breakdown["opportunity_factors"],
            scored_at=datetime.now(timezone.utc),
            strategies_analyzed=strategies_analyzed,
            strategies_agreeing=strategies_agreeing,
        )
