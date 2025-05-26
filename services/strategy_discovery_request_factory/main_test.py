"""Unit tests for main module (cron job version)."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from absl import flags
from absl.testing import flagsaver
from services.strategy_discovery_request_factory import main
from services.strategy_discovery_request_factory.test_utils import create_test_candles

FLAGS = flags.FLAGS

class MainCronTest(unittest.TestCase):
    """Test main cron job functionality."""

    def setUp(self):
        """Set up test environment."""
        # Reset FLAGS and parse with test arguments
        FLAGS.unparse_flags()
        
        # Parse flags with test arguments before accessing them
        test_argv = [
            "test_binary",
            "--influxdb_token=test-token",
            "--influxdb_org=test-org",
            "--lookback_minutes=5"
        ]
        FLAGS(test_argv)

        # Mock all external dependencies
        self.mock_redis_cls = patch(
            "services.strategy_discovery_request_factory.main.redis.Redis"
        ).start()
        self.mock_influx_poller_cls = patch(
            "services.strategy_discovery_request_factory.main.InfluxPoller"
        ).start()
        self.mock_strategy_discovery_processor_cls = patch(
            "services.strategy_discovery_request_factory.main.StrategyDiscoveryProcessor"
        ).start()
        self.mock_kafka_publisher_cls = patch(
            "services.strategy_discovery_request_factory.main.KafkaPublisher"
        ).start()
        self.mock_last_processed_tracker_cls = patch(
            "services.strategy_discovery_request_factory.main.LastProcessedTracker"
        ).start()

        # Mock instances
        self.mock_redis_instance = Mock()
        self.mock_influx_instance = Mock()
        self.mock_processor_instance = Mock()
        self.mock_kafka_instance = Mock()
        self.mock_tracker_instance = Mock()

        self.mock_redis_cls.return_value = self.mock_redis_instance
        self.mock_influx_poller_cls.return_value = self.mock_influx_instance
        self.mock_strategy_discovery_processor_cls.return_value = self.mock_processor_instance
        self.mock_kafka_publisher_cls.return_value = self.mock_kafka_instance
        self.mock_last_processed_tracker_cls.return_value = self.mock_tracker_instance

        # Set up default mock behaviors
        self.mock_redis_instance.ping.return_value = True
        self.mock_redis_instance.smembers.return_value = {b'btcusd', b'ethusd'}
        self.mock_influx_instance.fetch_new_candles.return_value = ([], 0)
        self.mock_processor_instance.add_candle.return_value = []
        self.mock_tracker_instance.get_last_timestamp.return_value = 0

    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()
        FLAGS.unparse_flags()

    def test_flag_definitions(self):
        """Test that all required flags are defined."""
        # Redis flags
        self.assertTrue(hasattr(FLAGS, "redis_host"))
        self.assertTrue(hasattr(FLAGS, "redis_port"))
        self.assertTrue(hasattr(FLAGS, "redis_db"))
        self.assertTrue(hasattr(FLAGS, "redis_password"))
        self.assertTrue(hasattr(FLAGS, "crypto_symbols_key"))
        
        # InfluxDB flags
        self.assertTrue(hasattr(FLAGS, "influxdb_url"))
        self.assertTrue(hasattr(FLAGS, "influxdb_token"))
        self.assertTrue(hasattr(FLAGS, "influxdb_org"))
        self.assertTrue(hasattr(FLAGS, "influxdb_bucket"))
        
        # Kafka flags
        self.assertTrue(hasattr(FLAGS, "kafka_bootstrap_servers"))
        self.assertTrue(hasattr(FLAGS, "kafka_topic"))
        
        # Processing flags
        self.assertTrue(hasattr(FLAGS, "lookback_minutes"))
        self.assertTrue(hasattr(FLAGS, "fibonacci_windows_minutes"))

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_missing_influxdb_token(self, mock_exit):
        """Test main function fails without InfluxDB token."""
        # Reset flags and parse without influxdb_token
        FLAGS.unparse_flags()
        test_argv = [
            "test_binary",
            "--influxdb_org=test-org",
        ]
        FLAGS(test_argv)
        
        main.main([])
        mock_exit.assert_called_with(1)

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_missing_influxdb_org(self, mock_exit):
        """Test main function fails without InfluxDB org."""
        # Reset flags and parse without influxdb_org
        FLAGS.unparse_flags()
        test_argv = [
            "test_binary",
            "--influxdb_token=test-token",
        ]
        FLAGS(test_argv)
        
        main.main([])
        mock_exit.assert_called_with(1)

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_redis_connection_failure(self, mock_exit):
        """Test main function fails when Redis connection fails."""
        self.mock_redis_instance.ping.side_effect = Exception("Redis connection failed")

        main.main([])
        mock_exit.assert_called_with(1)

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_no_crypto_symbols_in_redis(self, mock_exit):
        """Test main function fails when no symbols in Redis."""
        self.mock_redis_instance.smembers.return_value = set()  # Empty set

        main.main([])
        mock_exit.assert_called_with(1)

    def test_main_initialization_success(self):
        """Test successful main function initialization and execution."""
        main.main([])

        # Verify Redis connection
        self.mock_redis_cls.assert_called_once()
        self.mock_redis_instance.ping.assert_called_once()
        self.mock_redis_instance.smembers.assert_called_once()

        # Verify components were initialized
        self.mock_last_processed_tracker_cls.assert_called_once()
        self.mock_influx_poller_cls.assert_called_once()
        self.mock_strategy_discovery_processor_cls.assert_called_once()
        self.mock_kafka_publisher_cls.assert_called_once()

        # Verify currency pairs conversion and initialization
        expected_pairs = ["BTC/USD", "ETH/USD"]
        processor_init_args = self.mock_processor_instance.initialize_deques.call_args
        self.assertEqual(processor_init_args[0][0], expected_pairs)

        # Verify cleanup
        self.mock_influx_instance.close.assert_called_once()
        self.mock_kafka_instance.close.assert_called_once()
        self.mock_redis_instance.close.assert_called_once()

    def test_symbol_conversion(self):
        """Test symbol to currency pair conversion."""
        # Test with mock data
        self.mock_redis_instance.smembers.return_value = {b'btcusd', b'ethusd', b'adausd'}
        
        main.main([])

        # Verify processor was initialized with converted pairs
        processor_init_args = self.mock_processor_instance.initialize_deques.call_args
        expected_pairs = ["BTC/USD", "ETH/USD", "ADA/USD"]
        self.assertEqual(processor_init_args[0][0], expected_pairs)

    def test_main_processing_with_candles(self):
        """Test main processing when candles are available."""
        test_candles = create_test_candles(2, "BTC/USD")
        test_requests = [Mock(), Mock()]

        # Set up mocks to return data
        self.mock_influx_instance.fetch_new_candles.return_value = (test_candles, 1640995260000)
        self.mock_processor_instance.add_candle.return_value = test_requests
        self.mock_tracker_instance.get_last_timestamp.return_value = 0  # First run

        main.main([])

        # Verify processing occurred for each pair
        self.assertEqual(self.mock_influx_instance.fetch_new_candles.call_count, 2)  # BTC and ETH

        # Verify candle processing - 2 candles per pair, 2 pairs = 4 total
        self.assertEqual(self.mock_processor_instance.add_candle.call_count, 4)

        # Verify request publishing - 2 requests per candle, 2 candles per pair, 2 pairs = 8 total
        self.assertEqual(self.mock_kafka_instance.publish_request.call_count, 8)
        
        # Verify timestamp tracking
        self.mock_tracker_instance.set_last_timestamp.assert_called()

    def test_main_no_new_candles(self):
        """Test processing when no new candles are available."""
        # Mock returns no candles
        self.mock_influx_instance.fetch_new_candles.return_value = ([], 0)
        self.mock_tracker_instance.get_last_timestamp.return_value = 1000  # Previous run

        main.main([])

        # Verify processing occurred but no candle processing or publishing
        self.assertEqual(self.mock_influx_instance.fetch_new_candles.call_count, 2)
        self.mock_processor_instance.add_candle.assert_not_called()
        self.mock_kafka_instance.publish_request.assert_not_called()
        # Should not update timestamp if no new candles
        self.mock_tracker_instance.set_last_timestamp.assert_not_called()

    def test_first_run_lookback_behavior(self):
        """Test behavior on first run using lookback minutes."""
        test_candles = create_test_candles(1, "BTC/USD")
        
        # First run - no previous timestamp
        self.mock_tracker_instance.get_last_timestamp.return_value = 0
        self.mock_influx_instance.fetch_new_candles.return_value = (test_candles, 1000)

        with patch("services.strategy_discovery_request_factory.main.time.time", return_value=1000):
            main.main([])

        # Verify fetch_new_candles was called with calculated lookback timestamp
        # lookback_minutes=5 means 5*60*1000 = 300000 ms before current time
        expected_lookback = (1000 * 1000) - (5 * 60 * 1000)  # current_time_ms - lookback
        
        fetch_calls = self.mock_influx_instance.fetch_new_candles.call_args_list
        # Check that lookback was used for both BTC/USD and ETH/USD
        for call in fetch_calls:
            currency_pair, timestamp = call[0]
            self.assertEqual(timestamp, expected_lookback)

    def test_error_handling_single_pair(self):
        """Test that error in one pair doesn't stop processing of others."""
        # Make BTC/USD fail, but ETH/USD succeed
        def side_effect(pair, timestamp):
            if pair == "BTC/USD":
                raise Exception("Processing failed for BTC/USD")
            return (create_test_candles(1, pair), 1000)

        self.mock_influx_instance.fetch_new_candles.side_effect = side_effect

        # Should not raise exception and should continue processing
        main.main([])

        # Should have attempted both pairs
        self.assertEqual(self.mock_influx_instance.fetch_new_candles.call_count, 2)

    def test_fibonacci_windows_flag_parsing(self):
        """Test parsing of Fibonacci windows from flags."""
        # Reset flags and set fibonacci_windows_minutes
        FLAGS.unparse_flags()
        test_argv = [
            "test_binary",
            "--influxdb_token=test-token",
            "--influxdb_org=test-org",
            "--fibonacci_windows_minutes=5,8,13"
        ]
        FLAGS(test_argv)

        main.main([])

        # Verify StrategyDiscoveryProcessor was initialized with correct windows
        processor_call_args = self.mock_strategy_discovery_processor_cls.call_args
        fibonacci_windows = processor_call_args[1]["fibonacci_windows_minutes"]
        self.assertEqual(fibonacci_windows, [5, 8, 13])

    def test_redis_configuration_flags(self):
        """Test Redis configuration from flags."""
        # Reset flags with Redis config
        FLAGS.unparse_flags()
        test_argv = [
            "test_binary",
            "--redis_host=redis.example.com",
            "--redis_port=6380",
            "--redis_db=1",
            "--redis_password=secret",
            "--crypto_symbols_key=test:symbols",
            "--influxdb_token=test-token",
            "--influxdb_org=test-org",
        ]
        FLAGS(test_argv)

        main.main([])

        # Verify Redis was initialized with correct config
        redis_call_args = self.mock_redis_cls.call_args
        self.assertEqual(redis_call_args[1]["host"], "redis.example.com")
        self.assertEqual(redis_call_args[1]["port"], 6380)
        self.assertEqual(redis_call_args[1]["db"], 1)
        self.assertEqual(redis_call_args[1]["password"], "secret")

        # Verify correct Redis key was used
        self.mock_redis_instance.smembers.assert_called_with("test:symbols")

    def test_timestamp_tracking_per_pair(self):
        """Test that timestamps are tracked per currency pair."""
        self.mock_tracker_instance.get_last_timestamp.side_effect = [0, 500]  # BTC first run, ETH has previous

        self.mock_influx_instance.fetch_new_candles.side_effect = [
            (create_test_candles(1, "BTC/USD", start_timestamp_ms=1000), 1000),
            (create_test_candles(1, "ETH/USD", start_timestamp_ms=1500), 1500)
        ]

        main.main([])

        # Verify both pairs were processed and timestamps tracked
        self.assertEqual(self.mock_influx_instance.fetch_new_candles.call_count, 2)
        self.mock_tracker_instance.set_last_timestamp.assert_any_call("BTC/USD", 1000)
        self.mock_tracker_instance.set_last_timestamp.assert_any_call("ETH/USD", 1500)

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_component_initialization_failure(self, mock_exit):
        """Test that component initialization failures are handled."""
        # Make InfluxPoller initialization fail
        self.mock_influx_poller_cls.side_effect = Exception("InfluxDB connection failed")

        main.main([])

        # Should exit with error code
        mock_exit.assert_called_with(1)

    @patch("services.strategy_discovery_request_factory.main.logging")
    def test_logging_behavior(self, mock_logging):
        """Test that appropriate logging occurs."""
        main.main([])

        # Verify logging calls
        mock_logging.set_verbosity.assert_called_once()
        mock_logging.info.assert_called()


if __name__ == "__main__":
    unittest.main()
    