"""Sentiment-based trading signal generator.

Converts aggregated sentiment into actionable BUY/SELL/HOLD signals using:
1. Contrarian logic: extreme fear -> BUY, extreme greed -> SELL
2. Sentiment divergence: price vs sentiment disagreement
3. Sentiment momentum: acceleration / deceleration as a leading indicator
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from services.market_sentiment.aggregator import (
    AggregatedSentiment,
    SentimentSourceType,
    _clamp,
    sentiment_label,
)


# ---------------------------------------------------------------------------
# Signal data classes
# ---------------------------------------------------------------------------


@dataclass
class SentimentSignal:
    """A trading signal derived from sentiment analysis."""

    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 - 1.0
    reasoning: str
    sentiment_score: float
    sentiment_label: str
    signal_type: str  # contrarian, divergence, momentum
    timestamp: float = 0.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class DivergenceResult:
    """Price-vs-sentiment divergence detection result."""

    symbol: str
    divergence_type: str  # bullish_divergence, bearish_divergence, none
    price_change_pct: float
    sentiment_score: float
    strength: float  # 0.0 - 1.0
    description: str


@dataclass
class SentimentMomentum:
    """Tracks sentiment rate-of-change over a sliding window."""

    symbol: str
    current_score: float
    previous_score: float
    velocity: float  # first derivative (rate of change)
    acceleration: float  # second derivative (change in velocity)
    direction: str  # accelerating_bullish, decelerating_bullish, etc.


# ---------------------------------------------------------------------------
# Contrarian signal generation
# ---------------------------------------------------------------------------

# Thresholds for contrarian signals
EXTREME_FEAR_THRESHOLD = -0.6
FEAR_THRESHOLD = -0.3
GREED_THRESHOLD = 0.3
EXTREME_GREED_THRESHOLD = 0.6


def generate_contrarian_signal(
    sentiment: AggregatedSentiment,
) -> SentimentSignal:
    """Generate a contrarian trading signal from aggregated sentiment.

    Strategy:
    - Extreme fear (score <= -0.6): BUY with high confidence
    - Fear (score <= -0.3): BUY with moderate confidence
    - Extreme greed (score >= 0.6): SELL with high confidence
    - Greed (score >= 0.3): SELL with moderate confidence
    - Neutral: HOLD
    """
    score = sentiment.composite_score
    now = time.time()

    if score <= EXTREME_FEAR_THRESHOLD:
        conf = min(0.5 + abs(score + 0.6) * 1.25, 0.95)
        return SentimentSignal(
            symbol=sentiment.symbol,
            action="BUY",
            confidence=round(conf, 4),
            reasoning=(
                f"Extreme fear detected (score={score:.2f}). "
                "Contrarian buy signal — historically, extreme fear precedes recoveries."
            ),
            sentiment_score=score,
            sentiment_label=sentiment.label,
            signal_type="contrarian",
            timestamp=now,
        )

    if score <= FEAR_THRESHOLD:
        conf = min(0.3 + abs(score + 0.3) * 0.8, 0.7)
        return SentimentSignal(
            symbol=sentiment.symbol,
            action="BUY",
            confidence=round(conf, 4),
            reasoning=(
                f"Elevated fear (score={score:.2f}). "
                "Moderate contrarian buy — sentiment below average."
            ),
            sentiment_score=score,
            sentiment_label=sentiment.label,
            signal_type="contrarian",
            timestamp=now,
        )

    if score >= EXTREME_GREED_THRESHOLD:
        conf = min(0.5 + (score - 0.6) * 1.25, 0.95)
        return SentimentSignal(
            symbol=sentiment.symbol,
            action="SELL",
            confidence=round(conf, 4),
            reasoning=(
                f"Extreme greed detected (score={score:.2f}). "
                "Contrarian sell signal — extreme greed often precedes corrections."
            ),
            sentiment_score=score,
            sentiment_label=sentiment.label,
            signal_type="contrarian",
            timestamp=now,
        )

    if score >= GREED_THRESHOLD:
        conf = min(0.3 + (score - 0.3) * 0.8, 0.7)
        return SentimentSignal(
            symbol=sentiment.symbol,
            action="SELL",
            confidence=round(conf, 4),
            reasoning=(
                f"Elevated greed (score={score:.2f}). "
                "Moderate contrarian sell — sentiment above average."
            ),
            sentiment_score=score,
            sentiment_label=sentiment.label,
            signal_type="contrarian",
            timestamp=now,
        )

    return SentimentSignal(
        symbol=sentiment.symbol,
        action="HOLD",
        confidence=round(0.3 + abs(score) * 0.5, 4),
        reasoning=f"Neutral sentiment (score={score:.2f}). No contrarian signal.",
        sentiment_score=score,
        sentiment_label=sentiment.label,
        signal_type="contrarian",
        timestamp=now,
    )


# ---------------------------------------------------------------------------
# Divergence detection
# ---------------------------------------------------------------------------


def detect_divergence(
    symbol: str,
    sentiment_score: float,
    price_change_pct: float,
    threshold: float = 0.3,
) -> DivergenceResult:
    """Detect divergence between price movement and sentiment.

    Bearish divergence: price rising but sentiment falling (score negative).
    Bullish divergence: price falling but sentiment rising (score positive).

    Args:
        symbol: Trading symbol.
        sentiment_score: Current aggregated sentiment [-1, +1].
        price_change_pct: Recent price change as a percentage.
        threshold: Minimum absolute value required for both metrics.
    """
    if price_change_pct > threshold and sentiment_score < -threshold:
        strength = min((abs(price_change_pct) + abs(sentiment_score)) / 2.0, 1.0)
        return DivergenceResult(
            symbol=symbol,
            divergence_type="bearish_divergence",
            price_change_pct=round(price_change_pct, 4),
            sentiment_score=round(sentiment_score, 4),
            strength=round(strength, 4),
            description=(
                f"Price up {price_change_pct:.1f}% but sentiment negative "
                f"({sentiment_score:.2f}). Potential bearish reversal."
            ),
        )

    if price_change_pct < -threshold and sentiment_score > threshold:
        strength = min((abs(price_change_pct) + abs(sentiment_score)) / 2.0, 1.0)
        return DivergenceResult(
            symbol=symbol,
            divergence_type="bullish_divergence",
            price_change_pct=round(price_change_pct, 4),
            sentiment_score=round(sentiment_score, 4),
            strength=round(strength, 4),
            description=(
                f"Price down {price_change_pct:.1f}% but sentiment positive "
                f"({sentiment_score:.2f}). Potential bullish reversal."
            ),
        )

    return DivergenceResult(
        symbol=symbol,
        divergence_type="none",
        price_change_pct=round(price_change_pct, 4),
        sentiment_score=round(sentiment_score, 4),
        strength=0.0,
        description="No significant divergence detected.",
    )


def generate_divergence_signal(
    divergence: DivergenceResult,
) -> Optional[SentimentSignal]:
    """Convert a divergence result into a trading signal.

    Returns None if no divergence was found.
    """
    if divergence.divergence_type == "none":
        return None

    now = time.time()

    if divergence.divergence_type == "bullish_divergence":
        return SentimentSignal(
            symbol=divergence.symbol,
            action="BUY",
            confidence=round(divergence.strength * 0.8, 4),
            reasoning=divergence.description,
            sentiment_score=divergence.sentiment_score,
            sentiment_label=sentiment_label(divergence.sentiment_score),
            signal_type="divergence",
            timestamp=now,
            metadata={
                "divergence_type": divergence.divergence_type,
                "price_change_pct": divergence.price_change_pct,
            },
        )

    return SentimentSignal(
        symbol=divergence.symbol,
        action="SELL",
        confidence=round(divergence.strength * 0.8, 4),
        reasoning=divergence.description,
        sentiment_score=divergence.sentiment_score,
        sentiment_label=sentiment_label(divergence.sentiment_score),
        signal_type="divergence",
        timestamp=now,
        metadata={
            "divergence_type": divergence.divergence_type,
            "price_change_pct": divergence.price_change_pct,
        },
    )


# ---------------------------------------------------------------------------
# Sentiment momentum
# ---------------------------------------------------------------------------


class SentimentMomentumTracker:
    """Track sentiment velocity and acceleration over a sliding window.

    Maintains a fixed-size history of sentiment readings per symbol and
    computes first (velocity) and second (acceleration) derivatives.
    """

    def __init__(self, window_size: int = 10):
        self._window_size = window_size
        self._history: Dict[str, Deque[Tuple[float, float]]] = (
            {}
        )  # symbol -> deque of (timestamp, score)

    def record(
        self, symbol: str, score: float, timestamp: Optional[float] = None
    ) -> None:
        """Record a new sentiment reading."""
        ts = timestamp or time.time()
        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=self._window_size)
        self._history[symbol].append((ts, score))

    def compute_momentum(self, symbol: str) -> Optional[SentimentMomentum]:
        """Compute velocity and acceleration for a symbol.

        Requires at least 3 data points.
        """
        history = self._history.get(symbol)
        if not history or len(history) < 3:
            return None

        scores = [s for _, s in history]
        current = scores[-1]
        previous = scores[-2]

        # Velocity: average change over recent readings
        velocities = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
        velocity = sum(velocities) / len(velocities)

        # Acceleration: change in velocity
        if len(velocities) >= 2:
            accels = [
                velocities[i] - velocities[i - 1] for i in range(1, len(velocities))
            ]
            acceleration = sum(accels) / len(accels)
        else:
            acceleration = 0.0

        direction = _classify_momentum_direction(velocity, acceleration)

        return SentimentMomentum(
            symbol=symbol,
            current_score=round(current, 4),
            previous_score=round(previous, 4),
            velocity=round(velocity, 4),
            acceleration=round(acceleration, 4),
            direction=direction,
        )

    def get_history(self, symbol: str) -> List[Tuple[float, float]]:
        """Return the raw history for a symbol."""
        return list(self._history.get(symbol, []))


def _classify_momentum_direction(velocity: float, acceleration: float) -> str:
    """Classify momentum into a descriptive direction label."""
    if abs(velocity) < 0.02 and abs(acceleration) < 0.02:
        return "stable"

    if velocity > 0:
        if acceleration > 0.01:
            return "accelerating_bullish"
        if acceleration < -0.01:
            return "decelerating_bullish"
        return "steady_bullish"

    # velocity <= 0
    if acceleration < -0.01:
        return "accelerating_bearish"
    if acceleration > 0.01:
        return "decelerating_bearish"
    return "steady_bearish"


def generate_momentum_signal(
    momentum: SentimentMomentum,
) -> Optional[SentimentSignal]:
    """Generate a signal from sentiment momentum.

    Leading indicator: accelerating sentiment change often precedes price moves.
    """
    now = time.time()

    if momentum.direction == "accelerating_bullish" and momentum.velocity > 0.05:
        conf = min(0.4 + abs(momentum.velocity) + abs(momentum.acceleration), 0.85)
        return SentimentSignal(
            symbol=momentum.symbol,
            action="BUY",
            confidence=round(conf, 4),
            reasoning=(
                f"Sentiment accelerating bullish (velocity={momentum.velocity:.3f}, "
                f"accel={momentum.acceleration:.3f}). Leading bullish indicator."
            ),
            sentiment_score=momentum.current_score,
            sentiment_label=sentiment_label(momentum.current_score),
            signal_type="momentum",
            timestamp=now,
            metadata={
                "velocity": momentum.velocity,
                "acceleration": momentum.acceleration,
            },
        )

    if momentum.direction == "accelerating_bearish" and momentum.velocity < -0.05:
        conf = min(0.4 + abs(momentum.velocity) + abs(momentum.acceleration), 0.85)
        return SentimentSignal(
            symbol=momentum.symbol,
            action="SELL",
            confidence=round(conf, 4),
            reasoning=(
                f"Sentiment accelerating bearish (velocity={momentum.velocity:.3f}, "
                f"accel={momentum.acceleration:.3f}). Leading bearish indicator."
            ),
            sentiment_score=momentum.current_score,
            sentiment_label=sentiment_label(momentum.current_score),
            signal_type="momentum",
            timestamp=now,
            metadata={
                "velocity": momentum.velocity,
                "acceleration": momentum.acceleration,
            },
        )

    if momentum.direction == "decelerating_bullish" and momentum.current_score > 0.5:
        return SentimentSignal(
            symbol=momentum.symbol,
            action="SELL",
            confidence=round(min(0.3 + abs(momentum.acceleration), 0.6), 4),
            reasoning=(
                f"Bullish sentiment decelerating (score={momentum.current_score:.2f}, "
                f"accel={momentum.acceleration:.3f}). Potential top forming."
            ),
            sentiment_score=momentum.current_score,
            sentiment_label=sentiment_label(momentum.current_score),
            signal_type="momentum",
            timestamp=now,
            metadata={
                "velocity": momentum.velocity,
                "acceleration": momentum.acceleration,
            },
        )

    if momentum.direction == "decelerating_bearish" and momentum.current_score < -0.5:
        return SentimentSignal(
            symbol=momentum.symbol,
            action="BUY",
            confidence=round(min(0.3 + abs(momentum.acceleration), 0.6), 4),
            reasoning=(
                f"Bearish sentiment decelerating (score={momentum.current_score:.2f}, "
                f"accel={momentum.acceleration:.3f}). Potential bottom forming."
            ),
            sentiment_score=momentum.current_score,
            sentiment_label=sentiment_label(momentum.current_score),
            signal_type="momentum",
            timestamp=now,
            metadata={
                "velocity": momentum.velocity,
                "acceleration": momentum.acceleration,
            },
        )

    return None


# ---------------------------------------------------------------------------
# Composite signal from all methods
# ---------------------------------------------------------------------------


def generate_composite_signal(
    sentiment: AggregatedSentiment,
    price_change_pct: float,
    momentum_tracker: Optional[SentimentMomentumTracker] = None,
) -> SentimentSignal:
    """Generate a composite sentiment signal combining contrarian, divergence,
    and momentum sub-signals.

    The highest-confidence sub-signal is selected. If multiple agree on
    direction, confidence is boosted.
    """
    signals: List[SentimentSignal] = []

    # 1. Contrarian
    contrarian = generate_contrarian_signal(sentiment)
    signals.append(contrarian)

    # 2. Divergence
    div_result = detect_divergence(
        sentiment.symbol, sentiment.composite_score, price_change_pct
    )
    div_signal = generate_divergence_signal(div_result)
    if div_signal:
        signals.append(div_signal)

    # 3. Momentum
    if momentum_tracker:
        mom = momentum_tracker.compute_momentum(sentiment.symbol)
        if mom:
            mom_signal = generate_momentum_signal(mom)
            if mom_signal:
                signals.append(mom_signal)

    # Select the highest confidence non-HOLD signal, or the contrarian HOLD
    actionable = [s for s in signals if s.action != "HOLD"]
    if not actionable:
        return contrarian

    best = max(actionable, key=lambda s: s.confidence)

    # Boost confidence if multiple signals agree
    agreeing = [s for s in actionable if s.action == best.action]
    if len(agreeing) > 1:
        boost = 0.05 * (len(agreeing) - 1)
        best.confidence = round(min(best.confidence + boost, 0.95), 4)
        sources = ", ".join(s.signal_type for s in agreeing)
        best.reasoning += f" (confirmed by {sources})"

    return best
