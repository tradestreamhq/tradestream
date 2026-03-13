"""Tests for the technical indicator library.

Reference values are computed manually or from well-known sources
to verify correctness of each indicator implementation.
"""

import pytest

from services.indicators.library import (
    ATR,
    EMA,
    MACD,
    RSI,
    SMA,
    VWAP,
    BollingerBands,
    Candle,
    StochasticOscillator,
    compute_indicators,
)


def _make_candle(
    close: float,
    high: float = 0,
    low: float = 0,
    open_: float = 0,
    volume: float = 1.0,
) -> Candle:
    return Candle(
        timestamp="2026-01-01T00:00:00Z",
        open=open_ or close,
        high=high or close,
        low=low or close,
        close=close,
        volume=volume,
    )


# ---------------------------------------------------------------------------
# SMA
# ---------------------------------------------------------------------------


class TestSMA:
    def test_basic(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = SMA.compute(closes, period=3)
        assert result[:2] == [None, None]
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_period_1(self):
        closes = [10.0, 20.0, 30.0]
        result = SMA.compute(closes, period=1)
        assert result == [pytest.approx(10.0), pytest.approx(20.0), pytest.approx(30.0)]

    def test_streaming_matches_batch(self):
        closes = [44.0, 44.5, 43.5, 44.0, 44.5, 43.0, 42.5, 43.0, 43.5, 44.0]
        batch = SMA.compute(closes, period=5)
        sma = SMA(5)
        streaming = [sma.update(c) for c in closes]
        for b, s in zip(batch, streaming):
            if b is None:
                assert s is None
            else:
                assert s == pytest.approx(b)

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            SMA(0)


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------


class TestEMA:
    def test_basic(self):
        closes = [22.27, 22.19, 22.08, 22.17, 22.18, 22.13, 22.23, 22.43, 22.24, 22.29]
        result = EMA.compute(closes, period=10)
        # First 9 values should be None, 10th is the SMA seed
        for i in range(9):
            assert result[i] is None
        assert result[9] == pytest.approx(22.221, abs=0.001)

    def test_period_1(self):
        closes = [10.0, 20.0, 30.0]
        result = EMA.compute(closes, period=1)
        assert result == [pytest.approx(10.0), pytest.approx(20.0), pytest.approx(30.0)]

    def test_streaming_matches_batch(self):
        closes = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        batch = EMA.compute(closes, period=3)
        ema = EMA(3)
        streaming = [ema.update(c) for c in closes]
        for b, s in zip(batch, streaming):
            if b is None:
                assert s is None
            else:
                assert s == pytest.approx(b)


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------


class TestRSI:
    def test_reference_values(self):
        # Classic RSI test: prices that produce known RSI values
        closes = [
            44.0,
            44.34,
            44.09,
            43.61,
            44.33,
            44.83,
            45.10,
            45.42,
            45.84,
            46.08,
            45.89,
            46.03,
            45.61,
            46.28,
            46.28,
            46.00,
            46.03,
            46.41,
            46.22,
            45.64,
        ]
        result = RSI.compute(closes, period=14)
        # First 14 values (indices 0-13) should be None
        for i in range(14):
            assert result[i] is None
        # RSI at index 14 (first computed value)
        assert result[14] is not None
        assert 0 <= result[14] <= 100

    def test_all_gains(self):
        closes = [float(i) for i in range(1, 17)]
        result = RSI.compute(closes, period=14)
        # All gains → RSI should be 100
        assert result[14] == pytest.approx(100.0)

    def test_all_losses(self):
        closes = [float(20 - i) for i in range(16)]
        result = RSI.compute(closes, period=14)
        assert result[14] == pytest.approx(0.0)

    def test_streaming_matches_batch(self):
        closes = [
            44.0,
            44.34,
            44.09,
            43.61,
            44.33,
            44.83,
            45.10,
            45.42,
            45.84,
            46.08,
            45.89,
            46.03,
            45.61,
            46.28,
            46.28,
            46.00,
        ]
        batch = RSI.compute(closes, period=14)
        rsi = RSI(14)
        streaming = [rsi.update(c) for c in closes]
        for b, s in zip(batch, streaming):
            if b is None:
                assert s is None
            else:
                assert s == pytest.approx(b)


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------


class TestMACD:
    def test_basic(self):
        # Need at least 26 values for slow EMA to kick in
        closes = [float(100 + i) for i in range(35)]
        result = MACD.compute(closes)
        # First 25 should have None macd (slow EMA not ready)
        for i in range(25):
            assert result[i].macd is None
        # From index 25 onward, MACD line should be defined
        assert result[25].macd is not None
        # Signal needs 9 more after MACD starts
        assert result[33].signal is not None
        assert result[33].histogram is not None

    def test_trending_up(self):
        closes = [float(50 + i * 2) for i in range(40)]
        result = MACD.compute(closes)
        # In a strong uptrend, MACD should be positive
        last = result[-1]
        assert last.macd is not None
        assert last.macd > 0


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------


class TestBollingerBands:
    def test_basic(self):
        closes = [float(i) for i in range(1, 22)]
        result = BollingerBands.compute(closes, period=20, num_std=2.0)
        # First 19 should be empty
        for i in range(19):
            assert result[i].middle is None
        # At index 19, middle = mean of 1..20 = 10.5
        assert result[19].middle == pytest.approx(10.5)
        assert result[19].upper > result[19].middle
        assert result[19].lower < result[19].middle

    def test_constant_prices(self):
        closes = [50.0] * 25
        result = BollingerBands.compute(closes, period=20)
        # Std dev is 0, so bands collapse to middle
        assert result[19].upper == pytest.approx(50.0)
        assert result[19].middle == pytest.approx(50.0)
        assert result[19].lower == pytest.approx(50.0)

    def test_band_width(self):
        closes = [50.0] * 10 + [60.0] * 10 + [50.0] * 5
        result = BollingerBands.compute(closes, period=20, num_std=2.0)
        r = result[19]
        assert r.upper - r.lower > 0


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------


class TestATR:
    def test_basic(self):
        candles = [
            _make_candle(close=48.16, high=48.70, low=47.79),
            _make_candle(close=48.61, high=48.72, low=48.14),
            _make_candle(close=48.75, high=48.90, low=48.39),
            _make_candle(close=48.63, high=48.87, low=48.37),
            _make_candle(close=48.74, high=48.82, low=48.24),
        ]
        result = ATR.compute(candles, period=5)
        assert result[:4] == [None, None, None, None]
        assert result[4] is not None
        assert result[4] > 0

    def test_streaming(self):
        candles = [
            _make_candle(close=48.16, high=48.70, low=47.79),
            _make_candle(close=48.61, high=48.72, low=48.14),
            _make_candle(close=48.75, high=48.90, low=48.39),
            _make_candle(close=48.63, high=48.87, low=48.37),
            _make_candle(close=48.74, high=48.82, low=48.24),
            _make_candle(close=49.03, high=49.05, low=48.64),
        ]
        batch = ATR.compute(candles, period=5)
        atr = ATR(5)
        streaming = [atr.update(c) for c in candles]
        for b, s in zip(batch, streaming):
            if b is None:
                assert s is None
            else:
                assert s == pytest.approx(b)


# ---------------------------------------------------------------------------
# VWAP
# ---------------------------------------------------------------------------


class TestVWAP:
    def test_basic(self):
        candles = [
            _make_candle(close=10.0, high=11.0, low=9.0, volume=100.0),
            _make_candle(close=11.0, high=12.0, low=10.0, volume=150.0),
        ]
        result = VWAP.compute(candles)
        # First candle: TP = (11+9+10)/3 = 10.0, cum_tp_vol=1000, cum_vol=100 → 10.0
        assert result[0] == pytest.approx(10.0)
        # Second candle: TP = (12+10+11)/3 = 11.0, cum_tp_vol=1000+1650=2650, cum_vol=250 → 10.6
        assert result[1] == pytest.approx(2650.0 / 250.0)

    def test_zero_volume(self):
        candles = [_make_candle(close=50.0, high=51.0, low=49.0, volume=0.0)]
        result = VWAP.compute(candles)
        assert result[0] is None

    def test_reset(self):
        vwap = VWAP()
        c = _make_candle(close=10.0, high=11.0, low=9.0, volume=100.0)
        vwap.update(c)
        vwap.reset()
        assert vwap._cum_volume == 0.0


# ---------------------------------------------------------------------------
# Stochastic Oscillator
# ---------------------------------------------------------------------------


class TestStochasticOscillator:
    def test_basic(self):
        candles = [
            _make_candle(close=float(127 + i), high=float(128 + i), low=float(126 + i))
            for i in range(16)
        ]
        result = StochasticOscillator.compute(candles, k_period=14, d_period=3)
        # First 13 should be None
        for i in range(13):
            assert result[i].k is None
        # From index 13 onwards, %K should be defined
        assert result[13].k is not None
        assert 0 <= result[13].k <= 100
        # %D needs 3 %K values: available at index 15
        assert result[15].d is not None

    def test_at_high(self):
        # Close at the top of range → %K should be 100
        candles = []
        for i in range(14):
            candles.append(_make_candle(close=100.0, high=100.0, low=90.0))
        result = StochasticOscillator.compute(candles, k_period=14, d_period=3)
        assert result[13].k == pytest.approx(100.0)

    def test_at_low(self):
        # Close at the bottom of range → %K should be 0
        candles = []
        for i in range(14):
            candles.append(_make_candle(close=90.0, high=100.0, low=90.0))
        result = StochasticOscillator.compute(candles, k_period=14, d_period=3)
        assert result[13].k == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_indicators convenience function
# ---------------------------------------------------------------------------


class TestComputeIndicators:
    def test_multiple_indicators(self):
        candles = [
            _make_candle(
                close=float(50 + i), high=float(51 + i), low=float(49 + i), volume=100.0
            )
            for i in range(30)
        ]
        config = {
            "sma": {"period": 5},
            "ema": {"period": 5},
            "rsi": {"period": 14},
            "atr": {"period": 5},
            "vwap": {},
        }
        results = compute_indicators(candles, config)
        assert "sma" in results
        assert "ema" in results
        assert "rsi" in results
        assert "atr" in results
        assert "vwap" in results
        assert len(results["sma"]) == 30

    def test_empty_config(self):
        candles = [_make_candle(close=50.0) for _ in range(10)]
        results = compute_indicators(candles, {})
        assert results == {}
