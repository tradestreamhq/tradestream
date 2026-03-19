"""Tests for the CommoditiesMarketDataProvider."""

import unittest
from unittest.mock import patch, MagicMock

from shared.marketdata.commodities_provider import CommoditiesMarketDataProvider
from shared.marketdata.provider import AssetClass, NormalizedCandle


class CommoditiesMarketDataProviderTest(unittest.TestCase):
    def setUp(self):
        self.provider = CommoditiesMarketDataProvider(
            api_key="test-key",
            symbols=["WTI", "BRENT"],
        )

    def test_get_asset_class(self):
        self.assertEqual(self.provider.get_asset_class(), AssetClass.COMMODITIES)

    def test_get_supported_symbols(self):
        symbols = self.provider.get_supported_symbols()
        self.assertEqual(symbols, ["BRENT", "WTI"])

    def test_is_symbol_supported(self):
        self.assertTrue(self.provider.is_symbol_supported("WTI"))
        self.assertTrue(self.provider.is_symbol_supported("wti"))
        self.assertFalse(self.provider.is_symbol_supported("GOLD"))

    def test_add_remove_symbol(self):
        self.provider.add_symbol("COPPER")
        self.assertTrue(self.provider.is_symbol_supported("COPPER"))
        self.provider.remove_symbol("COPPER")
        self.assertFalse(self.provider.is_symbol_supported("COPPER"))

    def test_get_asset_metadata(self):
        meta = self.provider.get_asset_metadata("WTI")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.symbol, "WTI")
        self.assertEqual(meta.asset_class, AssetClass.COMMODITIES)
        self.assertEqual(meta.quote_currency, "USD")

    def test_normalize_symbol(self):
        self.assertEqual(self.provider.normalize_symbol("wti"), "WTI")

    @patch("shared.marketdata.commodities_provider.requests.get")
    def test_get_historical_candles_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"date": "2024-01-02", "value": "72.50"},
                {"date": "2024-01-03", "value": "73.25"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        candles = self.provider.get_historical_candles("WTI", "1d", 0, limit=10)
        self.assertEqual(len(candles), 2)
        self.assertIsInstance(candles[0], NormalizedCandle)
        self.assertEqual(candles[0].asset_class, AssetClass.COMMODITIES)
        self.assertEqual(candles[0].source, "alpha_vantage")

    @patch("shared.marketdata.commodities_provider.requests.get")
    def test_get_historical_candles_skips_missing_values(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"date": "2024-01-02", "value": "."},
                {"date": "2024-01-03", "value": "73.25"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        candles = self.provider.get_historical_candles("WTI", "1d", 0, limit=10)
        self.assertEqual(len(candles), 1)

    def test_unsupported_timeframe(self):
        candles = self.provider.get_historical_candles("WTI", "1m", 0)
        self.assertEqual(candles, [])

    def test_unsupported_symbol_returns_empty(self):
        candles = self.provider.get_historical_candles("UNKNOWN", "1d", 0)
        self.assertEqual(candles, [])


if __name__ == "__main__":
    unittest.main()
