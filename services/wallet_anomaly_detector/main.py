#!/usr/bin/env python3
"""
Wallet Behavior Anomaly Detection Engine

Analyzes wallet transaction patterns on prediction markets to detect
anomalous behavior that may signal insider trading or whale movements.

Scoring components (configurable):
- Wallet freshness: Fresh wallets making large positions
- Position size anomaly: Unusual sizing relative to history
- Niche market affinity: Repeated entries in low-liquidity markets
- Probability deviation: Concentrated bets on low-probability outcomes

Generates per-wallet alerts and aggregates them into per-market signals.
"""

import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

from absl import app, flags, logging

FLAGS = flags.FLAGS

# Scoring weight configuration (GA-optimizable)
flags.DEFINE_float("weight_freshness", 30.0, "Score weight for fresh wallet detection")
flags.DEFINE_float("weight_size", 25.0, "Score weight for position size anomaly")
flags.DEFINE_float("weight_niche", 20.0, "Score weight for niche market affinity")
flags.DEFINE_float("weight_probability", 25.0, "Score weight for probability deviation")

# Threshold configuration (GA-optimizable)
flags.DEFINE_integer(
    "wallet_age_threshold_days", 7, "Max age in days to consider a wallet 'fresh'"
)
flags.DEFINE_float(
    "position_size_multiplier",
    5.0,
    "Multiplier over average position size to flag as anomalous",
)
flags.DEFINE_integer(
    "niche_market_threshold",
    3,
    "Number of low-liquidity market entries to flag niche affinity",
)
flags.DEFINE_float(
    "probability_threshold",
    0.10,
    "Implied probability below which a bet is considered long odds",
)
flags.DEFINE_integer(
    "alert_threshold", 50, "Minimum anomaly score to trigger a wallet alert"
)
flags.DEFINE_integer(
    "market_alert_count",
    5,
    "Minimum wallet alerts in a market to generate a market signal",
)
flags.DEFINE_string(
    "signal_window_minutes",
    "1440",
    "Time window in minutes for aggregating alerts into market signals",
)

# Output Configuration
flags.DEFINE_string(
    "output_topic", "insider-alerts", "Kafka topic for wallet anomaly alerts"
)
flags.DEFINE_string(
    "signal_topic",
    "prediction-market-signals",
    "Kafka topic for market-level signals",
)
flags.DEFINE_boolean("dry_run", False, "Run in dry-run mode (no Kafka output)")


class SignalConfidence(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class WalletActivity:
    """Represents a wallet's historical activity profile."""

    address: str
    age_days: float
    avg_position_size: float
    total_trades: int
    niche_market_count: int
    first_seen: Optional[datetime] = None


@dataclass
class Trade:
    """Represents a single trade on a prediction market."""

    trade_id: str
    wallet_address: str
    market_id: str
    size: float
    implied_probability: float
    timestamp: datetime
    market_question: str = ""
    current_price: float = 0.0


@dataclass
class AnomalyScore:
    """Anomaly score for a single wallet-trade pair."""

    wallet_address: str
    market_id: str
    score: int
    reasons: List[str]
    alert: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    triggering_trade: Optional[Trade] = None

    def to_dict(self) -> Dict:
        return {
            "wallet_address": self.wallet_address,
            "market_id": self.market_id,
            "anomaly_score": self.score,
            "reasons": self.reasons,
            "alert": self.alert,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MarketSignal:
    """Aggregated market-level signal from multiple wallet alerts."""

    market_id: str
    market_question: str
    confidence: SignalConfidence
    alert_count: int
    top_alerts: List[AnomalyScore]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    suggested_entry_price: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "market_id": self.market_id,
            "market_question": self.market_question,
            "confidence": self.confidence.value,
            "alert_count": self.alert_count,
            "top_alerts": [a.to_dict() for a in self.top_alerts],
            "timestamp": self.timestamp.isoformat(),
            "suggested_entry_price": self.suggested_entry_price,
        }


class AnomalyScorer:
    """Scores individual trades for anomalous wallet behavior.

    Each scoring component contributes independently to the total score.
    A score at or above the alert threshold triggers a wallet alert.
    """

    def __init__(
        self,
        weight_freshness: float = 30.0,
        weight_size: float = 25.0,
        weight_niche: float = 20.0,
        weight_probability: float = 25.0,
        wallet_age_threshold_days: int = 7,
        position_size_multiplier: float = 5.0,
        niche_market_threshold: int = 3,
        probability_threshold: float = 0.10,
        alert_threshold: int = 50,
    ):
        self.weight_freshness = weight_freshness
        self.weight_size = weight_size
        self.weight_niche = weight_niche
        self.weight_probability = weight_probability
        self.wallet_age_threshold_days = wallet_age_threshold_days
        self.position_size_multiplier = position_size_multiplier
        self.niche_market_threshold = niche_market_threshold
        self.probability_threshold = probability_threshold
        self.alert_threshold = alert_threshold

    def score_wallet(self, wallet: WalletActivity, trade: Trade) -> AnomalyScore:
        """Score a wallet-trade pair for anomalous behavior."""
        score = 0
        reasons: List[str] = []

        # Fresh wallet detection
        freshness_score = self._score_freshness(wallet)
        score += freshness_score
        if freshness_score > 0:
            reasons.append(f"Fresh wallet: {wallet.age_days:.0f} days old")

        # Position size anomaly
        size_score = self._score_position_size(wallet, trade)
        score += size_score
        if size_score > 0:
            if wallet.avg_position_size > 0:
                multiplier = trade.size / wallet.avg_position_size
                reasons.append(f"Unusual size: {multiplier:.1f}x average")
            else:
                reasons.append("Unusual size: first known trade")

        # Niche market affinity
        niche_score = self._score_niche_affinity(wallet)
        score += niche_score
        if niche_score > 0:
            reasons.append(
                f"Niche market pattern: {wallet.niche_market_count} low-liq markets"
            )

        # Probability deviation
        prob_score = self._score_probability_deviation(trade)
        score += prob_score
        if prob_score > 0:
            reasons.append(
                f"Long odds bet: {trade.implied_probability:.1%} probability"
            )

        return AnomalyScore(
            wallet_address=wallet.address,
            market_id=trade.market_id,
            score=int(score),
            reasons=reasons,
            alert=score >= self.alert_threshold,
            triggering_trade=trade,
        )

    def _score_freshness(self, wallet: WalletActivity) -> float:
        """Score based on wallet age. Fresher wallets get higher scores."""
        if wallet.age_days < self.wallet_age_threshold_days:
            return self.weight_freshness
        return 0.0

    def _score_position_size(self, wallet: WalletActivity, trade: Trade) -> float:
        """Score based on position size relative to wallet history."""
        if wallet.avg_position_size <= 0:
            # No history — treat as anomalous if trade size is nonzero
            return self.weight_size if trade.size > 0 else 0.0
        if trade.size > wallet.avg_position_size * self.position_size_multiplier:
            return self.weight_size
        return 0.0

    def _score_niche_affinity(self, wallet: WalletActivity) -> float:
        """Score based on participation in niche/low-liquidity markets."""
        if wallet.niche_market_count > self.niche_market_threshold:
            return self.weight_niche
        return 0.0

    def _score_probability_deviation(self, trade: Trade) -> float:
        """Score based on betting on low-probability outcomes."""
        if trade.implied_probability < self.probability_threshold:
            return self.weight_probability
        return 0.0


class SignalAggregator:
    """Aggregates per-wallet alerts into per-market signals."""

    def __init__(self, market_alert_count: int = 5):
        self.market_alert_count = market_alert_count

    def aggregate_alerts(
        self,
        alerts: List[AnomalyScore],
        window: timedelta,
        market_questions: Optional[Dict[str, str]] = None,
        market_prices: Optional[Dict[str, float]] = None,
    ) -> List[MarketSignal]:
        """Group alerts by market and generate market-level signals."""
        now = datetime.now(timezone.utc)
        cutoff = now - window

        # Filter to window and group by market
        market_alerts: Dict[str, List[AnomalyScore]] = {}
        for alert in alerts:
            if alert.alert and alert.timestamp >= cutoff:
                market_alerts.setdefault(alert.market_id, []).append(alert)

        signals: List[MarketSignal] = []
        for market_id, market_alert_list in market_alerts.items():
            if len(market_alert_list) >= self.market_alert_count:
                # Sort by score descending for top alerts
                sorted_alerts = sorted(
                    market_alert_list, key=lambda a: a.score, reverse=True
                )
                confidence = self._determine_confidence(len(market_alert_list))
                question = (market_questions or {}).get(market_id, "")
                price = (market_prices or {}).get(market_id, 0.0)

                signals.append(
                    MarketSignal(
                        market_id=market_id,
                        market_question=question,
                        confidence=confidence,
                        alert_count=len(market_alert_list),
                        top_alerts=sorted_alerts[:5],
                        suggested_entry_price=price,
                    )
                )

        return signals

    def _determine_confidence(self, alert_count: int) -> SignalConfidence:
        """Determine signal confidence based on alert count."""
        if alert_count >= self.market_alert_count * 3:
            return SignalConfidence.HIGH
        elif alert_count >= self.market_alert_count * 2:
            return SignalConfidence.MEDIUM
        return SignalConfidence.LOW


def create_scorer_from_flags() -> AnomalyScorer:
    """Create an AnomalyScorer using command-line flags."""
    return AnomalyScorer(
        weight_freshness=FLAGS.weight_freshness,
        weight_size=FLAGS.weight_size,
        weight_niche=FLAGS.weight_niche,
        weight_probability=FLAGS.weight_probability,
        wallet_age_threshold_days=FLAGS.wallet_age_threshold_days,
        position_size_multiplier=FLAGS.position_size_multiplier,
        niche_market_threshold=FLAGS.niche_market_threshold,
        probability_threshold=FLAGS.probability_threshold,
        alert_threshold=FLAGS.alert_threshold,
    )


def create_aggregator_from_flags() -> SignalAggregator:
    """Create a SignalAggregator using command-line flags."""
    return SignalAggregator(market_alert_count=FLAGS.market_alert_count)


def main(argv):
    """Main entry point."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")

    logging.set_verbosity(logging.INFO)
    logging.info("Starting Wallet Behavior Anomaly Detection Engine")

    scorer = create_scorer_from_flags()
    aggregator = create_aggregator_from_flags()

    logging.info(
        "Anomaly scorer initialized with weights: "
        "freshness=%.1f, size=%.1f, niche=%.1f, probability=%.1f, "
        "alert_threshold=%d",
        scorer.weight_freshness,
        scorer.weight_size,
        scorer.weight_niche,
        scorer.weight_probability,
        scorer.alert_threshold,
    )
    logging.info(
        "Signal aggregator initialized with market_alert_count=%d",
        aggregator.market_alert_count,
    )

    if FLAGS.dry_run:
        logging.info("Running in dry-run mode — no Kafka output")


if __name__ == "__main__":
    app.run(main)
