"""Volatility regime classifier.

Monitors realized volatility to categorize the current market environment
as low, medium, or high volatility.
"""

import math
from datetime import datetime, timezone
from typing import Optional

from services.volatility_regime.models import (
    REGIME_THRESHOLDS,
    RegimeClassification,
    RegimeTransition,
    VolatilityMetrics,
    VolatilityRegime,
)

# Annualized factor: sqrt(trading days per year)
ANNUALIZATION_FACTOR = math.sqrt(365)


def classify_regime(annualized_vol: float) -> VolatilityRegime:
    """Classify a volatility value into a regime.

    Args:
        annualized_vol: Annualized volatility as a percentage.

    Returns:
        The volatility regime (low, medium, or high).
    """
    if annualized_vol < REGIME_THRESHOLDS["low_upper"]:
        return VolatilityRegime.LOW
    elif annualized_vol >= REGIME_THRESHOLDS["high_lower"]:
        return VolatilityRegime.HIGH
    else:
        return VolatilityRegime.MEDIUM


def compute_realized_volatility(
    daily_closes: list[float], window: int
) -> Optional[float]:
    """Compute annualized realized volatility from daily close prices.

    Args:
        daily_closes: List of daily closing prices, oldest first.
        window: Rolling window size in days.

    Returns:
        Annualized volatility as a percentage, or None if insufficient data.
    """
    if len(daily_closes) < window + 1:
        return None

    # Use the most recent `window + 1` prices to get `window` returns
    prices = daily_closes[-(window + 1) :]
    log_returns = [
        math.log(prices[i] / prices[i - 1])
        for i in range(1, len(prices))
        if prices[i - 1] > 0 and prices[i] > 0
    ]

    if len(log_returns) < 2:
        return None

    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    daily_vol = math.sqrt(variance)
    annualized = daily_vol * ANNUALIZATION_FACTOR * 100
    return round(annualized, 2)


class VolatilityRegimeClassifier:
    """Classifies market volatility into regimes and tracks transitions."""

    def __init__(self, max_transitions: int = 20):
        self._transitions: dict[str, list[RegimeTransition]] = {}
        self._current_regimes: dict[str, VolatilityRegime] = {}
        self._max_transitions = max_transitions

    def classify(self, symbol: str, daily_closes: list[float]) -> RegimeClassification:
        """Classify the current volatility regime for a symbol.

        Args:
            symbol: The instrument symbol.
            daily_closes: Daily closing prices, oldest first. Needs at least 61 values
                for 60-day volatility.

        Returns:
            RegimeClassification with current regime and metrics.
        """
        vol_20d = compute_realized_volatility(daily_closes, 20)
        vol_60d = compute_realized_volatility(daily_closes, 60)

        # Use 20-day vol as primary, fall back to 60-day
        primary_vol = vol_20d if vol_20d is not None else vol_60d
        if primary_vol is None:
            regime = VolatilityRegime.MEDIUM  # default when data is insufficient
        else:
            regime = classify_regime(primary_vol)

        # Track transitions
        previous = self._current_regimes.get(symbol)
        if previous != regime:
            transition = RegimeTransition(
                previous_regime=previous,
                current_regime=regime,
                transitioned_at=datetime.now(timezone.utc).isoformat(),
            )
            if symbol not in self._transitions:
                self._transitions[symbol] = []
            self._transitions[symbol].insert(0, transition)
            self._transitions[symbol] = self._transitions[symbol][
                : self._max_transitions
            ]
            self._current_regimes[symbol] = regime

        return RegimeClassification(
            symbol=symbol,
            regime=regime,
            volatility=VolatilityMetrics(
                realized_vol_20d=vol_20d,
                realized_vol_60d=vol_60d,
            ),
            recent_transitions=self._transitions.get(symbol, []),
        )
