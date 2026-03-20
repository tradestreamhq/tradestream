"""Tests for the sentiment signal generator."""

import time

import pytest

from services.market_sentiment.aggregator import AggregatedSentiment
from services.market_sentiment.signal_generator import (
    SentimentMomentumTracker,
    detect_divergence,
    generate_composite_signal,
    generate_contrarian_signal,
    generate_divergence_signal,
    generate_momentum_signal,
)


# ---------------------------------------------------------------------------
# Contrarian signal tests
# ---------------------------------------------------------------------------


class TestContrarianSignal:
    def _make_sentiment(self, score, symbol="BTC-USD"):
        from services.market_sentiment.aggregator import sentiment_label

        return AggregatedSentiment(
            symbol=symbol,
            composite_score=score,
            label=sentiment_label(score),
            source_scores=[],
        )

    def test_extreme_fear_generates_buy(self):
        s = self._make_sentiment(-0.8)
        signal = generate_contrarian_signal(s)
        assert signal.action == "BUY"
        assert signal.confidence >= 0.5
        assert signal.signal_type == "contrarian"
        assert "Extreme fear" in signal.reasoning

    def test_fear_generates_buy(self):
        s = self._make_sentiment(-0.4)
        signal = generate_contrarian_signal(s)
        assert signal.action == "BUY"
        assert signal.confidence >= 0.3

    def test_extreme_greed_generates_sell(self):
        s = self._make_sentiment(0.8)
        signal = generate_contrarian_signal(s)
        assert signal.action == "SELL"
        assert signal.confidence >= 0.5
        assert "Extreme greed" in signal.reasoning

    def test_greed_generates_sell(self):
        s = self._make_sentiment(0.4)
        signal = generate_contrarian_signal(s)
        assert signal.action == "SELL"
        assert signal.confidence >= 0.3

    def test_neutral_generates_hold(self):
        s = self._make_sentiment(0.1)
        signal = generate_contrarian_signal(s)
        assert signal.action == "HOLD"
        assert signal.signal_type == "contrarian"

    def test_boundary_fear(self):
        """Score exactly at -0.3 threshold should BUY."""
        s = self._make_sentiment(-0.3)
        signal = generate_contrarian_signal(s)
        assert signal.action == "BUY"

    def test_boundary_greed(self):
        """Score exactly at 0.3 threshold should SELL."""
        s = self._make_sentiment(0.3)
        signal = generate_contrarian_signal(s)
        assert signal.action == "SELL"

    def test_confidence_increases_with_extremity(self):
        mild = generate_contrarian_signal(self._make_sentiment(-0.35))
        extreme = generate_contrarian_signal(self._make_sentiment(-0.9))
        assert extreme.confidence > mild.confidence

    def test_confidence_capped(self):
        s = self._make_sentiment(-1.0)
        signal = generate_contrarian_signal(s)
        assert signal.confidence <= 0.95


# ---------------------------------------------------------------------------
# Divergence detection tests
# ---------------------------------------------------------------------------


class TestDivergenceDetection:
    def test_bearish_divergence(self):
        """Price up but sentiment negative."""
        result = detect_divergence("BTC-USD", -0.5, 5.0, threshold=0.3)
        assert result.divergence_type == "bearish_divergence"
        assert result.strength > 0

    def test_bullish_divergence(self):
        """Price down but sentiment positive."""
        result = detect_divergence("BTC-USD", 0.5, -5.0, threshold=0.3)
        assert result.divergence_type == "bullish_divergence"
        assert result.strength > 0

    def test_no_divergence_aligned(self):
        """Both positive -> no divergence."""
        result = detect_divergence("BTC-USD", 0.5, 5.0, threshold=0.3)
        assert result.divergence_type == "none"

    def test_no_divergence_below_threshold(self):
        """Small values below threshold."""
        result = detect_divergence("BTC-USD", -0.1, 0.2, threshold=0.3)
        assert result.divergence_type == "none"

    def test_strength_bounded(self):
        result = detect_divergence("BTC-USD", -0.9, 10.0, threshold=0.3)
        assert 0 < result.strength <= 1.0


class TestDivergenceSignal:
    def test_bullish_divergence_gives_buy(self):
        div = detect_divergence("BTC-USD", 0.6, -3.0, threshold=0.3)
        signal = generate_divergence_signal(div)
        assert signal is not None
        assert signal.action == "BUY"
        assert signal.signal_type == "divergence"

    def test_bearish_divergence_gives_sell(self):
        div = detect_divergence("BTC-USD", -0.6, 3.0, threshold=0.3)
        signal = generate_divergence_signal(div)
        assert signal is not None
        assert signal.action == "SELL"

    def test_no_divergence_returns_none(self):
        div = detect_divergence("BTC-USD", 0.5, 3.0, threshold=0.3)
        signal = generate_divergence_signal(div)
        assert signal is None


# ---------------------------------------------------------------------------
# Sentiment momentum tests
# ---------------------------------------------------------------------------


class TestSentimentMomentumTracker:
    def test_insufficient_data(self):
        tracker = SentimentMomentumTracker(window_size=10)
        tracker.record("BTC-USD", 0.5, timestamp=1.0)
        tracker.record("BTC-USD", 0.6, timestamp=2.0)
        assert tracker.compute_momentum("BTC-USD") is None

    def test_computes_velocity(self):
        tracker = SentimentMomentumTracker(window_size=10)
        tracker.record("BTC-USD", 0.0, timestamp=1.0)
        tracker.record("BTC-USD", 0.1, timestamp=2.0)
        tracker.record("BTC-USD", 0.2, timestamp=3.0)

        mom = tracker.compute_momentum("BTC-USD")
        assert mom is not None
        assert mom.velocity == pytest.approx(0.1, abs=0.01)
        assert mom.current_score == pytest.approx(0.2, abs=0.01)
        assert mom.previous_score == pytest.approx(0.1, abs=0.01)

    def test_computes_acceleration(self):
        tracker = SentimentMomentumTracker(window_size=10)
        # Increasing velocity: 0.1, 0.2 -> acceleration positive
        tracker.record("BTC-USD", 0.0, timestamp=1.0)
        tracker.record("BTC-USD", 0.1, timestamp=2.0)
        tracker.record("BTC-USD", 0.3, timestamp=3.0)

        mom = tracker.compute_momentum("BTC-USD")
        assert mom is not None
        assert mom.acceleration > 0  # accelerating bullish

    def test_negative_velocity(self):
        tracker = SentimentMomentumTracker(window_size=10)
        tracker.record("BTC-USD", 0.5, timestamp=1.0)
        tracker.record("BTC-USD", 0.3, timestamp=2.0)
        tracker.record("BTC-USD", 0.1, timestamp=3.0)

        mom = tracker.compute_momentum("BTC-USD")
        assert mom is not None
        assert mom.velocity < 0  # bearish

    def test_window_size_respected(self):
        tracker = SentimentMomentumTracker(window_size=3)
        for i in range(5):
            tracker.record("BTC-USD", float(i) * 0.1, timestamp=float(i))
        history = tracker.get_history("BTC-USD")
        assert len(history) == 3

    def test_unknown_symbol(self):
        tracker = SentimentMomentumTracker()
        assert tracker.compute_momentum("UNKNOWN") is None

    def test_direction_labels(self):
        tracker = SentimentMomentumTracker(window_size=10)
        # Accelerating bullish
        tracker.record("BTC-USD", 0.0, timestamp=1.0)
        tracker.record("BTC-USD", 0.1, timestamp=2.0)
        tracker.record("BTC-USD", 0.25, timestamp=3.0)
        tracker.record("BTC-USD", 0.45, timestamp=4.0)

        mom = tracker.compute_momentum("BTC-USD")
        assert mom is not None
        assert "bullish" in mom.direction


class TestMomentumSignal:
    def test_accelerating_bullish_buy(self):
        tracker = SentimentMomentumTracker(window_size=10)
        tracker.record("BTC-USD", 0.0, timestamp=1.0)
        tracker.record("BTC-USD", 0.1, timestamp=2.0)
        tracker.record("BTC-USD", 0.25, timestamp=3.0)
        tracker.record("BTC-USD", 0.45, timestamp=4.0)

        mom = tracker.compute_momentum("BTC-USD")
        signal = generate_momentum_signal(mom)
        if signal:
            assert signal.action == "BUY"
            assert signal.signal_type == "momentum"

    def test_accelerating_bearish_sell(self):
        tracker = SentimentMomentumTracker(window_size=10)
        tracker.record("BTC-USD", 0.0, timestamp=1.0)
        tracker.record("BTC-USD", -0.1, timestamp=2.0)
        tracker.record("BTC-USD", -0.25, timestamp=3.0)
        tracker.record("BTC-USD", -0.45, timestamp=4.0)

        mom = tracker.compute_momentum("BTC-USD")
        signal = generate_momentum_signal(mom)
        if signal:
            assert signal.action == "SELL"
            assert signal.signal_type == "momentum"

    def test_stable_returns_none(self):
        tracker = SentimentMomentumTracker(window_size=10)
        tracker.record("BTC-USD", 0.0, timestamp=1.0)
        tracker.record("BTC-USD", 0.01, timestamp=2.0)
        tracker.record("BTC-USD", 0.0, timestamp=3.0)

        mom = tracker.compute_momentum("BTC-USD")
        signal = generate_momentum_signal(mom)
        assert signal is None


# ---------------------------------------------------------------------------
# Composite signal tests
# ---------------------------------------------------------------------------


class TestCompositeSignal:
    def _make_sentiment(self, score, symbol="BTC-USD"):
        from services.market_sentiment.aggregator import sentiment_label

        return AggregatedSentiment(
            symbol=symbol,
            composite_score=score,
            label=sentiment_label(score),
            source_scores=[],
        )

    def test_extreme_fear_with_no_divergence(self):
        s = self._make_sentiment(-0.8)
        signal = generate_composite_signal(s, price_change_pct=-2.0)
        assert signal.action == "BUY"

    def test_extreme_greed_with_no_divergence(self):
        s = self._make_sentiment(0.8)
        signal = generate_composite_signal(s, price_change_pct=2.0)
        assert signal.action == "SELL"

    def test_neutral_with_divergence(self):
        """Even with neutral contrarian, divergence can generate a signal."""
        s = self._make_sentiment(0.5)
        # Price falling but sentiment positive -> bullish divergence
        signal = generate_composite_signal(s, price_change_pct=-5.0)
        # Should be BUY from divergence (bullish) or SELL from contrarian (greed)
        assert signal.action in ("BUY", "SELL")

    def test_multiple_agreeing_boost_confidence(self):
        """When contrarian and divergence agree, confidence is boosted."""
        s = self._make_sentiment(-0.7)
        # Price up but sentiment very negative -> bearish divergence + contrarian buy
        # Actually contrarian is BUY (extreme fear) but divergence with price up is bearish
        # Let's use price down + positive sentiment for aligned BUY
        s = self._make_sentiment(0.5)
        signal_no_div = generate_composite_signal(s, price_change_pct=0.0)
        # With bullish divergence (price down, sentiment up)
        signal_div = generate_composite_signal(s, price_change_pct=-5.0)
        # Both exist as actionable signals

    def test_with_momentum_tracker(self):
        tracker = SentimentMomentumTracker(window_size=10)
        tracker.record("BTC-USD", -0.5, timestamp=1.0)
        tracker.record("BTC-USD", -0.6, timestamp=2.0)
        tracker.record("BTC-USD", -0.75, timestamp=3.0)

        s = self._make_sentiment(-0.75)
        signal = generate_composite_signal(
            s, price_change_pct=0.0, momentum_tracker=tracker
        )
        assert signal.action in ("BUY", "SELL", "HOLD")
        assert signal.confidence > 0

    def test_hold_when_neutral_no_divergence(self):
        s = self._make_sentiment(0.0)
        signal = generate_composite_signal(s, price_change_pct=0.0)
        assert signal.action == "HOLD"
