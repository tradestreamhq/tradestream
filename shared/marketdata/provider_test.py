"""Tests for the NormalizedCandle and AssetMetadata models."""

import unittest

from shared.marketdata.provider import AssetClass, AssetMetadata, NormalizedCandle


class NormalizedCandleTest(unittest.TestCase):
    def _make_candle(self, **overrides):
        defaults = dict(
            timestamp_ms=1700000000000,
            symbol="BTC/USD",
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=1000.0,
            asset_class=AssetClass.CRYPTO,
            source="test",
        )
        defaults.update(overrides)
        return NormalizedCandle(**defaults)

    def test_valid_candle(self):
        c = self._make_candle()
        self.assertTrue(c.is_valid())

    def test_invalid_high_less_than_low(self):
        c = self._make_candle(high=80.0, low=90.0)
        self.assertFalse(c.is_valid())

    def test_invalid_zero_open(self):
        c = self._make_candle(open=0.0)
        self.assertFalse(c.is_valid())

    def test_invalid_negative_volume(self):
        c = self._make_candle(volume=-1.0)
        self.assertFalse(c.is_valid())

    def test_zero_volume_is_valid(self):
        c = self._make_candle(volume=0.0)
        self.assertTrue(c.is_valid())

    def test_to_dict(self):
        c = self._make_candle()
        d = c.to_dict()
        self.assertEqual(d["currency_pair"], "BTC/USD")
        self.assertEqual(d["asset_class"], "crypto")
        self.assertEqual(d["open"], 100.0)
        self.assertEqual(d["source"], "test")

    def test_frozen_dataclass(self):
        c = self._make_candle()
        with self.assertRaises(AttributeError):
            c.open = 999.0


class AssetMetadataTest(unittest.TestCase):
    def test_defaults(self):
        m = AssetMetadata(
            symbol="AAPL",
            asset_class=AssetClass.STOCKS,
            exchange="NASDAQ",
        )
        self.assertEqual(m.quote_currency, "USD")
        self.assertEqual(m.tick_size, 0.01)
        self.assertEqual(m.margin_requirement, 1.0)

    def test_crypto_metadata(self):
        m = AssetMetadata(
            symbol="BTC/USD",
            asset_class=AssetClass.CRYPTO,
            exchange="binance",
            trading_hours_timezone="",
        )
        self.assertEqual(m.trading_hours_timezone, "")


class AssetClassTest(unittest.TestCase):
    def test_values(self):
        self.assertEqual(AssetClass.CRYPTO.value, "crypto")
        self.assertEqual(AssetClass.STOCKS.value, "stocks")
        self.assertEqual(AssetClass.FOREX.value, "forex")
        self.assertEqual(AssetClass.COMMODITIES.value, "commodities")


if __name__ == "__main__":
    unittest.main()
