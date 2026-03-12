"""Tests for the NormalizedCandle model."""

import unittest
from datetime import datetime, timezone, timedelta

from services.data_normalization.models import NormalizedCandle


class NormalizedCandleTest(unittest.TestCase):

    def _make_candle(self, **overrides):
        defaults = {
            "symbol": "BTC/USD",
            "exchange": "test",
            "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": 105.0,
            "volume": 1000.0,
        }
        defaults.update(overrides)
        return NormalizedCandle(**defaults)

    def test_valid_candle(self):
        candle = self._make_candle()
        self.assertEqual(candle.symbol, "BTC/USD")
        self.assertEqual(candle.exchange, "test")
        self.assertEqual(candle.open, 100.0)
        self.assertIsNone(candle.vwap)

    def test_vwap_optional(self):
        candle = self._make_candle(vwap=102.5)
        self.assertEqual(candle.vwap, 102.5)

    def test_naive_timestamp_gets_utc(self):
        naive_ts = datetime(2024, 1, 1)
        candle = self._make_candle(timestamp=naive_ts)
        self.assertEqual(candle.timestamp.tzinfo, timezone.utc)

    def test_non_utc_timestamp_converted(self):
        est = timezone(timedelta(hours=-5))
        est_ts = datetime(2024, 1, 1, 5, 0, 0, tzinfo=est)
        candle = self._make_candle(timestamp=est_ts)
        self.assertEqual(candle.timestamp.tzinfo, timezone.utc)
        self.assertEqual(candle.timestamp.hour, 10)  # 5 AM EST = 10 AM UTC

    def test_negative_price_rejected(self):
        with self.assertRaises(ValueError):
            self._make_candle(open=-1.0)
        with self.assertRaises(ValueError):
            self._make_candle(close=-0.01)

    def test_negative_volume_rejected(self):
        with self.assertRaises(ValueError):
            self._make_candle(volume=-1.0)

    def test_zero_price_allowed(self):
        candle = self._make_candle(open=0.0, high=0.0, low=0.0, close=0.0)
        self.assertEqual(candle.open, 0.0)

    def test_zero_volume_allowed(self):
        candle = self._make_candle(volume=0.0)
        self.assertEqual(candle.volume, 0.0)

    def test_high_less_than_low_rejected(self):
        with self.assertRaises(ValueError):
            self._make_candle(high=90.0, low=100.0)

    def test_high_equals_low_allowed(self):
        candle = self._make_candle(high=100.0, low=100.0)
        self.assertEqual(candle.high, candle.low)


if __name__ == "__main__":
    unittest.main()
