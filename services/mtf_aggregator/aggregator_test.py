"""
Tests for Multi-Timeframe Signal Aggregator.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aggregator import MultiTimeframeAggregator, _direction_value
from models import (
    AggregationResult,
    DEFAULT_TIMEFRAME_WEIGHTS,
    SignalDirection,
    Timeframe,
    TimeframeSignal,
)


class TestDirectionValue:
    def test_buy(self):
        assert _direction_value(SignalDirection.BUY) == 1.0

    def test_sell(self):
        assert _direction_value(SignalDirection.SELL) == -1.0

    def test_hold(self):
        assert _direction_value(SignalDirection.HOLD) == 0.0


class TestModels:
    def test_timeframe_signal_creation(self):
        sig = TimeframeSignal(
            symbol="BTC/USD",
            timeframe=Timeframe.H1,
            direction=SignalDirection.BUY,
            confidence=0.85,
            strategy_type="SMA_RSI",
        )
        assert sig.symbol == "BTC/USD"
        assert sig.timeframe == Timeframe.H1
        assert sig.confidence == 0.85

    def test_aggregation_result_conviction_tiers(self):
        base = dict(
            symbol="BTC/USD",
            alignment_score=1.0,
            direction=SignalDirection.BUY,
            timeframe_count=3,
        )
        assert AggregationResult(conviction_score=0.80, **base).conviction_tier == "STRONG"
        assert AggregationResult(conviction_score=0.55, **base).conviction_tier == "MODERATE"
        assert AggregationResult(conviction_score=0.30, **base).conviction_tier == "WEAK"
        assert AggregationResult(conviction_score=0.10, **base).conviction_tier == "NEUTRAL"
        # Negative scores use absolute value for tier
        assert AggregationResult(conviction_score=-0.80, **base).conviction_tier == "STRONG"

    def test_default_weights_sum_to_one(self):
        total = sum(DEFAULT_TIMEFRAME_WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=0.01)


class TestMultiTimeframeAggregator:
    @pytest.fixture
    def aggregator(self):
        return MultiTimeframeAggregator()

    @pytest.fixture
    def custom_aggregator(self):
        weights = {
            Timeframe.M5: 0.20,
            Timeframe.H1: 0.30,
            Timeframe.D1: 0.50,
        }
        return MultiTimeframeAggregator(timeframe_weights=weights)

    # --- Empty / edge cases ---

    def test_empty_signals(self, aggregator):
        result = aggregator.aggregate([])
        assert result.conviction_score == 0.0
        assert result.alignment_score == 0.0
        assert result.direction == SignalDirection.HOLD
        assert result.timeframe_count == 0

    def test_single_signal(self, aggregator):
        signals = [
            TimeframeSignal(
                symbol="BTC/USD",
                timeframe=Timeframe.D1,
                direction=SignalDirection.BUY,
                confidence=0.9,
            )
        ]
        result = aggregator.aggregate(signals)
        assert result.conviction_score > 0.0
        assert result.direction == SignalDirection.BUY
        assert result.timeframe_count == 1
        assert result.alignment_score == 1.0

    # --- All timeframes agree (high conviction) ---

    def test_all_buy_high_conviction(self, custom_aggregator):
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.M5, SignalDirection.BUY, 0.9),
            TimeframeSignal("BTC/USD", Timeframe.H1, SignalDirection.BUY, 0.85),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.BUY, 0.95),
        ]
        result = custom_aggregator.aggregate(signals)
        assert result.conviction_score > 0.7
        assert result.direction == SignalDirection.BUY
        assert result.alignment_score == 1.0
        assert result.conviction_tier in ("STRONG", "MODERATE")

    def test_all_sell_high_conviction(self, custom_aggregator):
        signals = [
            TimeframeSignal("ETH/USD", Timeframe.M5, SignalDirection.SELL, 0.8),
            TimeframeSignal("ETH/USD", Timeframe.H1, SignalDirection.SELL, 0.9),
            TimeframeSignal("ETH/USD", Timeframe.D1, SignalDirection.SELL, 0.85),
        ]
        result = custom_aggregator.aggregate(signals)
        assert result.conviction_score < -0.7
        assert result.direction == SignalDirection.SELL
        assert result.alignment_score == 1.0

    # --- Mixed signals (lower conviction) ---

    def test_mixed_signals_reduce_conviction(self, custom_aggregator):
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.M5, SignalDirection.BUY, 0.9),
            TimeframeSignal("BTC/USD", Timeframe.H1, SignalDirection.SELL, 0.8),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.BUY, 0.7),
        ]
        result = custom_aggregator.aggregate(signals)
        # Mixed signals should yield lower absolute conviction than unanimous
        assert abs(result.conviction_score) < 0.7
        assert result.alignment_score < 1.0

    def test_opposing_equal_signals_near_zero(self):
        weights = {Timeframe.H1: 0.5, Timeframe.D1: 0.5}
        agg = MultiTimeframeAggregator(timeframe_weights=weights, alignment_bonus=0.0)
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.H1, SignalDirection.BUY, 0.8),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.SELL, 0.8),
        ]
        result = agg.aggregate(signals)
        assert result.conviction_score == pytest.approx(0.0, abs=0.01)

    # --- Higher timeframes dominate ---

    def test_higher_timeframe_dominates(self, custom_aggregator):
        """D1 (weight 0.50) SELL should overpower M5 (weight 0.20) BUY."""
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.M5, SignalDirection.BUY, 0.9),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.SELL, 0.9),
        ]
        result = custom_aggregator.aggregate(signals)
        assert result.conviction_score < 0.0
        assert result.direction == SignalDirection.SELL

    # --- HOLD signals ---

    def test_hold_signals_are_neutral(self, custom_aggregator):
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.M5, SignalDirection.HOLD, 0.5),
            TimeframeSignal("BTC/USD", Timeframe.H1, SignalDirection.BUY, 0.8),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.BUY, 0.7),
        ]
        result = custom_aggregator.aggregate(signals)
        assert result.direction == SignalDirection.BUY
        # HOLD doesn't count toward alignment denominator for directional signals
        assert result.alignment_score == 1.0  # Both directional signals agree

    def test_all_hold(self, aggregator):
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.H1, SignalDirection.HOLD, 0.5),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.HOLD, 0.6),
        ]
        result = aggregator.aggregate(signals)
        assert result.conviction_score == 0.0
        assert result.direction == SignalDirection.HOLD
        assert result.alignment_score == 0.0

    # --- Duplicate timeframes: highest confidence wins ---

    def test_duplicate_timeframe_uses_highest_confidence(self, custom_aggregator):
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.H1, SignalDirection.BUY, 0.5),
            TimeframeSignal("BTC/USD", Timeframe.H1, SignalDirection.SELL, 0.9),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.BUY, 0.8),
        ]
        result = custom_aggregator.aggregate(signals)
        # The H1 slot should use the SELL signal (confidence 0.9 > 0.5)
        assert "1h" in result.timeframe_details
        assert result.timeframe_details["1h"]["direction"] == "SELL"

    # --- Conviction is clamped to [-1, +1] ---

    def test_conviction_clamped(self):
        weights = {Timeframe.D1: 1.0}
        agg = MultiTimeframeAggregator(timeframe_weights=weights, alignment_bonus=0.5)
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.BUY, 1.0),
        ]
        result = agg.aggregate(signals)
        assert result.conviction_score <= 1.0

    # --- Alignment bonus effect ---

    def test_alignment_bonus_increases_conviction(self, custom_aggregator):
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.M5, SignalDirection.BUY, 0.7),
            TimeframeSignal("BTC/USD", Timeframe.H1, SignalDirection.BUY, 0.7),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.BUY, 0.7),
        ]
        with_bonus = custom_aggregator.aggregate(signals)

        no_bonus_agg = MultiTimeframeAggregator(
            timeframe_weights=custom_aggregator.timeframe_weights,
            alignment_bonus=0.0,
        )
        without_bonus = no_bonus_agg.aggregate(signals)

        assert with_bonus.conviction_score > without_bonus.conviction_score

    # --- Timeframe details ---

    def test_timeframe_details_populated(self, custom_aggregator):
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.M5, SignalDirection.BUY, 0.8),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.SELL, 0.6),
        ]
        result = custom_aggregator.aggregate(signals)
        assert "5m" in result.timeframe_details
        assert "1d" in result.timeframe_details
        assert result.timeframe_details["5m"]["direction"] == "BUY"
        assert result.timeframe_details["1d"]["direction"] == "SELL"
        # Weights should be normalized for active timeframes only
        weight_sum = sum(
            d["weight"] for d in result.timeframe_details.values()
        )
        assert weight_sum == pytest.approx(1.0, abs=0.01)

    # --- Custom weights ---

    def test_custom_weights_respected(self):
        # Give M5 all the weight
        weights = {Timeframe.M5: 1.0, Timeframe.D1: 0.0}
        agg = MultiTimeframeAggregator(timeframe_weights=weights, alignment_bonus=0.0)
        signals = [
            TimeframeSignal("BTC/USD", Timeframe.M5, SignalDirection.BUY, 0.8),
            TimeframeSignal("BTC/USD", Timeframe.D1, SignalDirection.SELL, 0.9),
        ]
        result = agg.aggregate(signals)
        # M5 BUY should dominate since D1 has zero weight
        assert result.conviction_score > 0.0
        assert result.direction == SignalDirection.BUY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
