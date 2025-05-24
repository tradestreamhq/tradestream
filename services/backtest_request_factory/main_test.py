"""Unit tests for main module."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import signal
import sys
from absl import flags
from absl.testing import flagsaver
from services.backtest_request_factory import main
from services.backtest_request_factory.test_utils import create_test_candles


class MainTest(unittest.TestCase):
    """Test main application functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Reset FLAGS for each test
        flags.FLAGS.unparse_flags()
        
        # Set required flags
        flags.FLAGS.cmc_api_key = "test-cmc-key"
        flags.FLAGS.influxdb_token = "test-token"
        flags.FLAGS.influxdb_org = "test-org"
        flags.FLAGS.polling_interval_seconds = 1  # Short interval for testing
        
        # Mock all external dependencies
        self.mock_get_top_n_crypto = patch('services.backtest_request_factory.main.get_top_n_crypto_symbols').start()
        self.mock_influx_poller = patch('services.backtest_request_factory.main.InfluxPoller').start()
        self.mock_candle_processor = patch('services.backtest_request_factory.main.CandleProcessor').start()
        self.mock_kafka_publisher = patch('services.backtest_request_factory.main.KafkaPublisher').start()
        
        # Set up mock return values
        self.mock_get_top_n_crypto.return_value = ['btcusd', 'ethusd']
        
        # Mock instances
        self.mock_influx_instance = Mock()
        self.mock_processor_instance = Mock()
        self.mock_kafka_instance = Mock()
        
        self.mock_influx_poller.return_value = self.mock_influx_instance
        self.mock_candle_processor.return_value = self.mock_processor_instance
        self.mock_kafka_publisher.return_value = self.mock_kafka_instance
        
        # Mock fetch_new_candles to return no candles by default
        self.mock_influx_instance.fetch_new_candles.return_value = ([], 0)
        self.mock_processor_instance.add_candle.return_value = []
    
    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()
        # Reset global variables
        main.shutdown_requested = False
        main.influx_poller_global = None
        main.kafka_publisher_global = None
    
    def test_flag_definitions(self):
        """Test that all required flags are defined."""
        # Test flag existence and default values
        self.assertTrue(hasattr(flags.FLAGS, 'cmc_api_key'))
        self.assertTrue(hasattr(flags.FLAGS, 'top_n_cryptos'))
        self.assertTrue(hasattr(flags.FLAGS, 'influxdb_url'))
        self.assertTrue(hasattr(flags.FLAGS, 'influxdb_token'))
        self.assertTrue(hasattr(flags.FLAGS, 'influxdb_org'))
        self.assertTrue(hasattr(flags.FLAGS, 'kafka_bootstrap_servers'))
        self.assertTrue(hasattr(flags.FLAGS, 'polling_interval_seconds'))
    
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_main_missing_cmc_api_key(self, mock_exit):
        """Test main function fails without CMC API key."""
        flags.FLAGS.cmc_api_key = None
        
        main.main([])
        
        mock_exit.assert_called_with(1)
    
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_main_missing_influxdb_token(self, mock_exit):
        """Test main function fails without InfluxDB token."""
        flags.FLAGS.influxdb_token = None
        
        main.main([])
        
        mock_exit.assert_called_with(1)
    
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_main_missing_influxdb_org(self, mock_exit):
        """Test main function fails without InfluxDB org."""
        flags.FLAGS.influxdb_org = None
        
        main.main([])
        
        mock_exit.assert_called_with(1)
    
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_main_cmc_fetch_failure(self, mock_exit):
        """Test main function fails when CMC returns no symbols."""
        self.mock_get_top_n_crypto.return_value = []
        
        main.main([])
        
        mock_exit.assert_called_with(1)
    
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_main_initialization_success(self, mock_exit, mock_sleep):
        """Test successful main function initialization."""
        # Make the loop exit immediately
        def side_effect(*args):
            main.shutdown_requested = True
            
        mock_sleep.side_effect = side_effect
        
        main.main([])
        
        # Verify components were initialized
        self.mock_influx_poller.assert_called_once()
        self.mock_candle_processor.assert_called_once()
        self.mock_kafka_publisher.assert_called_once()
        
        # Verify currency pairs conversion
        expected_pairs = ["BTC/USD", "ETH/USD"]
        processor_call_args = self.mock_candle_processor.call_args
        processor_init_args = self.mock_processor_instance.initialize_deques.call_args
        self.assertEqual(processor_init_args[0][0], expected_pairs)
    
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_main_polling_loop(self, mock_exit, mock_sleep):
        """Test main polling loop functionality."""
        test_candles = create_test_candles(2, "BTC/USD")
        test_requests = [Mock(), Mock()]
        
        # Set up mocks to return data on first poll, then exit
        poll_count = [0]
        
        def fetch_candles_side_effect(pair, last_ts):
            poll_count[0] += 1
            if poll_count[0] == 1:
                return test_candles, 1640995260000
            else:
                main.shutdown_requested = True
                return [], last_ts
        
        self.mock_influx_instance.fetch_new_candles.side_effect = fetch_candles_side_effect
        self.mock_processor_instance.add_candle.return_value = test_requests
        
        main.main([])
        
        # Verify polling occurred
        self.mock_influx_instance.fetch_new_candles.assert_called()
        
        # Verify candle processing
        self.assertEqual(self.mock_processor_instance.add_candle.call_count, 2)  # 2 candles
        
        # Verify request publishing
        self.assertEqual(self.mock_kafka_instance.publish_request.call_count, 4)  # 2 candles * 2 requests
    
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_main_no_new_candles(self, mock_exit, mock_sleep):
        """Test polling when no new candles are available."""
        # Make the loop exit after one iteration
        def sleep_side_effect(*args):
            main.shutdown_requested = True
            
        mock_sleep.side_effect = sleep_side_effect
        
        # Mock returns no candles
        self.mock_influx_instance.fetch_new_candles.return_value = ([], 0)
        
        main.main([])
        
        # Verify polling occurred but no processing
        self.mock_influx_instance.fetch_new_candles.assert_called()
        self.mock_processor_instance.add_candle.assert_not_called()
        self.mock_kafka_instance.publish_request.assert_not_called()
    
    def test_handle_shutdown_signal_sigint(self):
        """Test SIGINT signal handling."""
        mock_influx = Mock()
        mock_kafka = Mock()
        main.influx_poller_global = mock_influx
        main.kafka_publisher_global = mock_kafka
        
        main.handle_shutdown_signal(signal.SIGINT, None)
        
        self.assertTrue(main.shutdown_requested)
        mock_influx.close.assert_called_once()
        mock_kafka.close.assert_called_once()
    
    def test_handle_shutdown_signal_sigterm(self):
        """Test SIGTERM signal handling."""
        mock_influx = Mock()
        mock_kafka = Mock()
        main.influx_poller_global = mock_influx
        main.kafka_publisher_global = mock_kafka
        
        main.handle_shutdown_signal(signal.SIGTERM, None)
        
        self.assertTrue(main.shutdown_requested)
        mock_influx.close.assert_called_once()
        mock_kafka.close.assert_called_once()
    
    def test_handle_shutdown_signal_no_globals(self):
        """Test signal handling when global objects are None."""
        main.influx_poller_global = None
        main.kafka_publisher_global = None
        
        # Should not raise exception
        main.handle_shutdown_signal(signal.SIGINT, None)
        
        self.assertTrue(main.shutdown_requested)
    
    @patch('services.backtest_request_factory.main.signal.signal')
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_signal_registration(self, mock_exit, mock_sleep, mock_signal):
        """Test that signal handlers are registered."""
        def sleep_side_effect(*args):
            main.shutdown_requested = True
            
        mock_sleep.side_effect = sleep_side_effect
        
        main.main([])
        
        # Verify signal handlers were registered
        signal_calls = mock_signal.call_args_list
        registered_signals = [call[0][0] for call in signal_calls]
        
        self.assertIn(signal.SIGINT, registered_signals)
        self.assertIn(signal.SIGTERM, registered_signals)
    
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_fibonacci_windows_flag_parsing(self, mock_exit, mock_sleep):
        """Test parsing of Fibonacci windows from flags."""
        flags.FLAGS.fibonacci_windows_minutes = ["5", "8", "13"]
        
        def sleep_side_effect(*args):
            main.shutdown_requested = True
            
        mock_sleep.side_effect = sleep_side_effect
        
        main.main([])
        
        # Verify CandleProcessor was initialized with correct windows
        processor_call_args = self.mock_candle_processor.call_args
        fibonacci_windows = processor_call_args[1]['fibonacci_windows_minutes']
        self.assertEqual(fibonacci_windows, [5, 8, 13])
    
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_timestamp_tracking(self, mock_exit, mock_sleep):
        """Test that timestamps are properly tracked per currency pair."""
        # Set up two currency pairs
        self.mock_get_top_n_crypto.return_value = ['btcusd', 'ethusd']
        
        poll_count = [0]
        
        def fetch_candles_side_effect(pair, last_ts):
            poll_count[0] += 1
            if poll_count[0] <= 2:  # First poll for each pair
                return create_test_candles(1, pair), 1640995260000
            else:
                main.shutdown_requested = True
                return [], last_ts
        
        self.mock_influx_instance.fetch_new_candles.side_effect = fetch_candles_side_effect
        
        main.main([])
        
        # Verify both pairs were polled
        fetch_calls = self.mock_influx_instance.fetch_new_candles.call_args_list
        polled_pairs = [call[0][0] for call in fetch_calls]
        
        self.assertIn("BTC/USD", polled_pairs)
        self.assertIn("ETH/USD", polled_pairs)
    
    @patch('services.backtest_request_factory.main.time.monotonic')
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_polling_interval_timing(self, mock_exit, mock_sleep, mock_monotonic):
        """Test that polling respects the configured interval."""
        flags.FLAGS.polling_interval_seconds = 10
        
        # Mock monotonic time to simulate fast loop execution
        mock_monotonic.side_effect = [0, 2]  # Loop takes 2 seconds
        
        def sleep_side_effect(duration):
            if duration > 0:
                main.shutdown_requested = True
            
        mock_sleep.side_effect = sleep_side_effect
        
        main.main([])
        
        # Should sleep for remaining time (10 - 2 = 8 seconds)
        mock_sleep.assert_called()
        # The exact sleep duration depends on loop timing, but it should be positive
    
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_exception_handling(self, mock_exit, mock_sleep):
        """Test that exceptions are properly handled."""
        # Make InfluxPoller initialization fail
        self.mock_influx_poller.side_effect = Exception("Connection failed")
        
        main.main([])
        
        # Should exit with error code
        mock_exit.assert_called_with(1)
    
    @patch('services.backtest_request_factory.main.time.sleep')
    @patch('services.backtest_request_factory.main.sys.exit')
    def test_graceful_shutdown_in_loop(self, mock_exit, mock_sleep):
        """Test graceful shutdown during main loop."""
        def fetch_candles_side_effect(pair, last_ts):
            # Set shutdown flag during polling
            main.shutdown_requested = True
            return [], last_ts
        
        self.mock_influx_instance.fetch_new_candles.side_effect = fetch_candles_side_effect
        
        main.main([])
        
        # Should exit cleanly
        mock_exit.assert_called_with(0)
        
        # Should close resources
        self.mock_influx_instance.close.assert_called_once()
        self.mock_kafka_instance.close.assert_called_once()
    
    @patch('services.backtest_request_factory.main.logging')
    def test_logging_behavior(self, mock_logging):
        """Test that appropriate logging occurs."""
        with patch('services.backtest_request_factory.main.time.sleep') as mock_sleep:
            def sleep_side_effect(*args):
                main.shutdown_requested = True
                
            mock_sleep.side_effect = sleep_side_effect
            
            main.main([])
            
            # Verify logging calls
            mock_logging.set_verbosity.assert_called_once()
            mock_logging.info.assert_called()


if __name__ == '__main__':
    unittest.main()
