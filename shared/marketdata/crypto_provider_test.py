"""Tests for CryptoMarketDataProvider."""

import unittest
from unittest.mock import MagicMock, patch

from shared.marketdata.provider import AssetClass, NormalizedCandle
from shared.marketdata.crypto_provider import CryptoMarketDataProvider


class CryptoMarketDataProviderTest(unittest.TestCase):
    @patch("shared.marketdata.crypto_provider.CCXTCandleClient")
    def setUp(self, mock_ccxt_cls):
        self.mock_client = MagicMock()
        mock_ccxt_cls.return_value = self.mock_client
        self.mock_client.available_symbols = {"BTC/USD", "ETH/USD"}
        self.provider = CryptoMarketDataProvider("binance")

    def test_asset_class(self):
        self.assertEqual(self.provider.get_asset_class(), AssetClass.CRYPTO)

    def test_get_supported_symbols(self):
        symbols = self.provider.get_supported_symbols()
        self.assertIn("BTC/USD", symbols)
        self.assertIn("ETH/USD", symbols)

    def test_is_symbol_supported(self):
        self.mock_client.is_symbol_supported.return_value = True
        self.assertTrue(self.provider.is_symbol_supported("BTC/USD"))

    def test_get_historical_candles(self):
        self.mock_client.get_historical_candles.return_value = [
            {
                "timestamp_ms": 1700000000000,
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 5000.0,
                "currency_pair": "BTC/USD",
                "exchange": "binance",
            }
        ]

        candles = self.provider.get_historical_candles("BTC/USD", "1h", 1699999000000)
        self.assertEqual(len(candles), 1)
        self.assertIsInstance(candles[0], NormalizedCandle)
        self.assertEqual(candles[0].asset_class, AssetClass.CRYPTO)
        self.assertEqual(candles[0].source, "binance")
        self.assertEqual(candles[0].symbol, "BTC/USD")

    def test_skips_invalid_candles(self):
        self.mock_client.get_historical_candles.return_value = [
            {
                "timestamp_ms": 1700000000000,
                "open": 0.0,  # Invalid
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 5000.0,
                "currency_pair": "BTC/USD",
                "exchange": "binance",
            }
        ]

        candles = self.provider.get_historical_candles("BTC/USD", "1h", 1699999000000)
        self.assertEqual(len(candles), 0)

    def test_get_asset_metadata(self):
        self.mock_client.is_symbol_supported.return_value = True
        self.mock_client._normalize_symbol.return_value = "BTC/USD"

        meta = self.provider.get_asset_metadata("BTC/USD")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.asset_class, AssetClass.CRYPTO)
        self.assertEqual(meta.base_currency, "BTC")
        self.assertEqual(meta.quote_currency, "USD")
        # Crypto is 24/7
        self.assertEqual(meta.trading_hours_timezone, "")

    def test_get_asset_metadata_unsupported(self):
        self.mock_client.is_symbol_supported.return_value = False
        meta = self.provider.get_asset_metadata("INVALID")
        self.assertIsNone(meta)


if __name__ == "__main__":
    unittest.main()
