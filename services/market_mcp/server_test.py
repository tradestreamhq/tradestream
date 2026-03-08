"""Tests for market-mcp server tools."""

from unittest import mock

from absl.testing import absltest

from services.market_mcp.server import (
    get_candles,
    get_latest_price,
    get_market_summary,
    get_symbols,
    get_volatility,
    init_server,
)
from services.market_mcp import influxdb_client as influxdb_client_module
from services.market_mcp import redis_client as redis_client_module


class GetCandlesTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        self.mock_influx = mock.MagicMock(
            spec=influxdb_client_module.InfluxDBQueryClient
        )
        self.mock_redis = mock.MagicMock(
            spec=redis_client_module.RedisMarketClient
        )
        init_server(self.mock_influx, self.mock_redis)

    def test_get_candles_returns_data(self):
        expected = [
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 42000.0,
                "high": 42500.0,
                "low": 41800.0,
                "close": 42200.0,
                "volume": 100.5,
            }
        ]
        self.mock_influx.get_candles.return_value = expected

        result = get_candles("BTC/USD", "1m", "-1h", None, 100)

        self.mock_influx.get_candles.assert_called_once_with(
            "BTC/USD", "1m", "-1h", None, 100
        )
        self.assertEqual(result, expected)

    def test_get_candles_no_client(self):
        init_server(None, self.mock_redis)
        result = get_candles("BTC/USD")
        self.assertEqual(result, [{"error": "InfluxDB client not initialized"}])


class GetLatestPriceTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        self.mock_influx = mock.MagicMock(
            spec=influxdb_client_module.InfluxDBQueryClient
        )
        self.mock_redis = mock.MagicMock(
            spec=redis_client_module.RedisMarketClient
        )
        init_server(self.mock_influx, self.mock_redis)

    def test_returns_price_info(self):
        self.mock_influx.get_latest_candle.return_value = {
            "timestamp": "2024-01-01T00:00:00+00:00",
            "open": 42000.0,
            "high": 42500.0,
            "low": 41800.0,
            "close": 42200.0,
            "volume": 100.5,
        }
        self.mock_influx.get_candles_for_24h.return_value = [
            {
                "timestamp": "2023-12-31T00:00:00+00:00",
                "open": 41000.0,
                "high": 41500.0,
                "low": 40800.0,
                "close": 41000.0,
                "volume": 50.0,
            },
            {
                "timestamp": "2024-01-01T00:00:00+00:00",
                "open": 42000.0,
                "high": 42500.0,
                "low": 41800.0,
                "close": 42200.0,
                "volume": 100.5,
            },
        ]

        result = get_latest_price("BTC/USD")

        self.assertEqual(result["symbol"], "BTC/USD")
        self.assertEqual(result["price"], 42200.0)
        self.assertAlmostEqual(result["volume_24h"], 150.5)
        self.assertIn("change_24h", result)
        self.assertIn("timestamp", result)

    def test_no_data(self):
        self.mock_influx.get_latest_candle.return_value = None
        result = get_latest_price("BTC/USD")
        self.assertIn("error", result)

    def test_no_client(self):
        init_server(None, self.mock_redis)
        result = get_latest_price("BTC/USD")
        self.assertIn("error", result)


class GetVolatilityTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        self.mock_influx = mock.MagicMock(
            spec=influxdb_client_module.InfluxDBQueryClient
        )
        self.mock_redis = mock.MagicMock(
            spec=redis_client_module.RedisMarketClient
        )
        init_server(self.mock_influx, self.mock_redis)

    def test_computes_volatility(self):
        candles = [
            {
                "timestamp": f"2024-01-01T00:{i:02d}:00+00:00",
                "open": 42000.0 + i * 10,
                "high": 42050.0 + i * 10,
                "low": 41950.0 + i * 10,
                "close": 42000.0 + (i + 1) * 10,
                "volume": 10.0,
            }
            for i in range(10)
        ]
        self.mock_influx.get_candles_for_period.return_value = candles

        result = get_volatility("BTC/USD", 60)

        self.assertEqual(result["symbol"], "BTC/USD")
        self.assertIn("volatility", result)
        self.assertIn("atr", result)
        self.assertEqual(result["period"], 60)

    def test_insufficient_data(self):
        self.mock_influx.get_candles_for_period.return_value = [
            {"timestamp": "2024-01-01T00:00:00+00:00", "close": 42000.0}
        ]
        result = get_volatility("BTC/USD")
        self.assertIn("error", result)

    def test_no_client(self):
        init_server(None, self.mock_redis)
        result = get_volatility("BTC/USD")
        self.assertIn("error", result)


class GetSymbolsTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        self.mock_influx = mock.MagicMock(
            spec=influxdb_client_module.InfluxDBQueryClient
        )
        self.mock_redis = mock.MagicMock(
            spec=redis_client_module.RedisMarketClient
        )
        init_server(self.mock_influx, self.mock_redis)

    def test_returns_symbols(self):
        expected = [
            {
                "id": "btcusd",
                "asset_class": "crypto",
                "base": "BTC",
                "quote": "USD",
                "exchange": "multi",
            }
        ]
        self.mock_redis.get_symbols.return_value = expected
        result = get_symbols()
        self.assertEqual(result, expected)

    def test_no_client(self):
        init_server(self.mock_influx, None)
        result = get_symbols()
        self.assertEqual(result, [{"error": "Redis client not initialized"}])


class GetMarketSummaryTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        self.mock_influx = mock.MagicMock(
            spec=influxdb_client_module.InfluxDBQueryClient
        )
        self.mock_redis = mock.MagicMock(
            spec=redis_client_module.RedisMarketClient
        )
        init_server(self.mock_influx, self.mock_redis)

    def test_returns_summary(self):
        candles = [
            {
                "timestamp": f"2024-01-01T{h:02d}:00:00+00:00",
                "open": 42000.0 + h * 10,
                "high": 42100.0 + h * 10,
                "low": 41900.0 + h * 10,
                "close": 42050.0 + h * 10,
                "volume": 10.0 + h,
            }
            for h in range(24)
        ]
        self.mock_influx.get_candles_for_24h.return_value = candles

        result = get_market_summary("BTC/USD")

        self.assertEqual(result["symbol"], "BTC/USD")
        self.assertIn("price", result)
        self.assertIn("change_1h", result)
        self.assertIn("change_24h", result)
        self.assertIn("volume_24h", result)
        self.assertIn("volatility", result)
        self.assertIn("high_24h", result)
        self.assertIn("low_24h", result)
        self.assertIn("vwap", result)

    def test_no_data(self):
        self.mock_influx.get_candles_for_24h.return_value = []
        result = get_market_summary("BTC/USD")
        self.assertIn("error", result)

    def test_no_client(self):
        init_server(None, self.mock_redis)
        result = get_market_summary("BTC/USD")
        self.assertIn("error", result)


if __name__ == "__main__":
    absltest.main()
