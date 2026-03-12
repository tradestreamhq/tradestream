"""Tests for exchange adapters."""

import unittest
from datetime import datetime, timezone

from services.data_normalization.exchange_adapters import (
    BinanceAdapter,
    CoinbaseAdapter,
    KrakenAdapter,
    get_adapter,
)
from services.data_normalization.models import NormalizedCandle


class BinanceAdapterTest(unittest.TestCase):

    def setUp(self):
        self.adapter = BinanceAdapter()

    def test_dict_format(self):
        raw = {
            "t": 1672531200000,
            "o": "16500.00",
            "h": "16600.00",
            "l": "16400.00",
            "c": "16550.00",
            "v": "1234.56",
            "s": "BTCUSDT",
        }
        candle = self.adapter.normalize(raw)
        self.assertIsInstance(candle, NormalizedCandle)
        self.assertEqual(candle.symbol, "BTCUSDT")
        self.assertEqual(candle.exchange, "binance")
        self.assertEqual(candle.open, 16500.0)
        self.assertEqual(candle.high, 16600.0)
        self.assertEqual(candle.low, 16400.0)
        self.assertEqual(candle.close, 16550.0)
        self.assertEqual(candle.volume, 1234.56)
        self.assertEqual(candle.timestamp, datetime(2023, 1, 1, tzinfo=timezone.utc))

    def test_dict_format_with_vwap(self):
        raw = {
            "t": 1672531200000,
            "o": "100.0", "h": "110.0", "l": "90.0", "c": "105.0",
            "v": "1000.0", "q": "102500.0", "s": "TEST",
        }
        candle = self.adapter.normalize(raw)
        self.assertAlmostEqual(candle.vwap, 102.5)

    def test_ohlcv_list_format(self):
        raw = [1672531200000, 16500.0, 16600.0, 16400.0, 16550.0, 1234.56, "BTCUSDT"]
        candle = self.adapter.normalize(raw)
        self.assertEqual(candle.symbol, "BTCUSDT")
        self.assertEqual(candle.open, 16500.0)

    def test_ohlcv_list_no_symbol(self):
        raw = [1672531200000, 100.0, 110.0, 90.0, 105.0, 500.0]
        candle = self.adapter.normalize(raw)
        self.assertEqual(candle.symbol, "UNKNOWN")

    def test_batch_skips_invalid(self):
        raws = [
            {"t": 1672531200000, "o": "100", "h": "110", "l": "90", "c": "105", "v": "10", "s": "X"},
            {"t": 1672531200000, "o": "-1", "h": "110", "l": "90", "c": "105", "v": "10", "s": "X"},
        ]
        results = self.adapter.normalize_batch(raws)
        self.assertEqual(len(results), 1)


class CoinbaseAdapterTest(unittest.TestCase):

    def setUp(self):
        self.adapter = CoinbaseAdapter()

    def test_normalize(self):
        raw = {
            "start": "1672531200",
            "open": "16500.00",
            "high": "16600.00",
            "low": "16400.00",
            "close": "16550.00",
            "volume": "1234.56",
            "product_id": "BTC-USD",
        }
        candle = self.adapter.normalize(raw)
        self.assertEqual(candle.symbol, "BTC-USD")
        self.assertEqual(candle.exchange, "coinbase")
        self.assertEqual(candle.timestamp, datetime(2023, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(candle.open, 16500.0)

    def test_missing_volume_defaults_zero(self):
        raw = {
            "start": "1672531200",
            "open": "100", "high": "110", "low": "90", "close": "105",
            "product_id": "ETH-USD",
        }
        candle = self.adapter.normalize(raw)
        self.assertEqual(candle.volume, 0.0)


class KrakenAdapterTest(unittest.TestCase):

    def setUp(self):
        self.adapter = KrakenAdapter()

    def test_list_format(self):
        raw = [1672531200, "16500.00", "16600.00", "16400.00", "16550.00", "16525.00", "1234.56", 42]
        candle = self.adapter.normalize(raw)
        self.assertEqual(candle.exchange, "kraken")
        self.assertEqual(candle.open, 16500.0)
        self.assertAlmostEqual(candle.vwap, 16525.0)
        self.assertEqual(candle.volume, 1234.56)

    def test_dict_format(self):
        raw = {
            "time": 1672531200,
            "open": "16500.00",
            "high": "16600.00",
            "low": "16400.00",
            "close": "16550.00",
            "vwap": "16525.00",
            "volume": "1234.56",
            "pair": "XXBTZUSD",
        }
        candle = self.adapter.normalize(raw)
        self.assertEqual(candle.symbol, "XXBTZUSD")
        self.assertEqual(candle.vwap, 16525.0)

    def test_list_no_vwap(self):
        raw = [1672531200, "100", "110", "90", "105", None, "500", 5]
        candle = self.adapter.normalize(raw)
        self.assertIsNone(candle.vwap)


class GetAdapterTest(unittest.TestCase):

    def test_known_exchanges(self):
        for name in ("binance", "coinbase", "kraken"):
            adapter = get_adapter(name)
            self.assertEqual(adapter.exchange_name, name)

    def test_case_insensitive(self):
        adapter = get_adapter("Binance")
        self.assertEqual(adapter.exchange_name, "binance")

    def test_unknown_exchange_raises(self):
        with self.assertRaises(ValueError):
            get_adapter("unknown_exchange")


if __name__ == "__main__":
    unittest.main()
