"""Tests for the sentiment analysis engine."""

import pytest

from services.sentiment_api.engine import (
    DivergenceSignal,
    SentimentBreakdown,
    SentimentResult,
    TimeframeSentiment,
    _calculate_macd,
    _calculate_rsi,
    _clamp,
    _sentiment_label,
    compute_macd_sentiment,
    compute_momentum_sentiment,
    compute_rsi_sentiment,
    compute_sentiment,
    compute_timeframe_sentiment,
    compute_volume_sentiment,
    detect_divergences,
)


class TestClamp:
    def test_within_bounds(self):
        assert _clamp(0.5) == 0.5

    def test_above_upper(self):
        assert _clamp(1.5) == 1.0

    def test_below_lower(self):
        assert _clamp(-1.5) == -1.0

    def test_at_bounds(self):
        assert _clamp(1.0) == 1.0
        assert _clamp(-1.0) == -1.0


class TestSentimentLabel:
    def test_strongly_bullish(self):
        assert _sentiment_label(0.7) == "strongly_bullish"

    def test_bullish(self):
        assert _sentiment_label(0.3) == "bullish"

    def test_neutral(self):
        assert _sentiment_label(0.0) == "neutral"

    def test_bearish(self):
        assert _sentiment_label(-0.4) == "bearish"

    def test_strongly_bearish(self):
        assert _sentiment_label(-0.8) == "strongly_bearish"


class TestRsiSentiment:
    def test_oversold_is_bullish(self):
        score = compute_rsi_sentiment(20)
        assert score > 0.5

    def test_overbought_is_bearish(self):
        score = compute_rsi_sentiment(80)
        assert score < -0.5

    def test_neutral_at_50(self):
        score = compute_rsi_sentiment(50)
        assert score == 0.0

    def test_edge_zero(self):
        assert compute_rsi_sentiment(0) == 0.0

    def test_edge_100(self):
        assert compute_rsi_sentiment(100) == 0.0


class TestMacdSentiment:
    def test_bullish_crossover(self):
        score = compute_macd_sentiment(macd=1.0, signal=0.5, histogram=0.5)
        assert score > 0

    def test_bearish_crossover(self):
        score = compute_macd_sentiment(macd=-1.0, signal=0.5, histogram=-1.5)
        assert score < 0

    def test_zero_values(self):
        score = compute_macd_sentiment(macd=0.0, signal=0.0, histogram=0.0)
        assert score == 0.0


class TestVolumeSentiment:
    def test_high_volume_up_move(self):
        score = compute_volume_sentiment(
            current_volume=200, avg_volume=100, price_change_pct=2.0
        )
        assert score > 0

    def test_high_volume_down_move(self):
        score = compute_volume_sentiment(
            current_volume=200, avg_volume=100, price_change_pct=-2.0
        )
        assert score < 0

    def test_low_volume(self):
        score = compute_volume_sentiment(
            current_volume=50, avg_volume=100, price_change_pct=1.0
        )
        # Low volume => weak signal
        assert abs(score) < 0.5

    def test_zero_avg_volume(self):
        assert compute_volume_sentiment(100, 0, 1.0) == 0.0


class TestMomentumSentiment:
    def test_positive_momentum(self):
        changes = [1.0, 1.5, 2.0, 2.5, 3.0]
        score = compute_momentum_sentiment(changes)
        assert score > 0

    def test_negative_momentum(self):
        changes = [-1.0, -1.5, -2.0, -2.5, -3.0]
        score = compute_momentum_sentiment(changes)
        assert score < 0

    def test_empty_changes(self):
        assert compute_momentum_sentiment([]) == 0.0

    def test_single_value(self):
        score = compute_momentum_sentiment([2.0])
        assert score > 0


class TestRsiCalculation:
    def test_basic_rsi(self):
        # Generate rising prices -> RSI should be high
        closes = [100 + i * 0.5 for i in range(30)]
        rsi = _calculate_rsi(closes, 14)
        assert rsi > 60

    def test_falling_prices(self):
        closes = [100 - i * 0.5 for i in range(30)]
        rsi = _calculate_rsi(closes, 14)
        assert rsi < 40

    def test_insufficient_data(self):
        closes = [100, 101, 102]
        rsi = _calculate_rsi(closes, 14)
        assert rsi == 50.0  # Default neutral


class TestMacdCalculation:
    def test_trending_up(self):
        closes = [100 + i * 0.5 for i in range(50)]
        macd, signal, histogram = _calculate_macd(closes)
        assert macd > 0

    def test_insufficient_data(self):
        closes = [100, 101]
        macd, signal, histogram = _calculate_macd(closes)
        assert macd == 0.0


class TestComputeTimeframeSentiment:
    def _make_candles(self, closes, volumes=None):
        if volumes is None:
            volumes = [100.0] * len(closes)
        return [
            {
                "time": f"2026-01-{i+1:02d}T00:00:00Z",
                "open": c - 0.5,
                "high": c + 1.0,
                "low": c - 1.0,
                "close": c,
                "volume": v,
            }
            for i, (c, v) in enumerate(zip(closes, volumes))
        ]

    def test_bullish_candles(self):
        # Steadily rising prices
        closes = [100 + i for i in range(40)]
        candles = self._make_candles(closes)
        result = compute_timeframe_sentiment(candles)
        assert result is not None
        assert result.score > 0

    def test_bearish_candles(self):
        closes = [140 - i for i in range(40)]
        candles = self._make_candles(closes)
        result = compute_timeframe_sentiment(candles)
        assert result is not None
        assert result.score < 0

    def test_insufficient_candles(self):
        candles = self._make_candles([100, 101, 102])
        result = compute_timeframe_sentiment(candles)
        assert result is None


class TestComputeSentiment:
    def _make_candles(self, base, direction, count=40):
        closes = [base + direction * i for i in range(count)]
        return [
            {
                "time": f"2026-01-{i+1:02d}T00:00:00Z",
                "open": c - 0.5,
                "high": c + 1.0,
                "low": c - 1.0,
                "close": c,
                "volume": 100.0,
            }
            for i, c in enumerate(closes)
        ]

    def test_aggregates_timeframes(self):
        candles_by_tf = {
            "1h": self._make_candles(100, 1),
            "4h": self._make_candles(100, 1),
            "1d": self._make_candles(100, 1),
        }
        result = compute_sentiment("BTC/USD", candles_by_tf)
        assert result is not None
        assert result.symbol == "BTC/USD"
        assert result.score > 0
        assert len(result.timeframe_scores) == 3

    def test_no_data(self):
        result = compute_sentiment("BTC/USD", {})
        assert result is None

    def test_single_timeframe(self):
        candles_by_tf = {"1d": self._make_candles(100, 1)}
        result = compute_sentiment("BTC/USD", candles_by_tf)
        assert result is not None
        assert len(result.timeframe_scores) == 1

    def test_score_bounds(self):
        candles_by_tf = {"1d": self._make_candles(100, 5)}
        result = compute_sentiment("BTC/USD", candles_by_tf)
        assert result is not None
        assert -1.0 <= result.score <= 1.0

    def test_label_present(self):
        candles_by_tf = {"1d": self._make_candles(100, 1)}
        result = compute_sentiment("BTC/USD", candles_by_tf)
        assert result.label in [
            "strongly_bullish",
            "bullish",
            "neutral",
            "bearish",
            "strongly_bearish",
        ]


class TestDetectDivergences:
    def test_bullish_divergence(self):
        results = [
            SentimentResult(
                symbol="BTC/USD",
                score=0.6,
                label="bullish",
                timeframe_scores=[],
                breakdown=SentimentBreakdown(),
            )
        ]
        price_changes = {"BTC/USD": -5.0}
        divs = detect_divergences(results, price_changes, threshold=0.3)
        assert len(divs) == 1
        assert divs[0].divergence_type == "bullish_divergence"

    def test_bearish_divergence(self):
        results = [
            SentimentResult(
                symbol="ETH/USD",
                score=-0.6,
                label="bearish",
                timeframe_scores=[],
                breakdown=SentimentBreakdown(),
            )
        ]
        price_changes = {"ETH/USD": 5.0}
        divs = detect_divergences(results, price_changes, threshold=0.3)
        assert len(divs) == 1
        assert divs[0].divergence_type == "bearish_divergence"

    def test_no_divergence_when_aligned(self):
        results = [
            SentimentResult(
                symbol="BTC/USD",
                score=0.6,
                label="bullish",
                timeframe_scores=[],
                breakdown=SentimentBreakdown(),
            )
        ]
        price_changes = {"BTC/USD": 5.0}
        divs = detect_divergences(results, price_changes, threshold=0.3)
        assert len(divs) == 0

    def test_sorted_by_strength(self):
        results = [
            SentimentResult(
                symbol="BTC/USD",
                score=0.4,
                label="bullish",
                timeframe_scores=[],
                breakdown=SentimentBreakdown(),
            ),
            SentimentResult(
                symbol="ETH/USD",
                score=0.9,
                label="strongly_bullish",
                timeframe_scores=[],
                breakdown=SentimentBreakdown(),
            ),
        ]
        price_changes = {"BTC/USD": -1.0, "ETH/USD": -5.0}
        divs = detect_divergences(results, price_changes, threshold=0.3)
        assert len(divs) == 2
        assert divs[0].strength >= divs[1].strength
