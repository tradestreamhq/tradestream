"""Tests for StockMarketDataProvider."""

import unittest
from unittest.mock import MagicMock, patch

from shared.marketdata.provider import AssetClass, NormalizedCandle
from shared.marketdata.stock_provider import StockMarketDataProvider


class StockMarketDataProviderTest(unittest.TestCase):
    def setUp(self):
        self.provider = StockMarketDataProvider(
            api_key="test_key", symbols=["AAPL", "MSFT"]
        )

    def test_asset_class(self):
        self.assertEqual(self.provider.get_asset_class(), AssetClass.STOCKS)

    def test_supported_symbols(self):
        symbols = self.provider.get_supported_symbols()
        self.assertEqual(symbols, ["AAPL", "MSFT"])

    def test_is_symbol_supported(self):
        self.assertTrue(self.provider.is_symbol_supported("AAPL"))
        self.assertTrue(self.provider.is_symbol_supported("aapl"))
        self.assertFalse(self.provider.is_symbol_supported("GOOG"))

    def test_add_remove_symbol(self):
        self.provider.add_symbol("GOOG")
        self.assertTrue(self.provider.is_symbol_supported("GOOG"))
        self.provider.remove_symbol("GOOG")
        self.assertFalse(self.provider.is_symbol_supported("GOOG"))

    def test_get_asset_metadata(self):
        meta = self.provider.get_asset_metadata("AAPL")
        self.assertEqual(meta.asset_class, AssetClass.STOCKS)
        self.assertEqual(meta.symbol, "AAPL")
        self.assertEqual(meta.trading_hours_timezone, "America/New_York")
        self.assertEqual(meta.market_open, "09:30")
        self.assertEqual(meta.market_close, "16:00")
        self.assertEqual(meta.margin_requirement, 0.5)
        self.assertEqual(meta.lot_size, 1.0)

    @patch.object(StockMarketDataProvider, "_fetch_candles")
    def test_get_historical_candles(self, mock_fetch):
        mock_fetch.return_value = {
            "2024-01-15 10:00:00": {
                "1. open": "150.00",
                "2. high": "155.00",
                "3. low": "149.00",
                "4. close": "153.00",
                "5. volume": "1000000",
            }
        }

        candles = self.provider.get_historical_candles("AAPL", "1h", 0)
        self.assertEqual(len(candles), 1)
        c = candles[0]
        self.assertIsInstance(c, NormalizedCandle)
        self.assertEqual(c.asset_class, AssetClass.STOCKS)
        self.assertEqual(c.symbol, "AAPL")
        self.assertEqual(c.open, 150.0)
        self.assertEqual(c.close, 153.0)
        self.assertEqual(c.source, "alpha_vantage")

    @patch.object(StockMarketDataProvider, "_fetch_candles")
    def test_filters_by_since(self, mock_fetch):
        mock_fetch.return_value = {
            "2024-01-15 10:00:00": {
                "1. open": "150.00",
                "2. high": "155.00",
                "3. low": "149.00",
                "4. close": "153.00",
                "5. volume": "1000000",
            }
        }

        # since is far in the future, so no candles should match
        candles = self.provider.get_historical_candles("AAPL", "1h", 9999999999999)
        self.assertEqual(len(candles), 0)

    def test_unsupported_timeframe(self):
        candles = self.provider.get_historical_candles("AAPL", "3m", 0)
        self.assertEqual(len(candles), 0)

    def test_normalize_symbol(self):
        self.assertEqual(self.provider.normalize_symbol("aapl"), "AAPL")

    def test_parse_timestamp_datetime(self):
        ts = StockMarketDataProvider._parse_timestamp("2024-01-15 10:00:00")
        self.assertIsInstance(ts, int)
        self.assertGreater(ts, 0)

    def test_parse_timestamp_date(self):
        ts = StockMarketDataProvider._parse_timestamp("2024-01-15")
        self.assertIsInstance(ts, int)
        self.assertGreater(ts, 0)

    def test_parse_timestamp_invalid(self):
        with self.assertRaises(ValueError):
            StockMarketDataProvider._parse_timestamp("invalid")


if __name__ == "__main__":
    unittest.main()
