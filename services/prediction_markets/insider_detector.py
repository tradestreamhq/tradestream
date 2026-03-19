"""Insider activity detector for prediction markets.

Analyzes prediction market data for unusual volume/price patterns
that may indicate informed trading. Works in conjunction with the
polymarket-insider-tracker but also provides standalone detection.
"""

import time
from dataclasses import dataclass
from typing import List, Optional

from absl import logging


@dataclass(frozen=True)
class InsiderSignal:
    """Detected insider activity signal."""
    market_id: str
    market_question: str
    anomaly_type: str       # "volume_spike", "price_dislocation", "wallet_cluster"
    severity: str           # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    details: str
    detected_at_ms: int


class InsiderActivityDetector:
    """Detects unusual activity patterns in prediction market data.

    This operates as a complementary layer to the polymarket-insider-tracker,
    providing standalone anomaly detection when the tracker is unavailable
    and enriching tracker alerts with additional context.
    """

    def __init__(self, volume_spike_threshold: float = 3.0,
                 price_dislocation_threshold: float = 0.15,
                 min_volume_for_analysis: float = 1000.0):
        self.volume_spike_threshold = volume_spike_threshold
        self.price_dislocation_threshold = price_dislocation_threshold
        self.min_volume_for_analysis = min_volume_for_analysis
        # Track recent observations for pattern detection
        self._recent_volumes = {}  # market_id -> list of recent volumes

    def analyze_markets(self, markets: list) -> List[InsiderSignal]:
        """Analyze a batch of markets for insider activity signals.

        Args:
            markets: List of market dicts with volume, price, and metadata.

        Returns:
            List of InsiderSignal objects for detected anomalies.
        """
        signals = []

        for market in markets:
            market_id = market.get("market_id", market.get("condition_id", ""))
            volume = market.get("volume", 0)

            if volume < self.min_volume_for_analysis:
                continue

            volume_signal = self._check_volume_spike(market)
            if volume_signal:
                signals.append(volume_signal)

            price_signal = self._check_price_dislocation(market)
            if price_signal:
                signals.append(price_signal)

        return signals

    def enrich_tracker_alerts(self, tracker_alerts: list,
                               markets: list) -> list:
        """Enrich polymarket-insider-tracker alerts with local analysis.

        Args:
            tracker_alerts: Alerts from polymarket-insider-tracker API.
            markets: Current market data for context.

        Returns:
            Enriched alert dicts with additional context.
        """
        market_map = {}
        for m in markets:
            mid = m.get("market_id", m.get("condition_id", ""))
            if mid:
                market_map[mid] = m

        enriched = []
        for alert in tracker_alerts:
            alert_copy = dict(alert)
            market_id = alert.get("market_id", "")
            if market_id in market_map:
                market = market_map[market_id]
                alert_copy["current_volume"] = market.get("volume", 0)
                alert_copy["current_liquidity"] = market.get("liquidity", 0)
                alert_copy["market_active"] = market.get("active", False)
            enriched.append(alert_copy)

        return enriched

    def _check_volume_spike(self, market: dict) -> Optional[InsiderSignal]:
        """Detect volume spikes relative to historical average."""
        market_id = market.get("market_id", market.get("condition_id", ""))
        volume = market.get("volume", 0)
        avg_volume = market.get("avg_volume", 0)

        # Track volume history
        if market_id not in self._recent_volumes:
            self._recent_volumes[market_id] = []
        self._recent_volumes[market_id].append(volume)

        # Keep only last 20 observations
        if len(self._recent_volumes[market_id]) > 20:
            self._recent_volumes[market_id] = self._recent_volumes[market_id][-20:]

        # Use provided avg or calculate from history
        if avg_volume <= 0 and len(self._recent_volumes[market_id]) > 3:
            avg_volume = sum(self._recent_volumes[market_id][:-1]) / (
                len(self._recent_volumes[market_id]) - 1
            )

        if avg_volume <= 0:
            return None

        ratio = volume / avg_volume
        if ratio < self.volume_spike_threshold:
            return None

        severity = "MEDIUM"
        if ratio >= self.volume_spike_threshold * 2:
            severity = "HIGH"
        if ratio >= self.volume_spike_threshold * 4:
            severity = "CRITICAL"

        return InsiderSignal(
            market_id=market_id,
            market_question=market.get("question", market.get("title", "")),
            anomaly_type="volume_spike",
            severity=severity,
            details=f"Volume {ratio:.1f}x average ({volume:,.0f} vs avg {avg_volume:,.0f})",
            detected_at_ms=int(time.time() * 1000),
        )

    def _check_price_dislocation(self, market: dict) -> Optional[InsiderSignal]:
        """Detect rapid price movements that may indicate informed trading."""
        market_id = market.get("market_id", market.get("condition_id", ""))

        # Try different field names for current/previous prices
        current_price = (
            market.get("yes_price", 0)
            or market.get("probability", 0)
            or market.get("price", 0)
        )
        prev_price = (
            market.get("previous_yes_price", 0)
            or market.get("previous_probability", 0)
            or market.get("prev_price", 0)
        )

        if current_price <= 0 or prev_price <= 0:
            return None

        change = abs(current_price - prev_price)
        if change < self.price_dislocation_threshold:
            return None

        direction = "up" if current_price > prev_price else "down"
        severity = "MEDIUM"
        if change >= self.price_dislocation_threshold * 2:
            severity = "HIGH"
        if change >= self.price_dislocation_threshold * 3:
            severity = "CRITICAL"

        return InsiderSignal(
            market_id=market_id,
            market_question=market.get("question", market.get("title", "")),
            anomaly_type="price_dislocation",
            severity=severity,
            details=(
                f"Price moved {direction} {change:.0%} "
                f"({prev_price:.2f} -> {current_price:.2f})"
            ),
            detected_at_ms=int(time.time() * 1000),
        )
