"""Unit tests for main module."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import signal
import sys
from absl import flags
from absl.testing import flagsaver
from services.strategy_discovery_request_factory import main
from services.strategy_discovery_request_factory.test_utils import create_test_candles

FLAGS = flags.FLAGS

class MainTest(unittest.TestCase):
    """Test main application functionality."""

    def setUp(self):
        """Set up test environment."""
        # Reset FLAGS and parse with test arguments
        FLAGS.unparse_flags()
        
        # Parse flags with test arguments before accessing them
        test_argv = [
            "test_binary",
            "--cmc_api_key=test-cmc-key", 
            "--influxdb_token=test-token",
            "--influxdb_org=test-org",
            "--lookback_minutes=5"
        ]
        FLAGS(test_argv)

        # Mock all external dependencies
        self.mock_get_top_n_crypto = patch(
            "services.strategy_discovery_request_factory.main.get_top_n_crypto_symbols"
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

        # Set up mock return values
        self.mock_get_top_n_crypto.return_value = ["btcusd", "ethusd"]

        # Mock instances
        self.mock_influx_instance = Mock()
        self.mock_processor_instance = Mock()
        self.mock_kafka_instance = Mock()
        self.mock_tracker_instance = Mock()

        self.mock_influx_poller_cls.return_value = self.mock_influx_instance
        self.mock_strategy_discovery_processor_cls.return_value = self.mock_processor_instance
        self.mock_kafka_publisher_cls.return_value = self.mock_kafka_instance
        self.mock_last_processed_tracker_cls.return_value = self.mock_tracker_instance

        # Mock fetch_new_candles to return no candles by default
        self.mock_influx_instance.fetch_new_candles.return_value = ([], 0)
        self.mock_processor_instance.add_candle.return_value = []
        self.mock_tracker_instance.get_last_timestamp.return_value = 0

    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()
        FLAGS.unparse_flags()

    def test_flag_definitions(self):
        """Test that all required flags are defined."""
        # Test flag existence
        self.assertTrue(hasattr(FLAGS, "cmc_api_key"))
        self.assertTrue(hasattr(FLAGS, "top_n_cryptos"))
        self.assertTrue(hasattr(FLAGS, "influxdb_url"))
        self.assertTrue(hasattr(FLAGS, "influxdb_token"))
        self.assertTrue(hasattr(FLAGS, "influxdb_org"))
        self.assertTrue(hasattr(FLAGS, "kafka_bootstrap_servers"))
        self.assertTrue(hasattr(FLAGS, "lookback_minutes"))

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_missing_cmc_api_key(self, mock_exit):
        """Test main function fails without CMC API key."""
        # Reset flags and parse without cmc_api_key
        FLAGS.unparse_flags()
        test_argv = [
            "test_binary",
            "--influxdb_token=test-token",
            "--influxdb_org=test-org",
        ]
        FLAGS(test_argv)
        
        main.main([])
        mock_exit.assert_called_with(1)

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_missing_influxdb_token(self, mock_exit):
        """Test main function fails without InfluxDB token."""
        # Reset flags and parse without influxdb_token
        FLAGS.unparse_flags()
        test_argv = [
            "test_binary",
            "--cmc_api_key=test-key",
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
            "--cmc_api_key=test-key",
            "--influxdb_token=test-token",
        ]
        FLAGS(test_argv)
        
        main.main([])
        mock_exit.assert_called_with(1)

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_cmc_fetch_failure(self, mock_exit):
        """Test main function fails when CMC returns no symbols."""
        self.mock_get_top_n_crypto.return_value = []

        main.main([])
        mock_exit.assert_called_with(1)

    def test_main_initialization_success(self):
        """Test successful main function initialization."""
        main.main([])

        # Verify components were initialized
        self.mock_last_processed_tracker_cls.assert_called_once()
        self.mock_get_top_n_crypto.assert_called_once()
        self.mock_influx_poller_cls.assert_called_once()
        self.mock_strategy_discovery_processor_cls.assert_called_once()
        self.mock_kafka_publisher_cls.assert_called_once()

        # Verify currency pairs conversion
        expected_pairs = ["BTC/USD", "ETH/USD"]
        processor_init_args = self.mock_processor_instance.initialize_deques.call_args
        self.assertEqual(processor_init_args[0][0], expected_pairs)

    def test_main_processing_loop(self):
        """Test main processing loop functionality."""
        test_candles = create_test_candles(2, "BTC/USD")
        test_requests = [Mock(), Mock()]

        # Set up mocks to return data
        self.mock_influx_instance.fetch_new_candles.return_value = (test_candles, 1640995260000)
        self.mock_processor_instance.add_candle.return_value = test_requests
        self.mock_tracker_instance.get_last_timestamp.return_value = 0 # Simulate first run

        main.main([])

        # Verify processing occurred for each pair
        self.assertEqual(self.mock_influx_instance.fetch_new_candles.call_count, 2) # For BTC and ETH

        # Verify candle processing
        # Called twice for BTC/USD (one for each candle)
        # Called twice for ETH/USD (one for each candle, assuming fetch_new_candles returns 2 for ETH as well)
        self.assertEqual(self.mock_processor_instance.add_candle.call_count, 4)

        # Verify request publishing
        # 2 candles * 2 requests per candle * 2 pairs
        self.assertEqual(self.mock_kafka_instance.publish_request.call_count, 8)
        self.mock_tracker_instance.set_last_timestamp.assert_called()

    def test_main_no_new_candles(self):
        """Test processing when no new candles are available."""
        # Mock returns no candles
        self.mock_influx_instance.fetch_new_candles.return_value = ([], 0)
        self.mock_tracker_instance.get_last_timestamp.return_value = 1000 # Simulate already processed

        main.main([])

        # Verify processing occurred but no candle processing or publishing
        self.assertEqual(self.mock_influx_instance.fetch_new_candles.call_count, 2)
        self.mock_processor_instance.add_candle.assert_not_called()
        self.mock_kafka_instance.publish_request.assert_not_called()
        self.mock_tracker_instance.set_last_timestamp.assert_not_called() # No new timestamp to set

    @patch("signal.signal")
    def test_signal_registration(self, mock_signal):
        """Test that signal handlers are registered."""
        main.main([])

        # Verify signal handlers were registered
        mock_signal.assert_any_call(signal.SIGINT, main.handle_shutdown_signal)
        mock_signal.assert_any_call(signal.SIGTERM, main.handle_shutdown_signal)

    def test_fibonacci_windows_flag_parsing(self):
        """Test parsing of Fibonacci windows from flags."""
        # Reset flags and set fibonacci_windows_minutes
        FLAGS.unparse_flags()
        test_argv = [
            "test_binary",
            "--cmc_api_key=test-key",
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

    def test_timestamp_tracking(self):
        """Test that timestamps are properly tracked per currency pair."""
        # Set up two currency pairs
        self.mock_get_top_n_crypto.return_value = ["btcusd", "ethusd"]
        self.mock_tracker_instance.get_last_timestamp.side_effect = [0, 500] # BTC first run, ETH has previous

        self.mock_influx_instance.fetch_new_candles.side_effect = [
            (create_test_candles(1, "BTC/USD", start_timestamp_ms=1000), 1000),
            (create_test_candles(1, "ETH/USD", start_timestamp_ms=1500), 1500)
        ]

        main.main([])

        # Verify both pairs were polled and timestamps tracked
        self.assertEqual(self.mock_influx_instance.fetch_new_candles.call_count, 2)
        self.mock_tracker_instance.set_last_timestamp.assert_any_call("BTC/USD", 1000)
        self.mock_tracker_instance.set_last_timestamp.assert_any_call("ETH/USD", 1500)

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_exception_handling(self, mock_exit):
        """Test that exceptions are properly handled."""
        # Make InfluxPoller initialization fail
        self.mock_influx_poller_cls.side_effect = Exception("Connection failed")

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
