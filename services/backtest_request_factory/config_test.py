"""Unit tests for config module."""

import os
import unittest
from unittest.mock import patch
from protos.strategies_pb2 import StrategyType
from services.backtest_request_factory import config


class ConfigTest(unittest.TestCase):
    """Test configuration loading and defaults."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment variables
        self.original_env = {}
        env_vars = [
            "INFLUXDB_URL",
            "INFLUXDB_TOKEN",
            "INFLUXDB_ORG",
            "INFLUXDB_BUCKET_CANDLES",
            "KAFKA_BOOTSTRAP_SERVERS",
            "KAFKA_BACKTEST_REQUEST_TOPIC",
            "POLLING_INTERVAL_SECONDS",
            "TOP_N_CRYPTOS",
            "CMC_API_KEY",
            "DEFAULT_STRATEGY_TYPE",
            "CANDLE_GRANULARITY_MINUTES",
        ]
        for var in env_vars:
            self.original_env[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment variables
        for var, value in self.original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]

    def test_default_values(self):
        """Test that default configuration values are correct."""
        # Need to reload config module to pick up env changes
        import importlib

        importlib.reload(config)

        self.assertEqual(
            config.INFLUXDB_URL,
            "http://influxdb.tradestream-namespace.svc.cluster.local:8086",
        )
        self.assertIsNone(config.INFLUXDB_TOKEN)
        self.assertIsNone(config.INFLUXDB_ORG)
        self.assertEqual(config.INFLUXDB_BUCKET_CANDLES, "tradestream-data")
        self.assertEqual(config.KAFKA_BOOTSTRAP_SERVERS, "localhost:9092")
        self.assertEqual(config.KAFKA_BACKTEST_REQUEST_TOPIC, "backtest-requests")
        self.assertEqual(config.POLLING_INTERVAL_SECONDS, 60)
        self.assertEqual(config.TOP_N_CRYPTOS, 20)
        self.assertIsNone(config.CMC_API_KEY)
        self.assertEqual(config.CANDLE_GRANULARITY_MINUTES, 1)

    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        # Set environment variables
        os.environ["INFLUXDB_URL"] = "http://test-influx:8086"
        os.environ["INFLUXDB_TOKEN"] = "test-token"
        os.environ["INFLUXDB_ORG"] = "test-org"
        os.environ["INFLUXDB_BUCKET_CANDLES"] = "test-bucket"
        os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "test-kafka:9092"
        os.environ["KAFKA_BACKTEST_REQUEST_TOPIC"] = "test-topic"
        os.environ["POLLING_INTERVAL_SECONDS"] = "30"
        os.environ["TOP_N_CRYPTOS"] = "10"
        os.environ["CMC_API_KEY"] = "test-cmc-key"
        os.environ["DEFAULT_STRATEGY_TYPE"] = "EMA_MACD"
        os.environ["CANDLE_GRANULARITY_MINUTES"] = "5"

        # Reload config to pick up new env vars
        import importlib

        importlib.reload(config)

        self.assertEqual(config.INFLUXDB_URL, "http://test-influx:8086")
        self.assertEqual(config.INFLUXDB_TOKEN, "test-token")
        self.assertEqual(config.INFLUXDB_ORG, "test-org")
        self.assertEqual(config.INFLUXDB_BUCKET_CANDLES, "test-bucket")
        self.assertEqual(config.KAFKA_BOOTSTRAP_SERVERS, "test-kafka:9092")
        self.assertEqual(config.KAFKA_BACKTEST_REQUEST_TOPIC, "test-topic")
        self.assertEqual(config.POLLING_INTERVAL_SECONDS, 30)
        self.assertEqual(config.TOP_N_CRYPTOS, 10)
        self.assertEqual(config.CMC_API_KEY, "test-cmc-key")
        self.assertEqual(config.DEFAULT_STRATEGY_TYPE, StrategyType.EMA_MACD)
        self.assertEqual(config.CANDLE_GRANULARITY_MINUTES, 5)

    def test_fibonacci_windows_values(self):
        """Test that Fibonacci window values are correct."""
        expected_windows = [
            1597,
            2584,
            4181,
            6765,
            10946,
            17711,
            28657,
            46368,
            75025,
            121393,
        ]
        self.assertEqual(config.FIBONACCI_WINDOWS_MINUTES, expected_windows)

        # Verify they are sorted
        self.assertEqual(
            config.FIBONACCI_WINDOWS_MINUTES, sorted(config.FIBONACCI_WINDOWS_MINUTES)
        )

        # Verify they are all greater than 1 day (1440 minutes)
        for window in config.FIBONACCI_WINDOWS_MINUTES:
            self.assertGreater(window, 1440)

        # Verify they are all less than ~3 months (131400 minutes)
        for window in config.FIBONACCI_WINDOWS_MINUTES:
            self.assertLess(window, 131400)

    def test_deque_maxlen_sufficient(self):
        """Test that deque max length is sufficient for largest window."""
        max_window = max(config.FIBONACCI_WINDOWS_MINUTES)
        self.assertGreaterEqual(config.DEQUE_MAXLEN, max_window)

        # Should have some buffer
        self.assertGreater(config.DEQUE_MAXLEN, max_window * 1.05)

    def test_strategy_type_enum_conversion(self):
        """Test strategy type enum value conversion."""
        # Test default
        import importlib

        importlib.reload(config)

        # Should be a valid StrategyType value
        self.assertIsInstance(config.DEFAULT_STRATEGY_TYPE, int)
        self.assertIn(config.DEFAULT_STRATEGY_TYPE, StrategyType.values())

    def test_invalid_strategy_type_handling(self):
        """Test handling of invalid strategy type."""
        os.environ["DEFAULT_STRATEGY_TYPE"] = "INVALID_STRATEGY"

        # Should raise ValueError when trying to convert invalid strategy type
        with self.assertRaises(ValueError):
            import importlib

            importlib.reload(config)

    def test_numeric_conversion_errors(self):
        """Test handling of invalid numeric values."""
        # Test invalid polling interval
        os.environ["POLLING_INTERVAL_SECONDS"] = "invalid"
        with self.assertRaises(ValueError):
            import importlib

            importlib.reload(config)

        # Clean up for next test
        del os.environ["POLLING_INTERVAL_SECONDS"]

        # Test invalid top N cryptos
        os.environ["TOP_N_CRYPTOS"] = "invalid"
        with self.assertRaises(ValueError):
            import importlib

            importlib.reload(config)

        # Clean up for next test
        del os.environ["TOP_N_CRYPTOS"]

        # Test invalid candle granularity
        os.environ["CANDLE_GRANULARITY_MINUTES"] = "invalid"
        with self.assertRaises(ValueError):
            import importlib

            importlib.reload(config)


if __name__ == "__main__":
    unittest.main()
