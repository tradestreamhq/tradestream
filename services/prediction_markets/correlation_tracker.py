"""Correlation tracker for prediction market signals and asset prices.

Tracks how well prediction market probability changes correlate with
subsequent asset price movements, enabling signal quality assessment
and continuous improvement.
"""

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from absl import logging


@dataclass
class CorrelationRecord:
    """A single observation for correlation tracking."""

    event_id: str
    asset_symbol: str
    probability_change: float  # Change in prediction market probability
    price_change_pct: float  # Subsequent asset price change (%)
    lag_hours: float  # Time between prediction and price observation
    timestamp_ms: int


@dataclass
class CorrelationResult:
    """Computed correlation between prediction market and asset price."""

    event_category: str
    asset_symbol: str
    correlation: float  # Pearson correlation coefficient
    sample_count: int
    avg_lag_hours: float
    signal_accuracy: float  # % of signals that predicted direction correctly
    computed_at_ms: int


class CorrelationTracker:
    """Tracks correlation between prediction market signals and asset prices.

    Maintains a rolling window of observations to compute correlation
    coefficients and signal accuracy metrics.
    """

    def __init__(
        self, max_observations: int = 1000, observation_window_hours: float = 48.0
    ):
        self.max_observations = max_observations
        self.observation_window_hours = observation_window_hours
        # Keyed by (category, asset_symbol)
        self._observations: Dict[Tuple[str, str], List[CorrelationRecord]] = {}

    def record_observation(
        self,
        event_id: str,
        category: str,
        asset_symbol: str,
        probability_change: float,
        price_change_pct: float,
        lag_hours: float,
    ):
        """Record a paired observation of prediction and price movement.

        Args:
            event_id: The prediction market event ID.
            category: Event category (monetary_policy, regulatory, etc.).
            asset_symbol: The asset symbol (e.g. "BTC/USD").
            probability_change: Change in prediction probability.
            price_change_pct: Asset price change in percent.
            lag_hours: Hours between prediction signal and price observation.
        """
        key = (category, asset_symbol)
        if key not in self._observations:
            self._observations[key] = []

        self._observations[key].append(
            CorrelationRecord(
                event_id=event_id,
                asset_symbol=asset_symbol,
                probability_change=probability_change,
                price_change_pct=price_change_pct,
                lag_hours=lag_hours,
                timestamp_ms=int(time.time() * 1000),
            )
        )

        # Trim to max observations
        if len(self._observations[key]) > self.max_observations:
            self._observations[key] = self._observations[key][-self.max_observations :]

    def compute_correlation(
        self, category: str, asset_symbol: str
    ) -> Optional[CorrelationResult]:
        """Compute Pearson correlation for a category-asset pair.

        Args:
            category: Event category.
            asset_symbol: Asset symbol.

        Returns:
            CorrelationResult or None if insufficient data.
        """
        key = (category, asset_symbol)
        records = self._observations.get(key, [])

        if len(records) < 5:
            return None

        prob_changes = [r.probability_change for r in records]
        price_changes = [r.price_change_pct for r in records]

        correlation = self._pearson_correlation(prob_changes, price_changes)
        accuracy = self._compute_accuracy(prob_changes, price_changes)
        avg_lag = sum(r.lag_hours for r in records) / len(records)

        return CorrelationResult(
            event_category=category,
            asset_symbol=asset_symbol,
            correlation=correlation,
            sample_count=len(records),
            avg_lag_hours=avg_lag,
            signal_accuracy=accuracy,
            computed_at_ms=int(time.time() * 1000),
        )

    def get_all_correlations(self) -> List[CorrelationResult]:
        """Compute correlations for all tracked category-asset pairs."""
        results = []
        for category, asset_symbol in self._observations:
            result = self.compute_correlation(category, asset_symbol)
            if result is not None:
                results.append(result)
        return sorted(results, key=lambda r: abs(r.correlation), reverse=True)

    def get_signal_quality_score(self, category: str, asset_symbol: str) -> float:
        """Get a 0-1 quality score for signals of this type.

        Combines correlation strength and directional accuracy.
        Returns 0.5 (neutral) if insufficient data.
        """
        result = self.compute_correlation(category, asset_symbol)
        if result is None:
            return 0.5

        # Weight: 60% accuracy, 40% absolute correlation
        score = 0.6 * result.signal_accuracy + 0.4 * abs(result.correlation)
        return max(0.0, min(1.0, score))

    @staticmethod
    def _pearson_correlation(x: List[float], y: List[float]) -> float:
        """Compute Pearson correlation coefficient."""
        n = len(x)
        if n < 2:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
        denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

        if denom_x == 0 or denom_y == 0:
            return 0.0

        return numerator / (denom_x * denom_y)

    @staticmethod
    def _compute_accuracy(
        prob_changes: List[float], price_changes: List[float]
    ) -> float:
        """Compute directional accuracy: % of times probability change
        predicted the direction of price change."""
        correct = 0
        total = 0
        for pc, ac in zip(prob_changes, price_changes):
            if pc == 0 or ac == 0:
                continue
            if (pc > 0 and ac > 0) or (pc < 0 and ac < 0):
                correct += 1
            total += 1

        if total == 0:
            return 0.5  # No data -> neutral
        return correct / total
