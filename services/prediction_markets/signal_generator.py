"""Prediction market signal generator.

Converts prediction market probability data into actionable trading signals.
Monitors probability thresholds, spikes, and insider activity to emit signals
for crypto assets correlated with prediction market events.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from absl import logging


class SignalType(Enum):
    """Types of prediction market signals."""
    PROBABILITY_THRESHOLD = "probability_threshold"
    PROBABILITY_SPIKE = "probability_spike"
    INSIDER_ACTIVITY = "insider_activity"
    VOLUME_ANOMALY = "volume_anomaly"
    CROSS_MARKET_DIVERGENCE = "cross_market_divergence"


# Category-to-asset mapping: which crypto assets are affected by which categories
CATEGORY_ASSET_MAP = {
    "monetary_policy": ["BTC/USD", "ETH/USD", "SOL/USD"],
    "regulatory": ["BTC/USD", "ETH/USD", "SOL/USD"],
    "crypto_specific": ["BTC/USD", "ETH/USD", "SOL/USD"],
    "political": ["BTC/USD", "ETH/USD"],
    "economic": ["BTC/USD", "ETH/USD"],
    "btc_etf": ["BTC/USD"],
    "eth_etf": ["ETH/USD"],
}


@dataclass(frozen=True)
class PredictionSignal:
    """A trading signal derived from prediction market data."""
    signal_id: str
    signal_type: SignalType
    source_event_id: str
    category: str
    probability: float
    probability_change: float
    affected_asset: str
    signal_strength: float  # 0.0 - 1.0
    reasoning: str
    timestamp_ms: int


@dataclass
class ThresholdConfig:
    """Configuration for probability threshold signals."""
    bullish_threshold: float = 0.70
    bearish_threshold: float = 0.30
    spike_threshold: float = 0.10  # 10% change in probability
    volume_anomaly_multiplier: float = 3.0  # 3x avg volume


class PredictionMarketSignalGenerator:
    """Generates trading signals from prediction market events."""

    def __init__(self, config: ThresholdConfig = None,
                 target_symbols: list = None):
        self.config = config or ThresholdConfig()
        self.target_symbols = target_symbols or ["BTC/USD", "ETH/USD", "SOL/USD"]

    def generate_signals(self, events: list,
                         insider_alerts: list = None) -> List[PredictionSignal]:
        """Generate signals from prediction market data.

        Args:
            events: List of prediction market event dicts with at minimum:
                - event_id, category, probability, previous_probability,
                  volume, question
            insider_alerts: Optional list of insider alert dicts.

        Returns:
            List of PredictionSignal objects.
        """
        signals = []

        for event in events:
            signals.extend(self._check_threshold(event))
            signals.extend(self._check_spike(event))
            signals.extend(self._check_volume_anomaly(event))

        if insider_alerts:
            signals.extend(self._process_insider_alerts(insider_alerts))

        return signals

    def _check_threshold(self, event: dict) -> List[PredictionSignal]:
        """Check if probability crosses bullish/bearish thresholds."""
        signals = []
        prob = event.get("probability", 0)
        prev = event.get("previous_probability", 0)
        category = event.get("category", "")
        affected_assets = self._get_affected_assets(category)

        if not affected_assets:
            return signals

        # Bullish threshold crossing (probability went above threshold)
        if prob >= self.config.bullish_threshold and prev < self.config.bullish_threshold:
            for asset in affected_assets:
                if asset not in self.target_symbols:
                    continue
                strength = min(1.0, (prob - self.config.bullish_threshold) * 5 + 0.5)
                signals.append(PredictionSignal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.PROBABILITY_THRESHOLD,
                    source_event_id=event.get("event_id", ""),
                    category=category,
                    probability=prob,
                    probability_change=prob - prev,
                    affected_asset=asset,
                    signal_strength=strength,
                    reasoning=(
                        f"Bullish: '{event.get('question', '')}' probability "
                        f"crossed {self.config.bullish_threshold:.0%} "
                        f"(now {prob:.0%}, was {prev:.0%})"
                    ),
                    timestamp_ms=int(time.time() * 1000),
                ))

        # Bearish threshold crossing
        if prob <= self.config.bearish_threshold and prev > self.config.bearish_threshold:
            for asset in affected_assets:
                if asset not in self.target_symbols:
                    continue
                strength = min(1.0, (self.config.bearish_threshold - prob) * 5 + 0.5)
                signals.append(PredictionSignal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.PROBABILITY_THRESHOLD,
                    source_event_id=event.get("event_id", ""),
                    category=category,
                    probability=prob,
                    probability_change=prob - prev,
                    affected_asset=asset,
                    signal_strength=strength,
                    reasoning=(
                        f"Bearish: '{event.get('question', '')}' probability "
                        f"dropped below {self.config.bearish_threshold:.0%} "
                        f"(now {prob:.0%}, was {prev:.0%})"
                    ),
                    timestamp_ms=int(time.time() * 1000),
                ))

        return signals

    def _check_spike(self, event: dict) -> List[PredictionSignal]:
        """Check for rapid probability changes."""
        signals = []
        prob = event.get("probability", 0)
        prev = event.get("previous_probability", 0)
        change = abs(prob - prev)

        if change < self.config.spike_threshold:
            return signals

        category = event.get("category", "")
        affected_assets = self._get_affected_assets(category)
        direction = "up" if prob > prev else "down"

        for asset in affected_assets:
            if asset not in self.target_symbols:
                continue
            strength = min(1.0, change / self.config.spike_threshold * 0.5)
            signals.append(PredictionSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.PROBABILITY_SPIKE,
                source_event_id=event.get("event_id", ""),
                category=category,
                probability=prob,
                probability_change=prob - prev,
                affected_asset=asset,
                signal_strength=strength,
                reasoning=(
                    f"Spike {direction}: '{event.get('question', '')}' "
                    f"moved {change:.0%} "
                    f"({prev:.0%} -> {prob:.0%})"
                ),
                timestamp_ms=int(time.time() * 1000),
            ))

        return signals

    def _check_volume_anomaly(self, event: dict) -> List[PredictionSignal]:
        """Check for unusual volume in prediction markets."""
        signals = []
        volume = event.get("volume", 0)
        avg_volume = event.get("avg_volume", 0)

        if avg_volume <= 0 or volume <= 0:
            return signals

        volume_ratio = volume / avg_volume
        if volume_ratio < self.config.volume_anomaly_multiplier:
            return signals

        category = event.get("category", "")
        affected_assets = self._get_affected_assets(category)

        for asset in affected_assets:
            if asset not in self.target_symbols:
                continue
            strength = min(1.0, volume_ratio / (self.config.volume_anomaly_multiplier * 2))
            signals.append(PredictionSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.VOLUME_ANOMALY,
                source_event_id=event.get("event_id", ""),
                category=category,
                probability=event.get("probability", 0),
                probability_change=0,
                affected_asset=asset,
                signal_strength=strength,
                reasoning=(
                    f"Volume anomaly: '{event.get('question', '')}' "
                    f"volume {volume_ratio:.1f}x average"
                ),
                timestamp_ms=int(time.time() * 1000),
            ))

        return signals

    def _process_insider_alerts(self, alerts: list) -> List[PredictionSignal]:
        """Convert insider activity alerts to trading signals."""
        signals = []

        for alert in alerts:
            confidence = alert.get("confidence", "LOW")
            if confidence not in ("HIGH", "CRITICAL"):
                continue

            strength = 0.8 if confidence == "HIGH" else 1.0
            # Insider alerts on prediction markets generally affect all major crypto
            for asset in self.target_symbols:
                signals.append(PredictionSignal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.INSIDER_ACTIVITY,
                    source_event_id=alert.get("market_id", ""),
                    category="insider",
                    probability=alert.get("price", 0),
                    probability_change=0,
                    affected_asset=asset,
                    signal_strength=strength,
                    reasoning=(
                        f"Insider activity ({confidence}): "
                        f"Wallet {alert.get('wallet_address', 'unknown')[:10]}... "
                        f"{alert.get('side', 'BUY')} ${alert.get('position_size', 0):,.0f} "
                        f"on '{alert.get('market_question', '')}'"
                    ),
                    timestamp_ms=int(time.time() * 1000),
                ))

        return signals

    def _get_affected_assets(self, category: str) -> list:
        """Map event category to affected crypto assets."""
        category_lower = category.lower().replace(" ", "_")
        return CATEGORY_ASSET_MAP.get(category_lower, ["BTC/USD", "ETH/USD"])
