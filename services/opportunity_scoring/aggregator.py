"""Signal aggregation and consensus scoring.

Collects signals from multiple sources (technical strategies, sentiment,
prediction markets) for the same trading pair and computes consensus.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from .models import ContributingSignal, ScoredOpportunity
from .scoring import (
    DEFAULTS,
    assign_tier,
    calculate_opportunity_score,
    detect_regime,
)


def calculate_expected_return(
    signals: list[ContributingSignal],
    direction: str,
) -> tuple[float, float]:
    """Calculate weighted expected return and stddev from agreeing signals.

    Args:
        signals: List of contributing signals.
        direction: The consensus direction (BUY/SELL).

    Returns:
        Tuple of (weighted_avg_return, weighted_stddev).
    """
    agreeing = [
        s for s in signals
        if s.direction == direction
        and s.expected_return is not None
        and s.confidence > 0
    ]

    if not agreeing:
        return DEFAULTS["expected_return"], DEFAULTS["return_stddev"]

    total_weight = sum(s.confidence for s in agreeing)
    if total_weight <= 0:
        return DEFAULTS["expected_return"], DEFAULTS["return_stddev"]

    weighted_return = sum(
        (s.expected_return or 0.0) * s.confidence for s in agreeing
    ) / total_weight

    weighted_stddev = sum(
        (s.return_stddev or 0.0) * s.confidence for s in agreeing
    ) / total_weight

    return weighted_return, weighted_stddev


def compute_consensus(
    signals: list[ContributingSignal],
) -> tuple[str, float, int, int]:
    """Determine consensus direction and agreement percentage.

    Args:
        signals: All signals for a trading pair.

    Returns:
        Tuple of (direction, consensus_pct, agreeing_count, total_count).
    """
    if not signals:
        return "HOLD", 0.0, 0, 0

    direction_votes: dict[str, float] = defaultdict(float)
    direction_counts: dict[str, int] = defaultdict(int)

    for s in signals:
        if s.direction in ("BUY", "SELL"):
            direction_votes[s.direction] += s.confidence
            direction_counts[s.direction] += 1

    if not direction_votes:
        return "HOLD", 0.0, 0, len(signals)

    # Winner is direction with highest confidence-weighted vote
    winner = max(direction_votes, key=direction_votes.get)
    agreeing = direction_counts[winner]
    total = sum(direction_counts.values())
    consensus_pct = agreeing / total if total > 0 else 0.0

    return winner, consensus_pct, agreeing, total


def aggregate_signals(
    symbol: str,
    signals: list[ContributingSignal],
    volatility: Optional[float] = None,
    volatility_percentile: Optional[float] = None,
) -> Optional[ScoredOpportunity]:
    """Aggregate signals for a symbol into a single scored opportunity.

    This is the main entry point: given all signals for one trading pair,
    it computes consensus, expected return, and opportunity score.

    Args:
        symbol: Trading pair (e.g. "BTC/USD").
        signals: All contributing signals from various sources.
        volatility: Recent hourly volatility. Uses default if None.
        volatility_percentile: 30-day percentile for regime detection.

    Returns:
        ScoredOpportunity or None if no actionable signals.
    """
    if not signals:
        return None

    # Compute consensus
    direction, consensus_pct, agreeing, total = compute_consensus(signals)
    if direction == "HOLD":
        return None

    # Calculate expected return from agreeing signals
    exp_return, ret_stddev = calculate_expected_return(signals, direction)

    # Use defaults for missing market data
    vol = volatility if volatility is not None else DEFAULTS["volatility"]
    vol_pct = volatility_percentile if volatility_percentile is not None else 0.5

    # Detect market regime
    regime = detect_regime(vol_pct)

    # Compute average confidence of agreeing signals
    agreeing_signals = [s for s in signals if s.direction == direction]
    avg_confidence = (
        sum(s.confidence for s in agreeing_signals) / len(agreeing_signals)
        if agreeing_signals
        else 0.0
    )

    # Score is computed once at creation (freshness locked at 0)
    score, breakdown = calculate_opportunity_score(
        confidence=avg_confidence,
        expected_return=exp_return,
        return_stddev=ret_stddev,
        consensus_pct=consensus_pct,
        volatility=vol,
        minutes_ago=0,  # Always fresh at creation — score is cached
        market_regime=regime,
    )

    tier = assign_tier(score)

    # Identify top strategy
    top_strategy = None
    best_confidence = -1.0
    for s in agreeing_signals:
        if s.confidence > best_confidence and s.strategy_name:
            best_confidence = s.confidence
            top_strategy = s.strategy_name

    return ScoredOpportunity(
        opportunity_id=str(uuid.uuid4()),
        symbol=symbol,
        direction=direction,
        opportunity_score=score,
        tier=tier,
        score_breakdown=breakdown,
        contributing_signals=signals,
        strategies_analyzed=total,
        strategies_agreeing=agreeing,
        top_strategy=top_strategy,
        market_regime=regime,
    )


def rank_opportunities(
    opportunities: list[ScoredOpportunity],
    min_score: float = 0.0,
    min_tier: Optional[str] = None,
    exclude_stale: bool = True,
) -> list[ScoredOpportunity]:
    """Rank and filter opportunities by composite score.

    Args:
        opportunities: List of scored opportunities to rank.
        min_score: Minimum score threshold (default 0 = all).
        min_tier: Minimum tier filter (e.g. "GOOD" means GOOD + HOT).
        exclude_stale: Whether to exclude stale (>60 min) opportunities.

    Returns:
        Sorted list of opportunities (highest score first).
    """
    tier_order = {"HOT": 4, "GOOD": 3, "NEUTRAL": 2, "LOW": 1}
    min_tier_value = tier_order.get(min_tier, 0) if min_tier else 0

    filtered = []
    for opp in opportunities:
        if opp.opportunity_score < min_score:
            continue
        if tier_order.get(opp.tier, 0) < min_tier_value:
            continue
        if exclude_stale and opp.is_stale:
            continue
        filtered.append(opp)

    return sorted(filtered, key=lambda o: o.opportunity_score, reverse=True)
