"""Tests for the Market Regime Detector."""

import math
from unittest import mock

import pytest

from services.learning_engine.regime_detector import (
    REGIME_THRESHOLDS,
    RegimeDetector,
)


def _make_candles(closes, highs=None, lows=None, volumes=None):
    """Helper to create candle dicts from price lists."""
    n = len(closes)
    if highs is None:
        highs = [c * 1.01 for c in closes]
    if lows is None:
        lows = [c * 0.99 for c in closes]
    if volumes is None:
        volumes = [1000.0] * n
    return [
        {"open": closes[i], "high": highs[i], "low": lows[i],
         "close": closes[i], "volume": volumes[i]}
        for i in range(n)
    ]


class TestRegimeDetection:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_insufficient_data(self):
        candles = _make_candles([100, 101, 102])
        result = self.detector.detect(candles)
        assert result["regime_type"] == "unknown"
        assert result["confidence"] == 0.0

    def test_trending_up(self):
        # Strong uptrend: prices steadily increasing
        closes = [100 + i * 2 for i in range(30)]
        candles = _make_candles(closes)
        result = self.detector.detect(candles, "BTC-USD")
        assert result["regime_type"] == "trending_up"
        assert result["confidence"] > 0.5
        assert result["instrument"] == "BTC-USD"

    def test_trending_down(self):
        # Strong downtrend
        closes = [200 - i * 2 for i in range(30)]
        candles = _make_candles(closes)
        result = self.detector.detect(candles, "ETH-USD")
        assert result["regime_type"] == "trending_down"
        assert result["confidence"] > 0.5

    def test_volatile_market(self):
        # High volatility, no clear trend: large swings
        import random
        random.seed(42)
        base = 100
        closes = []
        for i in range(30):
            base += random.uniform(-10, 10)
            closes.append(max(50, base))
        candles = _make_candles(
            closes,
            highs=[c * 1.05 for c in closes],
            lows=[c * 0.95 for c in closes],
        )
        result = self.detector.detect(candles)
        # Should be volatile or ranging — not trending
        assert result["regime_type"] in ("volatile", "ranging")

    def test_quiet_market(self):
        # Very low volatility: tiny price changes, low volume
        closes = [100 + (i % 3) * 0.01 for i in range(30)]
        volumes = [100.0] * 30  # Low volume
        candles = _make_candles(
            closes,
            highs=[c + 0.01 for c in closes],
            lows=[c - 0.01 for c in closes],
            volumes=volumes,
        )
        result = self.detector.detect(candles)
        assert result["regime_type"] == "quiet"

    def test_ranging_market(self):
        # Oscillating between two levels
        closes = [100 + 5 * math.sin(i * 0.5) for i in range(30)]
        candles = _make_candles(closes)
        result = self.detector.detect(candles)
        assert result["regime_type"] in ("ranging", "quiet", "volatile")
        assert result["confidence"] > 0.0

    def test_indicators_populated(self):
        closes = [100 + i for i in range(30)]
        candles = _make_candles(closes)
        result = self.detector.detect(candles)
        indicators = result["indicators"]
        assert "volatility" in indicators
        assert "trend_strength" in indicators
        assert "trend_direction" in indicators
        assert "volume_ratio" in indicators
        assert "atr_ratio" in indicators


class TestVolatilityCalculation:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_zero_volatility(self):
        closes = [100.0] * 10
        vol = self.detector._calculate_volatility(closes)
        assert vol == 0.0

    def test_positive_volatility(self):
        closes = [100, 102, 98, 103, 97, 105, 95]
        vol = self.detector._calculate_volatility(closes)
        assert vol > 0.0

    def test_single_candle(self):
        vol = self.detector._calculate_volatility([100])
        assert vol == 0.0


class TestTrendStrength:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_perfect_trend(self):
        closes = [float(i) for i in range(20)]
        strength = self.detector._calculate_trend_strength(closes)
        assert strength > 0.9

    def test_no_trend(self):
        closes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
        strength = self.detector._calculate_trend_strength(closes)
        assert strength == 0.0

    def test_short_data(self):
        strength = self.detector._calculate_trend_strength([100, 101])
        assert strength == 0.0


class TestTrendDirection:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_upward_direction(self):
        closes = [100 + i for i in range(20)]
        direction = self.detector._calculate_trend_direction(closes)
        assert direction > 0

    def test_downward_direction(self):
        closes = [200 - i for i in range(20)]
        direction = self.detector._calculate_trend_direction(closes)
        assert direction < 0


class TestVolumeRatio:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_normal_volume(self):
        volumes = [1000.0] * 20
        ratio = self.detector._calculate_volume_ratio(volumes)
        assert abs(ratio - 1.0) < 0.01

    def test_surging_volume(self):
        volumes = [1000.0] * 15 + [3000.0] * 5
        ratio = self.detector._calculate_volume_ratio(volumes)
        assert ratio > 1.0

    def test_empty_volumes(self):
        ratio = self.detector._calculate_volume_ratio([])
        assert ratio == 1.0

    def test_zero_volumes(self):
        ratio = self.detector._calculate_volume_ratio([0.0] * 10)
        assert ratio == 1.0


class TestATRRatio:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_positive_atr(self):
        highs = [105, 106, 107, 108, 109]
        lows = [95, 96, 97, 98, 99]
        closes = [100, 101, 102, 103, 104]
        ratio = self.detector._calculate_atr_ratio(highs, lows, closes)
        assert ratio > 0.0

    def test_single_candle(self):
        ratio = self.detector._calculate_atr_ratio([105], [95], [100])
        assert ratio == 0.0


class TestRegimeStorage:
    def test_store_regime(self):
        conn = mock.Mock()
        cur = mock.Mock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        detector = RegimeDetector(db_connection=conn)
        result = detector.store_regime({
            "instrument": "BTC-USD",
            "regime_type": "trending_up",
            "confidence": 0.85,
            "indicators": {"volatility": 0.02},
        })

        assert result is not None
        assert cur.execute.call_count == 2  # UPDATE + INSERT
        conn.commit.assert_called_once()

    def test_store_without_connection(self):
        detector = RegimeDetector()
        result = detector.store_regime({"instrument": "BTC-USD", "regime_type": "trending_up",
                                        "confidence": 0.85, "indicators": {}})
        assert result is None

    def test_get_current_regime_no_connection(self):
        detector = RegimeDetector()
        assert detector.get_current_regime("BTC-USD") is None

    def test_get_regime_history_no_connection(self):
        detector = RegimeDetector()
        assert detector.get_regime_history("BTC-USD") == []


class TestCustomThresholds:
    def test_custom_thresholds(self):
        custom = dict(REGIME_THRESHOLDS)
        custom["trend_strong"] = 0.1  # very low threshold
        detector = RegimeDetector(thresholds=custom)
        closes = [100 + i * 0.5 for i in range(30)]
        candles = _make_candles(closes)
        result = detector.detect(candles)
        assert result["regime_type"] in ("trending_up", "trending_down")
