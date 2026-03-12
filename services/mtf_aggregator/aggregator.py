"""
Multi-Timeframe Signal Aggregator.

Combines signals from different timeframes into a unified conviction score.
Higher timeframes receive more weight by default, and signal alignment across
timeframes boosts the overall conviction.
"""

from typing import Dict, List, Optional

from models import (
    AggregationResult,
    DEFAULT_TIMEFRAME_WEIGHTS,
    SignalDirection,
    Timeframe,
    TimeframeSignal,
)


def _direction_value(direction: SignalDirection) -> float:
    """Convert a signal direction to a numeric value."""
    if direction == SignalDirection.BUY:
        return 1.0
    elif direction == SignalDirection.SELL:
        return -1.0
    return 0.0


class MultiTimeframeAggregator:
    """Aggregates signals across multiple timeframes into a conviction score."""

    def __init__(
        self,
        timeframe_weights: Optional[Dict[Timeframe, float]] = None,
        alignment_bonus: float = 0.20,
    ):
        self.timeframe_weights = dict(timeframe_weights or DEFAULT_TIMEFRAME_WEIGHTS)
        self.alignment_bonus = alignment_bonus

    def aggregate(self, signals: List[TimeframeSignal]) -> AggregationResult:
        """Aggregate signals from multiple timeframes into a single conviction score.

        Args:
            signals: List of signals, each tagged with a timeframe.

        Returns:
            AggregationResult with conviction score in [-1, +1] and alignment info.
        """
        if not signals:
            return AggregationResult(
                symbol="",
                conviction_score=0.0,
                alignment_score=0.0,
                direction=SignalDirection.HOLD,
                timeframe_count=0,
            )

        symbol = signals[0].symbol

        # Group signals by timeframe; if multiple signals per timeframe,
        # use the one with the highest confidence.
        best_by_tf: Dict[Timeframe, TimeframeSignal] = {}
        for sig in signals:
            tf = sig.timeframe
            if tf not in best_by_tf or sig.confidence > best_by_tf[tf].confidence:
                best_by_tf[tf] = sig

        # Compute weighted conviction
        active_tfs = list(best_by_tf.keys())
        total_weight = sum(self.timeframe_weights.get(tf, 0.0) for tf in active_tfs)

        if total_weight == 0.0:
            return AggregationResult(
                symbol=symbol,
                conviction_score=0.0,
                alignment_score=0.0,
                direction=SignalDirection.HOLD,
                timeframe_count=len(active_tfs),
                contributing_signals=signals,
            )

        # Normalize weights to sum to 1.0 among active timeframes
        normalized_weights = {
            tf: self.timeframe_weights.get(tf, 0.0) / total_weight for tf in active_tfs
        }

        # Raw weighted score: each signal contributes direction * confidence * weight
        raw_score = 0.0
        timeframe_details: Dict[str, Dict] = {}
        for tf in active_tfs:
            sig = best_by_tf[tf]
            direction_val = _direction_value(sig.direction)
            contribution = direction_val * sig.confidence * normalized_weights[tf]
            raw_score += contribution
            timeframe_details[tf.value] = {
                "direction": sig.direction.value,
                "confidence": sig.confidence,
                "weight": normalized_weights[tf],
                "contribution": contribution,
            }

        # Alignment: fraction of non-HOLD signals that agree on direction
        directional_signals = [
            s for s in best_by_tf.values() if s.direction != SignalDirection.HOLD
        ]
        if len(directional_signals) <= 1:
            alignment_score = 1.0 if directional_signals else 0.0
        else:
            dominant_direction = (
                SignalDirection.BUY if raw_score >= 0 else SignalDirection.SELL
            )
            agreeing = sum(
                1 for s in directional_signals if s.direction == dominant_direction
            )
            alignment_score = agreeing / len(directional_signals)

        # Apply alignment bonus: full bonus when all timeframes agree
        bonus = self.alignment_bonus * alignment_score
        if raw_score >= 0:
            conviction = min(raw_score + bonus * raw_score, 1.0)
        else:
            conviction = max(raw_score + bonus * raw_score, -1.0)

        # Determine overall direction
        if conviction > 0.0:
            direction = SignalDirection.BUY
        elif conviction < 0.0:
            direction = SignalDirection.SELL
        else:
            direction = SignalDirection.HOLD

        return AggregationResult(
            symbol=symbol,
            conviction_score=round(conviction, 6),
            alignment_score=round(alignment_score, 6),
            direction=direction,
            timeframe_count=len(active_tfs),
            timeframe_details=timeframe_details,
            contributing_signals=signals,
        )
