"""Tests for the market regime detection engine using synthetic price series."""

import math
from datetime import datetime, timedelta, timezone

import pytest

from services.market_regime.regime_detector import (
    Regime,
    RegimeDetector,
    _atr,
    _max_drawdown,
    _realized_volatility,
    _sma,
)


def _make_timestamps(n: int) -> list:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [base + timedelta(days=i) for i in range(n)]


def _trending_up_series(n: int = 300, start: float = 100.0, daily_pct: float = 0.005):
    """Generate a steadily rising price series."""
    closes, highs, lows = [], [], []
    price = start
    for _ in range(n):
        price *= 1 + daily_pct
        closes.append(price)
        highs.append(price * 1.005)
        lows.append(price * 0.995)
    return closes, highs, lows


def _trending_down_series(n: int = 300, start: float = 100.0, daily_pct: float = 0.005):
    """Generate a steadily falling price series."""
    closes, highs, lows = [], [], []
    price = start
    for _ in range(n):
        price *= 1 - daily_pct
        closes.append(price)
        highs.append(price * 1.005)
        lows.append(price * 0.995)
    return closes, highs, lows


def _range_bound_series(n: int = 300, center: float = 100.0, amplitude: float = 1.0):
    """Generate a sideways oscillating price series."""
    closes, highs, lows = [], [], []
    for i in range(n):
        price = center + amplitude * math.sin(2 * math.pi * i / 20)
        closes.append(price)
        highs.append(price + 0.3)
        lows.append(price - 0.3)
    return closes, highs, lows


def _high_volatility_series(n: int = 300, start: float = 100.0):
    """Generate a series with high ATR via large swings."""
    closes, highs, lows = [], [], []
    price = start
    for i in range(n):
        swing = 5.0 * (1 if i % 2 == 0 else -1)
        price = max(price + swing, 10.0)
        closes.append(price)
        highs.append(price + 4.0)
        lows.append(price - 4.0)
    return closes, highs, lows


def _low_volatility_series(n: int = 300, center: float = 100.0):
    """Generate an extremely flat series with tiny moves."""
    closes, highs, lows = [], [], []
    for i in range(n):
        price = center + 0.01 * math.sin(i)
        closes.append(price)
        highs.append(price + 0.005)
        lows.append(price - 0.005)
    return closes, highs, lows


def _crisis_series(n: int = 300, start: float = 100.0):
    """Generate a series with a sharp crash in the last 60 candles."""
    closes, highs, lows = [], [], []
    price = start
    # Stable first part
    for _ in range(n - 60):
        price *= 1.001
        closes.append(price)
        highs.append(price * 1.002)
        lows.append(price * 0.998)
    # Crash: 30% drop
    for i in range(60):
        price *= 0.994
        closes.append(price)
        highs.append(price * 1.01)
        lows.append(price * 0.99)
    return closes, highs, lows


class TestHelperFunctions:
    def test_sma(self):
        assert _sma([1, 2, 3, 4, 5], 3) == pytest.approx(4.0)
        assert _sma([10, 20], 5) == 0.0

    def test_atr(self):
        highs = [12, 13, 14, 13, 15]
        lows = [10, 11, 12, 11, 13]
        closes = [11, 12, 13, 12, 14]
        result = _atr(highs, lows, closes, 3)
        assert result > 0

    def test_max_drawdown_no_drawdown(self):
        closes = [1, 2, 3, 4, 5]
        assert _max_drawdown(closes, 5) == 0.0

    def test_max_drawdown_with_drop(self):
        closes = [100, 110, 90, 95, 80]
        dd = _max_drawdown(closes, 5)
        assert dd < 0
        assert dd == pytest.approx((80 - 110) / 110)

    def test_realized_volatility(self):
        # Constant prices = zero vol
        closes = [100.0] * 30
        assert _realized_volatility(closes, 20) == 0.0


class TestRegimeDetectorTrendingUp:
    def test_detects_trending_up(self):
        detector = RegimeDetector()
        closes, highs, lows = _trending_up_series()
        result = detector.classify(
            "BTC/USD", closes, highs, lows, _make_timestamps(300)
        )
        assert result is not None
        assert result.regime == Regime.TRENDING_UP
        assert result.confidence >= 0.5
        assert result.symbol == "BTC/USD"

    def test_trending_up_indicators(self):
        detector = RegimeDetector()
        closes, highs, lows = _trending_up_series()
        result = detector.classify("BTC/USD", closes, highs, lows)
        assert result.indicators["sma_20"] > result.indicators["sma_50"]
        assert result.indicators["sma_50"] > result.indicators["sma_200"]


class TestRegimeDetectorTrendingDown:
    def test_detects_trending_down(self):
        detector = RegimeDetector()
        closes, highs, lows = _trending_down_series()
        result = detector.classify(
            "ETH/USD", closes, highs, lows, _make_timestamps(300)
        )
        assert result is not None
        assert result.regime == Regime.TRENDING_DOWN
        assert result.confidence >= 0.5

    def test_trending_down_sma_order(self):
        detector = RegimeDetector()
        closes, highs, lows = _trending_down_series()
        result = detector.classify("ETH/USD", closes, highs, lows)
        assert result.indicators["sma_20"] < result.indicators["sma_50"]
        assert result.indicators["sma_50"] < result.indicators["sma_200"]


class TestRegimeDetectorRangeBound:
    def test_detects_range_bound(self):
        detector = RegimeDetector()
        closes, highs, lows = _range_bound_series()
        result = detector.classify(
            "ADA/USD", closes, highs, lows, _make_timestamps(300)
        )
        assert result is not None
        assert result.regime == Regime.RANGE_BOUND


class TestRegimeDetectorHighVolatility:
    def test_detects_high_volatility(self):
        detector = RegimeDetector()
        closes, highs, lows = _high_volatility_series()
        result = detector.classify(
            "SOL/USD", closes, highs, lows, _make_timestamps(300)
        )
        assert result is not None
        assert result.regime == Regime.HIGH_VOLATILITY
        assert result.indicators["atr_percentile"] >= 80.0


class TestRegimeDetectorLowVolatility:
    def test_detects_low_volatility(self):
        detector = RegimeDetector()
        closes, highs, lows = _low_volatility_series()
        result = detector.classify(
            "USDT/USD", closes, highs, lows, _make_timestamps(300)
        )
        assert result is not None
        assert result.regime == Regime.LOW_VOLATILITY
        assert result.indicators["atr_percentile"] <= 20.0


class TestRegimeDetectorCrisis:
    def test_detects_crisis(self):
        detector = RegimeDetector()
        closes, highs, lows = _crisis_series()
        result = detector.classify(
            "LUNA/USD", closes, highs, lows, _make_timestamps(300)
        )
        assert result is not None
        assert result.regime == Regime.CRISIS
        assert result.confidence >= 0.5
        assert result.indicators["drawdown"] <= -0.20


class TestRegimeTransitions:
    def test_records_transition(self):
        detector = RegimeDetector()
        # First: trending up
        closes, highs, lows = _trending_up_series()
        detector.classify("BTC/USD", closes, highs, lows, _make_timestamps(300))
        # Then: crisis
        closes2, highs2, lows2 = _crisis_series()
        detector.classify("BTC/USD", closes2, highs2, lows2, _make_timestamps(300))

        transitions = detector.get_transitions("BTC/USD")
        assert len(transitions) >= 1
        last = transitions[-1]
        assert last.symbol == "BTC/USD"
        assert last.previous_regime != last.new_regime

    def test_no_transition_same_regime(self):
        detector = RegimeDetector()
        closes, highs, lows = _trending_up_series()
        detector.classify("BTC/USD", closes, highs, lows)
        detector.classify("BTC/USD", closes, highs, lows)
        transitions = detector.get_transitions("BTC/USD")
        assert len(transitions) == 0


class TestRegimeHistory:
    def test_history_accumulates(self):
        detector = RegimeDetector()
        closes, highs, lows = _trending_up_series()
        detector.classify("BTC/USD", closes, highs, lows)
        detector.classify("BTC/USD", closes, highs, lows)
        history = detector.get_history("BTC/USD")
        assert len(history) == 2

    def test_history_empty_symbol(self):
        detector = RegimeDetector()
        assert detector.get_history("UNKNOWN") == []


class TestEdgeCases:
    def test_insufficient_data(self):
        detector = RegimeDetector()
        result = detector.classify("X/USD", [100.0] * 50, [101.0] * 50, [99.0] * 50)
        assert result is None

    def test_per_asset_independence(self):
        detector = RegimeDetector()
        up_c, up_h, up_l = _trending_up_series()
        down_c, down_h, down_l = _trending_down_series()
        r1 = detector.classify("BTC/USD", up_c, up_h, up_l)
        r2 = detector.classify("ETH/USD", down_c, down_h, down_l)
        assert r1.regime != r2.regime
        assert r1.symbol == "BTC/USD"
        assert r2.symbol == "ETH/USD"
