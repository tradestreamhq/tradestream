"""
Signal Aggregator and Consensus Engine.

Combines signals from multiple strategies for the same trading pair
within a configurable time window, producing weighted consensus signals.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass
class StrategyWeight:
    """Weight configuration for a strategy based on its performance."""

    strategy_id: str
    spec_id: str
    strategy_name: str
    win_rate: float = 0.5
    sharpe_ratio: float = 0.0
    weight: float = 1.0

    def compute_weight(self) -> float:
        """Compute composite weight from win rate and Sharpe ratio.

        Weight = 0.4 * normalized_win_rate + 0.6 * normalized_sharpe
        Both components are clamped to [0, 1] range.
        """
        wr_component = max(0.0, min(1.0, self.win_rate))
        sharpe_component = max(0.0, min(1.0, self.sharpe_ratio / 3.0))
        self.weight = 0.4 * wr_component + 0.6 * sharpe_component
        return self.weight


@dataclass
class Signal:
    """A signal from a single strategy."""

    strategy_id: str
    spec_id: str
    instrument: str
    signal_type: str  # BUY, SELL, HOLD
    strength: float  # 0.0 - 1.0
    price: float
    timestamp: datetime


@dataclass
class ConsensusSignal:
    """Aggregated consensus signal from multiple strategies."""

    id: str = field(default_factory=lambda: str(uuid4()))
    instrument: str = ""
    direction: Direction = Direction.NEUTRAL
    confidence: float = 0.0
    contributing_signals: int = 0
    agreeing_signals: int = 0
    dissenting_signals: int = 0
    weighted_score: float = 0.0
    avg_price: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    signal_details: List[Dict] = field(default_factory=list)

    def agreement_ratio(self) -> float:
        if self.contributing_signals == 0:
            return 0.0
        return self.agreeing_signals / self.contributing_signals


@dataclass
class AggregationConfig:
    """Configuration for the aggregation engine."""

    window_seconds: int = 300  # 5 minutes
    min_strategies: int = 2
    confidence_threshold: float = 0.5


class SignalAggregator:
    """Aggregates signals from multiple strategies into consensus signals."""

    def __init__(self, config: Optional[AggregationConfig] = None):
        self.config = config or AggregationConfig()

    def aggregate(
        self,
        signals: List[Signal],
        weights: Dict[str, StrategyWeight],
    ) -> Optional[ConsensusSignal]:
        """Aggregate signals into a consensus signal.

        Args:
            signals: List of signals from different strategies for the same pair.
            weights: Map of strategy_id -> StrategyWeight.

        Returns:
            ConsensusSignal if enough strategies contributed, None otherwise.
        """
        if len(signals) < self.config.min_strategies:
            return None

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.config.window_seconds)

        # Filter signals within the time window
        window_signals = [s for s in signals if s.timestamp >= window_start]
        if len(window_signals) < self.config.min_strategies:
            return None

        return self._compute_consensus(window_signals, weights, window_start, now)

    def _compute_consensus(
        self,
        signals: List[Signal],
        weights: Dict[str, StrategyWeight],
        window_start: datetime,
        window_end: datetime,
    ) -> ConsensusSignal:
        """Compute weighted consensus from filtered signals."""
        long_score = 0.0
        short_score = 0.0
        neutral_score = 0.0
        total_weight = 0.0
        price_sum = 0.0
        price_weight_sum = 0.0

        signal_details = []

        for signal in signals:
            sw = weights.get(signal.strategy_id)
            w = sw.weight if sw else 1.0
            effective_weight = w * signal.strength

            if signal.signal_type == "BUY":
                long_score += effective_weight
            elif signal.signal_type == "SELL":
                short_score += effective_weight
            else:
                neutral_score += effective_weight

            total_weight += w
            price_sum += signal.price * w
            price_weight_sum += w

            signal_details.append(
                {
                    "strategy_id": signal.strategy_id,
                    "signal_type": signal.signal_type,
                    "strength": signal.strength,
                    "weight": w,
                    "effective_weight": effective_weight,
                }
            )

        # Determine direction
        scores = {
            Direction.LONG: long_score,
            Direction.SHORT: short_score,
            Direction.NEUTRAL: neutral_score,
        }
        direction = max(scores, key=scores.get)
        winning_score = scores[direction]

        # Confidence = winning_score / total possible score
        if total_weight > 0:
            confidence = winning_score / total_weight
        else:
            confidence = 0.0

        # Count agreeing/dissenting
        direction_to_type = {
            Direction.LONG: "BUY",
            Direction.SHORT: "SELL",
            Direction.NEUTRAL: "HOLD",
        }
        winning_type = direction_to_type[direction]
        agreeing = sum(1 for s in signals if s.signal_type == winning_type)
        dissenting = len(signals) - agreeing

        avg_price = price_sum / price_weight_sum if price_weight_sum > 0 else 0.0

        return ConsensusSignal(
            instrument=signals[0].instrument,
            direction=direction,
            confidence=round(confidence, 4),
            contributing_signals=len(signals),
            agreeing_signals=agreeing,
            dissenting_signals=dissenting,
            weighted_score=round(winning_score, 4),
            avg_price=round(avg_price, 2),
            window_start=window_start,
            window_end=window_end,
            signal_details=signal_details,
        )

    def compute_agreement_matrix(
        self,
        signals_by_pair: Dict[str, List[Signal]],
    ) -> Dict[str, Dict[str, float]]:
        """Compute pairwise agreement ratios between strategies.

        Returns a matrix where matrix[strategy_a][strategy_b] = agreement_ratio.
        Agreement ratio = fraction of instruments where both strategies agree on direction.
        """
        # Collect all strategy IDs
        all_strategies = set()
        for signals in signals_by_pair.values():
            for s in signals:
                all_strategies.add(s.strategy_id)

        strategy_list = sorted(all_strategies)
        matrix: Dict[str, Dict[str, float]] = {}

        for sa in strategy_list:
            matrix[sa] = {}
            for sb in strategy_list:
                if sa == sb:
                    matrix[sa][sb] = 1.0
                    continue
                agreements = 0
                comparisons = 0
                for _pair, signals in signals_by_pair.items():
                    sig_a = next((s for s in signals if s.strategy_id == sa), None)
                    sig_b = next((s for s in signals if s.strategy_id == sb), None)
                    if sig_a and sig_b:
                        comparisons += 1
                        if sig_a.signal_type == sig_b.signal_type:
                            agreements += 1
                if comparisons > 0:
                    matrix[sa][sb] = round(agreements / comparisons, 4)
                else:
                    matrix[sa][sb] = 0.0

        return matrix
