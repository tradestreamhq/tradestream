"""Tests for ForexMarketDataProvider."""

import unittest
from unittest.mock import patch

from shared.marketdata.provider import AssetClass, NormalizedCandle
from shared.marketdata.forex_provider import ForexMarketDataProvider


class ForexMarketDataProviderTest(unittest.TestCase):
    def setUp(self):
        self.provider = ForexMarketDataProvider(
            api_key="test_key", pairs=["EUR/USD", "GBP/USD"]
        )

    def test_asset_class(self):
        self.assertEqual(self.provider.get_asset_class(), AssetClass.FOREX)

    def test_supported_symbols(self):
        symbols = self.provider.get_supported_symbols()
        self.assertEqual(symbols, ["EUR/USD", "GBP/USD"])

    def test_is_symbol_supported(self):
        self.assertTrue(self.provider.is_symbol_supported("EUR/USD"))
        self.assertTrue(self.provider.is_symbol_supported("EURUSD"))
        self.assertFalse(self.provider.is_symbol_supported("AUD/NZD"))

    def test_add_remove_pair(self):
        self.provider.add_pair("USD/JPY")
        self.assertTrue(self.provider.is_symbol_supported("USD/JPY"))
        self.provider.remove_pair("USD/JPY")
        self.assertFalse(self.provider.is_symbol_supported("USD/JPY"))

    def test_normalize_pair(self):
        self.assertEqual(
            ForexMarketDataProvider._normalize_pair("eurusd"), "EUR/USD"
        )
        self.assertEqual(
            ForexMarketDataProvider._normalize_pair("EUR/USD"), "EUR/USD"
        )

    def test_get_asset_metadata(self):
        meta = self.provider.get_asset_metadata("EUR/USD")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.asset_class, AssetClass.FOREX)
        self.assertEqual(meta.base_currency, "EUR")
        self.assertEqual(meta.quote_currency, "USD")
        self.assertEqual(meta.tick_size, 0.0001)
        self.assertEqual(meta.price_precision, 5)
        self.assertEqual(meta.margin_requirement, 0.02)

    def test_get_asset_metadata_jpy_pair(self):
        self.provider.add_pair("USD/JPY")
        meta = self.provider.get_asset_metadata("USD/JPY")
        self.assertEqual(meta.tick_size, 0.01)
        self.assertEqual(meta.price_precision, 3)

    def test_get_asset_metadata_invalid(self):
        meta = self.provider.get_asset_metadata("X")
        self.assertIsNone(meta)

    @patch.object(ForexMarketDataProvider, "_fetch_candles")
    def test_get_historical_candles(self, mock_fetch):
        mock_fetch.return_value = {
            "2024-01-15 10:00:00": {
                "1. open": "1.09500",
                "2. high": "1.09700",
                "3. low": "1.09400",
                "4. close": "1.09600",
            }
        }

        candles = self.provider.get_historical_candles("EUR/USD", "1h", 0)
        self.assertEqual(len(candles), 1)
        c = candles[0]
        self.assertIsInstance(c, NormalizedCandle)
        self.assertEqual(c.asset_class, AssetClass.FOREX)
        self.assertEqual(c.symbol, "EUR/USD")
        self.assertEqual(c.volume, 0.0)  # FX has no volume from AV
        self.assertEqual(c.source, "alpha_vantage")

    def test_invalid_pair_format(self):
        candles = self.provider.get_historical_candles("X", "1h", 0)
        self.assertEqual(len(candles), 0)

    def test_unsupported_timeframe(self):
        candles = self.provider.get_historical_candles("EUR/USD", "3m", 0)
        self.assertEqual(len(candles), 0)


if __name__ == "__main__":
    unittest.main()
