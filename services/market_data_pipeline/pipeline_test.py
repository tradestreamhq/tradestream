"""Comprehensive tests for the market data pipeline."""

import json
import os
import tempfile
import unittest

from services.market_data_pipeline.schema import (
    OHLCV,
    Trade,
    OrderBookSnapshot,
    PriceLevel,
)
from services.market_data_pipeline.adapters import (
    BinanceAdapter,
    CoinbaseAdapter,
    get_adapter,
)
from services.market_data_pipeline.validation import (
    OHLCVValidator,
    TradeValidator,
    ValidationResult,
)
from services.market_data_pipeline.replay import FileReplaySource


TESTDATA_DIR = os.path.join(os.path.dirname(__file__), "testdata")


# --- Schema Tests ---


class TestOHLCV(unittest.TestCase):
    def test_to_dict(self):
        ohlcv = OHLCV(
            timestamp_ms=1640995200000,
            symbol="BTC/USD",
            exchange="binance",
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=100.5,
        )
        d = ohlcv.to_dict()
        self.assertEqual(d["timestamp_ms"], 1640995200000)
        self.assertEqual(d["symbol"], "BTC/USD")
        self.assertEqual(d["open"], 50000.0)
        self.assertEqual(d["volume"], 100.5)
        self.assertEqual(d["interval"], "1m")

    def test_frozen(self):
        ohlcv = OHLCV(
            timestamp_ms=1, symbol="X", exchange="e",
            open=1, high=2, low=0.5, close=1.5, volume=10,
        )
        with self.assertRaises(AttributeError):
            ohlcv.open = 999


class TestTrade(unittest.TestCase):
    def test_to_dict(self):
        trade = Trade(
            timestamp_ms=1640995200000,
            symbol="BTC/USD",
            exchange="binance",
            price=50000.0,
            volume=1.5,
            trade_id="t1",
            side="buy",
        )
        d = trade.to_dict()
        self.assertEqual(d["trade_id"], "t1")
        self.assertEqual(d["side"], "buy")


class TestOrderBookSnapshot(unittest.TestCase):
    def test_to_dict(self):
        ob = OrderBookSnapshot(
            timestamp_ms=1640995200000,
            symbol="BTC/USD",
            exchange="binance",
            bids=(PriceLevel(50000.0, 1.0), PriceLevel(49900.0, 2.0)),
            asks=(PriceLevel(50100.0, 0.5), PriceLevel(50200.0, 1.5)),
        )
        d = ob.to_dict()
        self.assertEqual(len(d["bids"]), 2)
        self.assertEqual(d["bids"][0]["price"], 50000.0)
        self.assertEqual(d["asks"][1]["size"], 1.5)


# --- Adapter Tests ---


class TestBinanceAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = BinanceAdapter()

    def test_exchange_name(self):
        self.assertEqual(self.adapter.exchange_name, "binance")

    def test_normalize_ohlcv_list_format(self):
        raw = [1640995200000, "50000.0", "51000.0", "49000.0", "50500.0", "100.5",
               1640995259999, "5050250.0", 1500, "55.2", "2787600.0", "0", "BTC/USD"]
        result = self.adapter.normalize_ohlcv(raw)
        self.assertEqual(result.timestamp_ms, 1640995200000)
        self.assertEqual(result.open, 50000.0)
        self.assertEqual(result.high, 51000.0)
        self.assertEqual(result.low, 49000.0)
        self.assertEqual(result.close, 50500.0)
        self.assertEqual(result.volume, 100.5)
        self.assertEqual(result.symbol, "BTC/USD")
        self.assertEqual(result.exchange, "binance")

    def test_normalize_ohlcv_dict_format(self):
        raw = {
            "timestamp": 1640995200000,
            "symbol": "BTC/USD",
            "open": "50000",
            "high": "51000",
            "low": "49000",
            "close": "50500",
            "volume": "100.5",
        }
        result = self.adapter.normalize_ohlcv(raw)
        self.assertEqual(result.open, 50000.0)
        self.assertEqual(result.exchange, "binance")

    def test_normalize_trade(self):
        raw = {
            "id": 100001,
            "price": "50100.00",
            "qty": "0.5",
            "time": 1640995200100,
            "isBuyerMaker": False,
            "symbol": "BTC/USD",
        }
        result = self.adapter.normalize_trade(raw)
        self.assertEqual(result.price, 50100.0)
        self.assertEqual(result.volume, 0.5)
        self.assertEqual(result.side, "buy")
        self.assertEqual(result.trade_id, "100001")

    def test_normalize_trade_seller(self):
        raw = {
            "id": 100002,
            "price": "50150.00",
            "qty": "1.2",
            "time": 1640995200200,
            "isBuyerMaker": True,
            "symbol": "BTC/USD",
        }
        result = self.adapter.normalize_trade(raw)
        self.assertEqual(result.side, "sell")

    def test_normalize_order_book(self):
        raw = {
            "timestamp": 1640995200000,
            "symbol": "BTC/USD",
            "bids": [["50000.0", "1.0"], ["49900.0", "2.0"]],
            "asks": [["50100.0", "0.5"], ["50200.0", "1.5"]],
        }
        result = self.adapter.normalize_order_book(raw)
        self.assertEqual(len(result.bids), 2)
        self.assertEqual(result.bids[0].price, 50000.0)
        self.assertEqual(result.asks[1].size, 1.5)

    def test_normalize_ohlcv_batch_skips_invalid(self):
        records = [
            {"timestamp": 1640995200000, "symbol": "X", "open": "1", "high": "2",
             "low": "0.5", "close": "1.5", "volume": "10"},
            {"bad_key": "missing fields"},
        ]
        results = self.adapter.normalize_ohlcv_batch(records)
        self.assertEqual(len(results), 1)


class TestCoinbaseAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = CoinbaseAdapter()

    def test_exchange_name(self):
        self.assertEqual(self.adapter.exchange_name, "coinbase")

    def test_normalize_ohlcv_list_format(self):
        # Coinbase format: [timestamp_s, low, high, open, close, volume]
        raw = [1640995200, 49100.0, 51100.0, 50100.0, 50600.0, 78.3, "BTC-USD"]
        result = self.adapter.normalize_ohlcv(raw)
        self.assertEqual(result.timestamp_ms, 1640995200000)  # Converted from s to ms
        self.assertEqual(result.open, 50100.0)  # Index 3
        self.assertEqual(result.high, 51100.0)  # Index 2
        self.assertEqual(result.low, 49100.0)   # Index 1
        self.assertEqual(result.close, 50600.0)  # Index 4
        self.assertEqual(result.volume, 78.3)
        self.assertEqual(result.exchange, "coinbase")

    def test_normalize_ohlcv_dict_seconds_timestamp(self):
        raw = {
            "timestamp": 1640995200,
            "symbol": "BTC-USD",
            "open": 50100.0,
            "high": 51100.0,
            "low": 49100.0,
            "close": 50600.0,
            "volume": 78.3,
        }
        result = self.adapter.normalize_ohlcv(raw)
        self.assertEqual(result.timestamp_ms, 1640995200000)

    def test_normalize_trade_iso_timestamp(self):
        raw = {
            "trade_id": 200001,
            "price": "50120.00",
            "size": "0.3",
            "time": "2022-01-01T00:00:00.100Z",
            "side": "buy",
            "product_id": "BTC-USD",
        }
        result = self.adapter.normalize_trade(raw)
        self.assertEqual(result.price, 50120.0)
        self.assertEqual(result.volume, 0.3)
        self.assertEqual(result.side, "buy")
        self.assertEqual(result.symbol, "BTC-USD")
        self.assertGreater(result.timestamp_ms, 0)

    def test_normalize_order_book(self):
        raw = {
            "timestamp": 1640995200000,
            "symbol": "BTC-USD",
            "bids": [["50000.0", "1.0"]],
            "asks": [["50100.0", "0.5"]],
        }
        result = self.adapter.normalize_order_book(raw)
        self.assertEqual(result.exchange, "coinbase")
        self.assertEqual(len(result.bids), 1)


class TestAdapterRegistry(unittest.TestCase):
    def test_get_binance(self):
        adapter = get_adapter("binance")
        self.assertIsInstance(adapter, BinanceAdapter)

    def test_get_coinbase(self):
        adapter = get_adapter("coinbase")
        self.assertIsInstance(adapter, CoinbaseAdapter)

    def test_get_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_adapter("unknown_exchange")

    def test_case_insensitive(self):
        adapter = get_adapter("BINANCE")
        self.assertIsInstance(adapter, BinanceAdapter)


# --- Validation Tests ---


class TestOHLCVValidator(unittest.TestCase):
    def setUp(self):
        self.validator = OHLCVValidator(
            max_price_change_pct=50.0,
            max_gap_ms=120_000,
        )

    def _make_ohlcv(self, **kwargs):
        defaults = {
            "timestamp_ms": 1640995200000,
            "symbol": "BTC/USD",
            "exchange": "test",
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "volume": 100.0,
        }
        defaults.update(kwargs)
        return OHLCV(**defaults)

    def test_valid_record(self):
        result = self.validator.validate(self._make_ohlcv())
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 0)

    def test_high_less_than_low(self):
        result = self.validator.validate(self._make_ohlcv(high=48000.0, low=49000.0))
        self.assertFalse(result.is_valid)

    def test_non_positive_price(self):
        result = self.validator.validate(self._make_ohlcv(open=0))
        self.assertFalse(result.is_valid)

    def test_negative_volume(self):
        result = self.validator.validate(self._make_ohlcv(volume=-1))
        self.assertFalse(result.is_valid)

    def test_non_positive_timestamp(self):
        result = self.validator.validate(self._make_ohlcv(timestamp_ms=0))
        self.assertFalse(result.is_valid)

    def test_gap_detection(self):
        self.validator.validate(self._make_ohlcv(timestamp_ms=1000000))
        result = self.validator.validate(self._make_ohlcv(timestamp_ms=1200000))
        # Gap of 200s > 120s threshold
        self.assertTrue(result.is_valid)
        self.assertTrue(any("gap" in w for w in result.warnings))

    def test_timestamp_backwards(self):
        self.validator.validate(self._make_ohlcv(timestamp_ms=2000000))
        result = self.validator.validate(self._make_ohlcv(timestamp_ms=1000000))
        self.assertFalse(result.is_valid)

    def test_spike_detection(self):
        self.validator.validate(self._make_ohlcv(close=100.0))
        result = self.validator.validate(self._make_ohlcv(
            timestamp_ms=1640995260000, open=200.0, high=210.0, low=190.0, close=205.0
        ))
        self.assertTrue(result.is_valid)
        self.assertTrue(any("spike" in w for w in result.warnings))

    def test_stale_data_warning(self):
        result = self.validator.validate(
            self._make_ohlcv(open=100, high=100, low=100, close=100)
        )
        self.assertTrue(result.is_valid)
        self.assertTrue(any("stale" in w for w in result.warnings))

    def test_validate_batch(self):
        records = [
            self._make_ohlcv(timestamp_ms=3000000),
            self._make_ohlcv(timestamp_ms=1000000),
            self._make_ohlcv(timestamp_ms=2000000),
            self._make_ohlcv(timestamp_ms=4000000, high=1.0, low=5.0),  # invalid
        ]
        valid = self.validator.validate_batch(records)
        self.assertEqual(len(valid), 3)
        # Should be sorted by timestamp
        self.assertEqual(valid[0].timestamp_ms, 1000000)
        self.assertEqual(valid[2].timestamp_ms, 3000000)

    def test_reset(self):
        self.validator.validate(self._make_ohlcv(timestamp_ms=5000000))
        self.validator.reset()
        # After reset, backwards timestamp should be fine (no previous record)
        result = self.validator.validate(self._make_ohlcv(timestamp_ms=1000000))
        self.assertTrue(result.is_valid)


class TestTradeValidator(unittest.TestCase):
    def setUp(self):
        self.validator = TradeValidator(max_price_change_pct=50.0)

    def _make_trade(self, **kwargs):
        defaults = {
            "timestamp_ms": 1640995200000,
            "symbol": "BTC/USD",
            "exchange": "test",
            "price": 50000.0,
            "volume": 1.0,
            "trade_id": "t1",
        }
        defaults.update(kwargs)
        return Trade(**defaults)

    def test_valid_trade(self):
        result = self.validator.validate(self._make_trade())
        self.assertTrue(result.is_valid)

    def test_non_positive_price(self):
        result = self.validator.validate(self._make_trade(price=0))
        self.assertFalse(result.is_valid)

    def test_non_positive_volume(self):
        result = self.validator.validate(self._make_trade(volume=0))
        self.assertFalse(result.is_valid)

    def test_spike_detection(self):
        self.validator.validate(self._make_trade(price=100.0))
        result = self.validator.validate(self._make_trade(price=200.0))
        self.assertTrue(any("spike" in w for w in result.warnings))

    def test_validate_batch_filters_invalid(self):
        records = [
            self._make_trade(timestamp_ms=1000000, price=100.0),
            self._make_trade(timestamp_ms=2000000, price=0),  # invalid
            self._make_trade(timestamp_ms=3000000, price=110.0),
        ]
        valid = self.validator.validate_batch(records)
        self.assertEqual(len(valid), 2)


# --- Replay Tests ---


class TestFileReplaySource(unittest.TestCase):
    def test_replay_binance_ohlcv_from_file(self):
        source = FileReplaySource(BinanceAdapter(), validate=True)
        path = os.path.join(TESTDATA_DIR, "binance_ohlcv.json")
        records = source.replay_ohlcv(path)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].exchange, "binance")
        self.assertEqual(records[0].open, 50000.0)
        # Should be sorted by timestamp
        self.assertLessEqual(records[0].timestamp_ms, records[1].timestamp_ms)

    def test_replay_coinbase_ohlcv_from_file(self):
        source = FileReplaySource(CoinbaseAdapter(), validate=True)
        path = os.path.join(TESTDATA_DIR, "coinbase_ohlcv.json")
        records = source.replay_ohlcv(path)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].exchange, "coinbase")
        # Coinbase timestamps converted from seconds to ms
        self.assertEqual(records[0].timestamp_ms, 1640995200000)

    def test_replay_binance_trades_from_file(self):
        source = FileReplaySource(BinanceAdapter(), validate=True)
        path = os.path.join(TESTDATA_DIR, "binance_trades.json")
        records = source.replay_trades(path)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].side, "buy")
        self.assertEqual(records[1].side, "sell")

    def test_replay_coinbase_trades_from_file(self):
        source = FileReplaySource(CoinbaseAdapter(), validate=True)
        path = os.path.join(TESTDATA_DIR, "coinbase_trades.json")
        records = source.replay_trades(path)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].symbol, "BTC-USD")

    def test_replay_ohlcv_iter(self):
        source = FileReplaySource(BinanceAdapter(), validate=True)
        path = os.path.join(TESTDATA_DIR, "binance_ohlcv.json")
        records = list(source.replay_ohlcv_iter(path))
        self.assertEqual(len(records), 3)

    def test_replay_ndjson_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            for record in [
                {"timestamp": 1000000, "symbol": "X", "open": "1", "high": "2",
                 "low": "0.5", "close": "1.5", "volume": "10"},
                {"timestamp": 2000000, "symbol": "X", "open": "1.5", "high": "2.5",
                 "low": "1.0", "close": "2.0", "volume": "15"},
            ]:
                f.write(json.dumps(record) + "\n")
            f.flush()
            source = FileReplaySource(BinanceAdapter(), validate=True)
            records = source.replay_ohlcv(f.name)
            self.assertEqual(len(records), 2)
            os.unlink(f.name)

    def test_replay_missing_file(self):
        source = FileReplaySource(BinanceAdapter())
        with self.assertRaises(FileNotFoundError):
            source.replay_ohlcv("/nonexistent/file.json")

    def test_replay_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("")
            f.flush()
            source = FileReplaySource(BinanceAdapter())
            records = source.replay_ohlcv(f.name)
            self.assertEqual(len(records), 0)
            os.unlink(f.name)

    def test_replay_without_validation(self):
        source = FileReplaySource(BinanceAdapter(), validate=False)
        path = os.path.join(TESTDATA_DIR, "binance_ohlcv.json")
        records = source.replay_ohlcv(path)
        self.assertEqual(len(records), 3)


# --- Cross-exchange normalization tests ---


class TestCrossExchangeNormalization(unittest.TestCase):
    """Tests that both adapters produce consistent unified output."""

    def test_same_timestamp_different_formats(self):
        binance = BinanceAdapter()
        coinbase = CoinbaseAdapter()

        # Same candle at the same time, different raw formats
        binance_raw = [1640995200000, "50000", "51000", "49000", "50500", "100", "BTC/USD"]
        coinbase_raw = [1640995200, 49000, 51000, 50000, 50500, 100, "BTC-USD"]

        b = binance.normalize_ohlcv(binance_raw)
        c = coinbase.normalize_ohlcv(coinbase_raw)

        # Both should have the same timestamp in ms
        self.assertEqual(b.timestamp_ms, c.timestamp_ms)
        # Both should have matching OHLCV values
        self.assertEqual(b.open, c.open)
        self.assertEqual(b.high, c.high)
        self.assertEqual(b.low, c.low)
        self.assertEqual(b.close, c.close)
        self.assertEqual(b.volume, c.volume)
        # Exchange names differ
        self.assertEqual(b.exchange, "binance")
        self.assertEqual(c.exchange, "coinbase")


if __name__ == "__main__":
    unittest.main()
