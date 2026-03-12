"""Tests for the normalizer module."""

import unittest

from services.data_normalization.normalizer import normalize_candles, normalize_single
from services.data_normalization.models import NormalizedCandle


class NormalizeCandlesTest(unittest.TestCase):

    def test_binance_batch(self):
        raws = [
            {"t": 1672531200000, "o": "100", "h": "110", "l": "90", "c": "105", "v": "1000", "s": "BTCUSDT"},
            {"t": 1672534800000, "o": "105", "h": "115", "l": "95", "c": "110", "v": "2000", "s": "BTCUSDT"},
        ]
        results = normalize_candles("binance", raws)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], NormalizedCandle)
        self.assertEqual(results[0].exchange, "binance")

    def test_coinbase_batch(self):
        raws = [
            {"start": "1672531200", "open": "100", "high": "110", "low": "90", "close": "105", "volume": "500", "product_id": "BTC-USD"},
        ]
        results = normalize_candles("coinbase", raws)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].exchange, "coinbase")

    def test_kraken_batch(self):
        raws = [
            [1672531200, "100", "110", "90", "105", "102", "500", 10],
        ]
        results = normalize_candles("kraken", raws)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].exchange, "kraken")

    def test_invalid_candles_skipped(self):
        raws = [
            {"t": 1672531200000, "o": "100", "h": "110", "l": "90", "c": "105", "v": "1000", "s": "X"},
            {"t": 1672531200000, "o": "100", "h": "50", "l": "90", "c": "105", "v": "1000", "s": "X"},  # high < low
        ]
        results = normalize_candles("binance", raws)
        self.assertEqual(len(results), 1)

    def test_unknown_exchange_raises(self):
        with self.assertRaises(ValueError):
            normalize_candles("nonexistent", [])


class NormalizeSingleTest(unittest.TestCase):

    def test_single_binance(self):
        raw = {"t": 1672531200000, "o": "100", "h": "110", "l": "90", "c": "105", "v": "1000", "s": "ETHUSDT"}
        candle = normalize_single("binance", raw)
        self.assertEqual(candle.symbol, "ETHUSDT")

    def test_single_invalid_raises(self):
        raw = {"t": 1672531200000, "o": "-1", "h": "110", "l": "90", "c": "105", "v": "1000", "s": "X"}
        with self.assertRaises(ValueError):
            normalize_single("binance", raw)


if __name__ == "__main__":
    unittest.main()
