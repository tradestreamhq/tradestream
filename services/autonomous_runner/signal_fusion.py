"""Signal fusion engine: combines signals from multiple sources with confidence-weighted voting.

Merges strategy signals, sentiment data, prediction market probabilities,
and market regime detection into a single actionable signal.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class SourceSignal:
    """A signal from a single source."""

    source: str  # e.g. "strategy_consensus", "sentiment", "prediction_market", "regime"
    action: SignalAction
    confidence: float  # 0.0 - 1.0
    weight: float = 1.0  # source weighting factor
    metadata: dict = field(default_factory=dict)


@dataclass
class FusedSignal:
    """Result of fusing multiple source signals."""

    symbol: str
    action: SignalAction
    confidence: float
    source_signals: list  # list of SourceSignal
    agreement_ratio: float  # fraction of sources agreeing with action
    conflict_resolution_applied: str = ""
    reasoning: str = ""


# Default source weights (sum to 1.0)
DEFAULT_SOURCE_WEIGHTS = {
    "strategy_consensus": 0.40,
    "sentiment": 0.15,
    "prediction_market": 0.20,
    "regime_detection": 0.15,
    "learning_engine": 0.10,
}


class ConflictResolutionStrategy(str, Enum):
    WEIGHTED_MAJORITY = "weighted_majority"
    HIGHEST_CONFIDENCE = "highest_confidence"
    CONSERVATIVE = "conservative"


def calculate_confidence(strategies: list) -> float:
    """Calculate confidence based on strategy consensus and individual scores.

    Spec-defined tiers (for 5 strategies):
    - 5/5 agree: 0.90-0.95 (modified by avg strategy score)
    - 4/5 agree: 0.75-0.85
    - 3/5 agree: 0.60-0.70
    - 2/5 agree: 0.45-0.55
    - 1/5 agree: 0.30-0.40

    Formula: confidence = base * (0.8 + 0.2 * avg_score)
    """
    if not strategies:
        return 0.30

    total = len(strategies)
    bullish = sum(1 for s in strategies if s.action == SignalAction.BUY)
    bearish = sum(1 for s in strategies if s.action == SignalAction.SELL)
    neutral = total - bullish - bearish

    max_agreement = max(bullish, bearish, neutral)
    consensus_ratio = max_agreement / total if total > 0 else 0

    avg_score = sum(s.confidence for s in strategies) / total if total > 0 else 0

    # Base confidence from consensus ratio (spec-defined tiers)
    if consensus_ratio >= 1.0:
        base = 0.90
    elif consensus_ratio >= 0.8:
        base = 0.85
    elif consensus_ratio >= 0.6:
        base = 0.75
    elif consensus_ratio >= 0.4:
        base = 0.55
    else:
        base = 0.40

    # Adjust by average strategy score per spec formula
    confidence = base * (0.8 + 0.2 * avg_score)
    return min(0.95, max(0.30, confidence))


def fuse_signals(
    symbol: str,
    source_signals: list,
    source_weights: Optional[dict] = None,
    conflict_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.WEIGHTED_MAJORITY,
) -> FusedSignal:
    """Fuse signals from multiple sources into a single actionable signal.

    Args:
        symbol: Trading symbol.
        source_signals: List of SourceSignal from various sources.
        source_weights: Override weights per source name.
        conflict_strategy: How to resolve disagreements.

    Returns:
        FusedSignal with the final action and confidence.
    """
    if not source_signals:
        return FusedSignal(
            symbol=symbol,
            action=SignalAction.HOLD,
            confidence=0.30,
            source_signals=[],
            agreement_ratio=0.0,
            reasoning="No source signals available.",
        )

    weights = source_weights or DEFAULT_SOURCE_WEIGHTS

    # Apply source weights
    for sig in source_signals:
        sig.weight = weights.get(sig.source, 0.10)

    # Weighted vote tally
    vote_scores = {
        SignalAction.BUY: 0.0,
        SignalAction.SELL: 0.0,
        SignalAction.HOLD: 0.0,
    }
    total_weight = 0.0

    for sig in source_signals:
        weighted_vote = sig.weight * sig.confidence
        vote_scores[sig.action] += weighted_vote
        total_weight += sig.weight

    # Normalize
    if total_weight > 0:
        for action in vote_scores:
            vote_scores[action] /= total_weight

    resolution_applied = ""

    if conflict_strategy == ConflictResolutionStrategy.WEIGHTED_MAJORITY:
        action, reasoning = _resolve_weighted_majority(vote_scores, source_signals)
        resolution_applied = "weighted_majority"

    elif conflict_strategy == ConflictResolutionStrategy.HIGHEST_CONFIDENCE:
        action, reasoning = _resolve_highest_confidence(source_signals)
        resolution_applied = "highest_confidence"

    elif conflict_strategy == ConflictResolutionStrategy.CONSERVATIVE:
        action, reasoning = _resolve_conservative(vote_scores, source_signals)
        resolution_applied = "conservative"

    else:
        action, reasoning = _resolve_weighted_majority(vote_scores, source_signals)
        resolution_applied = "weighted_majority"

    # Calculate agreement ratio
    agreeing = sum(1 for s in source_signals if s.action == action)
    agreement_ratio = agreeing / len(source_signals)

    # Calculate fused confidence
    confidence = _calculate_fused_confidence(
        action, source_signals, agreement_ratio, vote_scores
    )

    return FusedSignal(
        symbol=symbol,
        action=action,
        confidence=confidence,
        source_signals=source_signals,
        agreement_ratio=agreement_ratio,
        conflict_resolution_applied=resolution_applied,
        reasoning=reasoning,
    )


def _resolve_weighted_majority(vote_scores: dict, source_signals: list) -> tuple:
    """Weighted majority wins. If tied, prefer HOLD."""
    sorted_actions = sorted(vote_scores.items(), key=lambda x: x[1], reverse=True)
    top = sorted_actions[0]
    runner_up = sorted_actions[1] if len(sorted_actions) > 1 else (None, 0)

    # If top two are very close (within 10%), it's a conflict
    if runner_up[1] > 0 and (top[1] - runner_up[1]) < 0.10:
        return (
            SignalAction.HOLD,
            f"Near-tie between {top[0].value} ({top[1]:.2f}) and "
            f"{runner_up[0].value} ({runner_up[1]:.2f}), defaulting to HOLD.",
        )

    return (
        top[0],
        f"Weighted majority: {top[0].value} scored {top[1]:.2f} vs "
        f"{runner_up[0].value} ({runner_up[1]:.2f}).",
    )


def _resolve_highest_confidence(source_signals: list) -> tuple:
    """The single source with highest confidence wins."""
    best = max(source_signals, key=lambda s: s.confidence)
    return (
        best.action,
        f"Highest confidence source: {best.source} at {best.confidence:.2f} -> {best.action.value}.",
    )


def _resolve_conservative(vote_scores: dict, source_signals: list) -> tuple:
    """Conservative approach: only act on strong consensus, else HOLD."""
    sorted_actions = sorted(vote_scores.items(), key=lambda x: x[1], reverse=True)
    top = sorted_actions[0]

    # Require >60% weighted vote share to act
    if top[1] >= 0.60 and top[0] != SignalAction.HOLD:
        return (
            top[0],
            f"Conservative: strong consensus for {top[0].value} ({top[1]:.2f}).",
        )

    return (
        SignalAction.HOLD,
        f"Conservative: no strong consensus (top={top[0].value} at {top[1]:.2f}), holding.",
    )


def _calculate_fused_confidence(
    action: SignalAction,
    source_signals: list,
    agreement_ratio: float,
    vote_scores: dict,
) -> float:
    """Calculate final confidence score for fused signal."""
    # Base: weighted vote score for the winning action
    base = vote_scores.get(action, 0.0)

    # Boost for high agreement
    agreement_bonus = 0.0
    if agreement_ratio >= 0.8:
        agreement_bonus = 0.10
    elif agreement_ratio >= 0.6:
        agreement_bonus = 0.05

    # Average confidence of agreeing sources
    agreeing_confidences = [s.confidence for s in source_signals if s.action == action]
    avg_agree_conf = (
        sum(agreeing_confidences) / len(agreeing_confidences)
        if agreeing_confidences
        else 0.30
    )

    confidence = (base * 0.5 + avg_agree_conf * 0.5) + agreement_bonus
    return min(0.95, max(0.30, confidence))
