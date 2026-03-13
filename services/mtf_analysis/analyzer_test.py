"""Tests for the Multi-Timeframe Analyzer."""

from unittest.mock import MagicMock

import pytest

from services.mtf_analysis.analyzer import (
    TIMEFRAMES,
    ConfluenceResult,
    MultiTimeframeAnalyzer,
    Signal,
    TimeframeAnalysis,
    _MIN_CANDLES,
)


def _make_candles(prices, base_time="2026-01-01T00:00:00Z"):
    """Generate candle dicts from a list of close prices."""
    candles = []
    for i, p in enumerate(prices):
        candles.append(
            {
                "timestamp": f"2026-01-01T00:{i:02d}:00Z",
                "open": p * 0.999,
                "high": p * 1.005,
                "low": p * 0.995,
                "close": p,
                "volume": 100.0,
            }
        )
    return candles


def _uptrend_prices(n=30, start=100.0, step=1.0):
    return [start + i * step for i in range(n)]


def _downtrend_prices(n=30, start=200.0, step=1.0):
    return [start - i * step for i in range(n)]


def _flat_prices(n=30, price=100.0):
    return [price] * n


@pytest.fixture
def influx():
    return MagicMock()


@pytest.fixture
def analyzer(influx):
    return MultiTimeframeAnalyzer(influx)


class TestSMA:
    def test_sma_basic(self, analyzer):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert analyzer._compute_sma(closes, 3) == 4.0

    def test_sma_insufficient_data(self, analyzer):
        assert analyzer._compute_sma([1.0, 2.0], 5) is None


class TestEMA:
    def test_ema_basic(self, analyzer):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        ema = analyzer._compute_ema(closes, 5)
        assert ema is not None
        assert ema > 5.0  # EMA should weight recent values more

    def test_ema_insufficient_data(self, analyzer):
        assert analyzer._compute_ema([1.0], 5) is None


class TestRSI:
    def test_rsi_uptrend(self, analyzer):
        closes = _uptrend_prices(30)
        rsi = analyzer._compute_rsi(closes)
        assert rsi is not None
        assert rsi > 70  # Strong uptrend -> high RSI

    def test_rsi_downtrend(self, analyzer):
        closes = _downtrend_prices(30)
        rsi = analyzer._compute_rsi(closes)
        assert rsi is not None
        assert rsi < 30  # Strong downtrend -> low RSI

    def test_rsi_insufficient_data(self, analyzer):
        assert analyzer._compute_rsi([1.0, 2.0]) is None


class TestAnalyzeCandles:
    def test_bullish_signal_on_uptrend(self, analyzer):
        candles = _make_candles(_uptrend_prices(30))
        result = analyzer._analyze_candles(candles, "1h")
        assert result.signal == Signal.BULLISH
        assert result.strength > 0
        assert result.timeframe == "1h"

    def test_bearish_signal_on_downtrend(self, analyzer):
        candles = _make_candles(_downtrend_prices(30))
        result = analyzer._analyze_candles(candles, "1h")
        assert result.signal == Signal.BEARISH
        assert result.strength > 0

    def test_neutral_on_flat(self, analyzer):
        candles = _make_candles(_flat_prices(30))
        result = analyzer._analyze_candles(candles, "1h")
        assert result.signal == Signal.NEUTRAL

    def test_insufficient_candles(self, analyzer):
        candles = _make_candles([100.0] * 5)
        result = analyzer._analyze_candles(candles, "1h")
        assert result.signal == Signal.NEUTRAL
        assert result.strength == 0.0

    def test_indicators_populated(self, analyzer):
        candles = _make_candles(_uptrend_prices(30))
        result = analyzer._analyze_candles(candles, "1h")
        assert result.indicators["sma_10"] is not None
        assert result.indicators["sma_20"] is not None
        assert result.indicators["ema_10"] is not None
        assert result.indicators["ema_20"] is not None
        assert result.indicators["rsi_14"] is not None
        assert result.indicators["price"] is not None

    def test_candle_count(self, analyzer):
        candles = _make_candles(_uptrend_prices(25))
        result = analyzer._analyze_candles(candles, "5m")
        assert result.candle_count == 25


class TestGetSnapshot:
    def test_returns_all_timeframes(self, analyzer, influx):
        influx.get_candles.return_value = _make_candles(_uptrend_prices(30))
        snapshot = analyzer.get_snapshot("BTC/USD")
        assert set(snapshot.keys()) == set(TIMEFRAMES)
        for tf in TIMEFRAMES:
            assert isinstance(snapshot[tf], TimeframeAnalysis)

    def test_custom_timeframes(self, analyzer, influx):
        influx.get_candles.return_value = _make_candles(_uptrend_prices(30))
        snapshot = analyzer.get_snapshot("BTC/USD", ["1h", "4h"])
        assert set(snapshot.keys()) == {"1h", "4h"}

    def test_calls_influx_per_timeframe(self, analyzer, influx):
        influx.get_candles.return_value = _make_candles(_uptrend_prices(30))
        analyzer.get_snapshot("BTC/USD", ["1m", "5m", "1h"])
        assert influx.get_candles.call_count == 3


class TestGetConfluence:
    def test_bullish_confluence(self, analyzer, influx):
        influx.get_candles.return_value = _make_candles(_uptrend_prices(30))
        result = analyzer.get_confluence("BTC/USD")
        assert isinstance(result, ConfluenceResult)
        assert result.score > 0
        assert result.signal == Signal.BULLISH
        assert len(result.agreeing_timeframes) > 0
        assert result.pair == "BTC/USD"

    def test_bearish_confluence(self, analyzer, influx):
        influx.get_candles.return_value = _make_candles(_downtrend_prices(30))
        result = analyzer.get_confluence("BTC/USD")
        assert result.score < 0
        assert result.signal == Signal.BEARISH

    def test_neutral_confluence(self, analyzer, influx):
        influx.get_candles.return_value = _make_candles(_flat_prices(30))
        result = analyzer.get_confluence("BTC/USD")
        assert result.signal == Signal.NEUTRAL

    def test_total_timeframes_count(self, analyzer, influx):
        influx.get_candles.return_value = _make_candles(_uptrend_prices(30))
        result = analyzer.get_confluence("BTC/USD", ["1h", "4h", "1d"])
        assert result.total_timeframes == 3

    def test_score_bounded(self, analyzer, influx):
        influx.get_candles.return_value = _make_candles(_uptrend_prices(50))
        result = analyzer.get_confluence("BTC/USD")
        assert -1.0 <= result.score <= 1.0
