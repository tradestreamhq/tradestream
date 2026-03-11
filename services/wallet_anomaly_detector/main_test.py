#!/usr/bin/env python3
"""Tests for Wallet Behavior Anomaly Detection Engine."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from absl import flags

FLAGS = flags.FLAGS

if not FLAGS.is_parsed():
    FLAGS.mark_as_parsed()

from main import (
    AnomalyScore,
    AnomalyScorer,
    MarketSignal,
    SignalAggregator,
    SignalConfidence,
    Trade,
    WalletActivity,
)


def _make_wallet(
    address="0xabc",
    age_days=1.0,
    avg_position_size=100.0,
    total_trades=10,
    niche_market_count=0,
):
    return WalletActivity(
        address=address,
        age_days=age_days,
        avg_position_size=avg_position_size,
        total_trades=total_trades,
        niche_market_count=niche_market_count,
    )


def _make_trade(
    wallet_address="0xabc",
    market_id="market-1",
    size=100.0,
    implied_probability=0.50,
):
    return Trade(
        trade_id="trade-1",
        wallet_address=wallet_address,
        market_id=market_id,
        size=size,
        implied_probability=implied_probability,
        timestamp=datetime.now(timezone.utc),
    )


class TestAnomalyScorer:
    """Test cases for AnomalyScorer."""

    @pytest.fixture
    def scorer(self):
        return AnomalyScorer()

    def test_fresh_wallet_scores_freshness(self, scorer):
        """Fresh wallet (< 7 days) should receive freshness points."""
        wallet = _make_wallet(age_days=2)
        trade = _make_trade(size=50)
        result = scorer.score_wallet(wallet, trade)
        assert result.score >= 30
        assert any("Fresh wallet" in r for r in result.reasons)

    def test_old_wallet_no_freshness(self, scorer):
        """Old wallet (>= 7 days) should not receive freshness points."""
        wallet = _make_wallet(age_days=30)
        trade = _make_trade(size=50)
        result = scorer.score_wallet(wallet, trade)
        assert not any("Fresh wallet" in r for r in result.reasons)

    def test_large_position_scores_size(self, scorer):
        """Position > 5x average should receive size anomaly points."""
        wallet = _make_wallet(avg_position_size=100)
        trade = _make_trade(size=600)  # 6x average
        result = scorer.score_wallet(wallet, trade)
        assert any("Unusual size" in r for r in result.reasons)

    def test_normal_position_no_size_score(self, scorer):
        """Position within normal range should not score size anomaly."""
        wallet = _make_wallet(avg_position_size=100)
        trade = _make_trade(size=200)  # 2x average, below 5x
        result = scorer.score_wallet(wallet, trade)
        assert not any("Unusual size" in r for r in result.reasons)

    def test_zero_avg_position_size(self, scorer):
        """Wallet with no history (avg=0) should flag nonzero trades."""
        wallet = _make_wallet(avg_position_size=0)
        trade = _make_trade(size=500)
        result = scorer.score_wallet(wallet, trade)
        assert any("first known trade" in r for r in result.reasons)

    def test_niche_market_affinity(self, scorer):
        """Wallet with many niche market entries should score niche affinity."""
        wallet = _make_wallet(niche_market_count=5)
        trade = _make_trade()
        result = scorer.score_wallet(wallet, trade)
        assert any("Niche market" in r for r in result.reasons)

    def test_no_niche_affinity(self, scorer):
        """Wallet with few niche entries should not score niche affinity."""
        wallet = _make_wallet(niche_market_count=2)
        trade = _make_trade()
        result = scorer.score_wallet(wallet, trade)
        assert not any("Niche market" in r for r in result.reasons)

    def test_long_odds_bet(self, scorer):
        """Bet on low-probability outcome should score probability deviation."""
        wallet = _make_wallet(age_days=30)
        trade = _make_trade(implied_probability=0.05)
        result = scorer.score_wallet(wallet, trade)
        assert any("Long odds" in r for r in result.reasons)

    def test_normal_odds_no_probability_score(self, scorer):
        """Normal probability bet should not score probability deviation."""
        wallet = _make_wallet(age_days=30)
        trade = _make_trade(implied_probability=0.50)
        result = scorer.score_wallet(wallet, trade)
        assert not any("Long odds" in r for r in result.reasons)

    def test_all_signals_fire_max_score(self, scorer):
        """When all anomaly signals fire, score should be 100."""
        wallet = _make_wallet(
            age_days=1,
            avg_position_size=100,
            niche_market_count=5,
        )
        trade = _make_trade(size=600, implied_probability=0.05)
        result = scorer.score_wallet(wallet, trade)
        assert result.score == 100
        assert result.alert is True
        assert len(result.reasons) == 4

    def test_no_signals_zero_score(self, scorer):
        """Normal wallet and trade should produce zero score."""
        wallet = _make_wallet(
            age_days=30,
            avg_position_size=100,
            niche_market_count=0,
        )
        trade = _make_trade(size=50, implied_probability=0.50)
        result = scorer.score_wallet(wallet, trade)
        assert result.score == 0
        assert result.alert is False
        assert len(result.reasons) == 0

    def test_alert_threshold_boundary(self, scorer):
        """Score exactly at threshold should trigger alert."""
        # freshness (30) + niche (20) = 50 = threshold
        wallet = _make_wallet(age_days=1, niche_market_count=5)
        trade = _make_trade(size=50, implied_probability=0.50)
        result = scorer.score_wallet(wallet, trade)
        assert result.score == 50
        assert result.alert is True

    def test_below_alert_threshold(self, scorer):
        """Score below threshold should not trigger alert."""
        # Only freshness (30) < 50
        wallet = _make_wallet(age_days=1)
        trade = _make_trade(size=50, implied_probability=0.50)
        result = scorer.score_wallet(wallet, trade)
        assert result.score == 30
        assert result.alert is False

    def test_custom_weights(self):
        """Custom weights should change scoring behavior."""
        scorer = AnomalyScorer(weight_freshness=50, weight_size=0, weight_niche=0, weight_probability=0)
        wallet = _make_wallet(age_days=1)
        trade = _make_trade()
        result = scorer.score_wallet(wallet, trade)
        assert result.score == 50
        assert result.alert is True

    def test_custom_thresholds(self):
        """Custom thresholds should change detection sensitivity."""
        scorer = AnomalyScorer(
            wallet_age_threshold_days=3,
            position_size_multiplier=2.0,
            niche_market_threshold=1,
            probability_threshold=0.20,
        )
        # Wallet is 5 days old — above custom 3-day threshold
        wallet = _make_wallet(age_days=5, avg_position_size=100, niche_market_count=2)
        trade = _make_trade(size=250, implied_probability=0.15)
        result = scorer.score_wallet(wallet, trade)
        # No freshness (5 > 3), yes size (2.5x > 2x), yes niche (2 > 1), yes prob (0.15 < 0.20)
        assert not any("Fresh wallet" in r for r in result.reasons)
        assert any("Unusual size" in r for r in result.reasons)
        assert any("Niche market" in r for r in result.reasons)
        assert any("Long odds" in r for r in result.reasons)

    def test_score_contains_wallet_and_market(self, scorer):
        """AnomalyScore should carry wallet address and market id."""
        wallet = _make_wallet(address="0xdef")
        trade = _make_trade(wallet_address="0xdef", market_id="mkt-42")
        result = scorer.score_wallet(wallet, trade)
        assert result.wallet_address == "0xdef"
        assert result.market_id == "mkt-42"


class TestSignalAggregator:
    """Test cases for SignalAggregator."""

    @pytest.fixture
    def aggregator(self):
        return SignalAggregator(market_alert_count=5)

    def _make_alert(self, market_id="market-1", score=60, minutes_ago=10):
        ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        return AnomalyScore(
            wallet_address=f"0x{score:04x}",
            market_id=market_id,
            score=score,
            reasons=["test"],
            alert=True,
            timestamp=ts,
        )

    def test_enough_alerts_generates_signal(self, aggregator):
        """5+ alerts in a market should produce a signal."""
        alerts = [self._make_alert() for _ in range(5)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert len(signals) == 1
        assert signals[0].market_id == "market-1"
        assert signals[0].alert_count == 5

    def test_insufficient_alerts_no_signal(self, aggregator):
        """Fewer than 5 alerts should not produce a signal."""
        alerts = [self._make_alert() for _ in range(4)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert len(signals) == 0

    def test_old_alerts_excluded(self, aggregator):
        """Alerts outside the window should be excluded."""
        # 5 alerts but all too old
        alerts = [self._make_alert(minutes_ago=120) for _ in range(5)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert len(signals) == 0

    def test_multiple_markets(self, aggregator):
        """Alerts from different markets should produce independent signals."""
        alerts = [self._make_alert(market_id="m1") for _ in range(5)]
        alerts += [self._make_alert(market_id="m2") for _ in range(6)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert len(signals) == 2
        market_ids = {s.market_id for s in signals}
        assert market_ids == {"m1", "m2"}

    def test_non_alert_scores_excluded(self, aggregator):
        """Scores with alert=False should be excluded from aggregation."""
        alerts = []
        for _ in range(5):
            a = self._make_alert()
            a.alert = False
            alerts.append(a)
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert len(signals) == 0

    def test_confidence_low(self, aggregator):
        """5 alerts (1x threshold) should produce LOW confidence."""
        alerts = [self._make_alert() for _ in range(5)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert signals[0].confidence == SignalConfidence.LOW

    def test_confidence_medium(self, aggregator):
        """10 alerts (2x threshold) should produce MEDIUM confidence."""
        alerts = [self._make_alert() for _ in range(10)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert signals[0].confidence == SignalConfidence.MEDIUM

    def test_confidence_high(self, aggregator):
        """15 alerts (3x threshold) should produce HIGH confidence."""
        alerts = [self._make_alert() for _ in range(15)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert signals[0].confidence == SignalConfidence.HIGH

    def test_top_alerts_sorted_by_score(self, aggregator):
        """Top alerts in a signal should be sorted by score descending."""
        alerts = [self._make_alert(score=40 + i * 5) for i in range(6)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        top_scores = [a.score for a in signals[0].top_alerts]
        assert top_scores == sorted(top_scores, reverse=True)

    def test_top_alerts_limited_to_five(self, aggregator):
        """Signal should contain at most 5 top alerts."""
        alerts = [self._make_alert() for _ in range(10)]
        signals = aggregator.aggregate_alerts(alerts, window=timedelta(hours=1))
        assert len(signals[0].top_alerts) <= 5

    def test_market_question_and_price_passed_through(self, aggregator):
        """Market question and price should be included in signal."""
        alerts = [self._make_alert(market_id="m1") for _ in range(5)]
        signals = aggregator.aggregate_alerts(
            alerts,
            window=timedelta(hours=1),
            market_questions={"m1": "Will X happen?"},
            market_prices={"m1": 0.075},
        )
        assert signals[0].market_question == "Will X happen?"
        assert signals[0].suggested_entry_price == 0.075


class TestDataclasses:
    """Test data class serialization."""

    def test_anomaly_score_to_dict(self):
        score = AnomalyScore(
            wallet_address="0xabc",
            market_id="m1",
            score=75,
            reasons=["Fresh wallet: 2 days old"],
            alert=True,
        )
        d = score.to_dict()
        assert d["wallet_address"] == "0xabc"
        assert d["anomaly_score"] == 75
        assert d["alert"] is True
        assert "Fresh wallet" in d["reasons"][0]

    def test_market_signal_to_dict(self):
        alert = AnomalyScore(
            wallet_address="0xabc",
            market_id="m1",
            score=60,
            reasons=["test"],
            alert=True,
        )
        signal = MarketSignal(
            market_id="m1",
            market_question="Test?",
            confidence=SignalConfidence.HIGH,
            alert_count=10,
            top_alerts=[alert],
            suggested_entry_price=0.08,
        )
        d = signal.to_dict()
        assert d["confidence"] == "HIGH"
        assert d["alert_count"] == 10
        assert len(d["top_alerts"]) == 1
        assert d["suggested_entry_price"] == 0.08


if __name__ == "__main__":
    pytest.main([__file__])
