"""Unit tests for main module (stateless orchestration version)."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from datetime import datetime, timezone
from absl import flags
from absl.testing import flagsaver, absltest  # Changed from unittest to absltest
from services.strategy_discovery_request_factory import main

FLAGS = flags.FLAGS


class StatelessMainTest(absltest.TestCase):  # Changed from unittest.TestCase
    """Test stateless main orchestration functionality."""

    def setUp(self):
        """Set up test environment."""
        # Save original flags
        self.saved_flags = flagsaver.save_flag_values()

        # Set required flags for tests
        FLAGS.influxdb_token = "test-token"
        FLAGS.influxdb_org = "test-org"
        FLAGS.tracker_service_name = "test_strategy_discovery"
        FLAGS.global_status_tracker_service_name = "test_global_candle_status"
        FLAGS.min_processing_advance_minutes = 1

        # Mock all external dependencies
        self.mock_kafka_publisher_cls = patch(
            "services.strategy_discovery_request_factory.main.KafkaPublisher"
        ).start()
        self.mock_strategy_processor_cls = patch(
            "services.strategy_discovery_request_factory.main.StrategyDiscoveryProcessor"
        ).start()
        self.mock_tracker_cls = patch(
            "services.strategy_discovery_request_factory.main.InfluxDBLastProcessedTracker"
        ).start()

        # Mock instances
        self.mock_kafka_instance = Mock()
        self.mock_kafka_instance.producer = True  # Simulate successful connection
        self.mock_kafka_publisher_cls.return_value = self.mock_kafka_instance

        self.mock_processor_instance = Mock()
        self.mock_strategy_processor_cls.return_value = self.mock_processor_instance

        self.mock_tracker_instance = Mock()
        self.mock_tracker_instance.client = True  # Simulate successful connection
        self.mock_tracker_cls.return_value = self.mock_tracker_instance

        # Mock the currency pairs retrieval method
        self.currency_pairs_patcher = patch.object(
            main.StrategyDiscoveryService, "_get_currency_pairs_from_redis"
        )
        self.mock_get_currency_pairs = self.currency_pairs_patcher.start()
        self.mock_get_currency_pairs.return_value = ["BTC/USD", "ETH/USD"]

    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()
        flagsaver.restore_flag_values(self.saved_flags)

    def test_service_initialization_success(self):
        """Test successful service initialization."""
        service = main.StrategyDiscoveryService()

        service._connect_kafka()
        service._initialize_tracker()
        service._initialize_processor()

        # Verify components were initialized
        self.mock_kafka_publisher_cls.assert_called_once()
        self.mock_tracker_cls.assert_called_once()
        self.mock_strategy_processor_cls.assert_called_once()

    def test_validation_missing_influxdb_token(self):
        """Test validation fails without InfluxDB token."""
        FLAGS.influxdb_token = None
        service = main.StrategyDiscoveryService()

        with self.assertRaises(ValueError) as cm:
            service._validate_configuration()
        self.assertIn("InfluxDB token is required", str(cm.exception))

    def test_validation_missing_influxdb_org(self):
        """Test validation fails without InfluxDB org."""
        FLAGS.influxdb_org = None
        service = main.StrategyDiscoveryService()

        with self.assertRaises(ValueError) as cm:
            service._validate_configuration()
        self.assertIn("InfluxDB organization is required", str(cm.exception))

    def test_validation_negative_min_advance(self):
        """Test validation fails with negative min processing advance."""
        FLAGS.min_processing_advance_minutes = -1
        service = main.StrategyDiscoveryService()

        with self.assertRaises(ValueError) as cm:
            service._validate_configuration()
        self.assertIn(
            "Minimum processing advance minutes must be non-negative", str(cm.exception)
        )

    def test_tracker_key_generation(self):
        """Test tracker key generation methods."""
        service = main.StrategyDiscoveryService()

        # Test SDRF processed tracker key
        sdrf_key = service._get_sdrf_processed_tracker_key("BTC/USD")
        expected_sdrf = f"{FLAGS.tracker_service_name}_BTC_USD_sdrf_processed_end_ts"
        self.assertEqual(sdrf_key, expected_sdrf)

        # Test ingested data tracker item ID
        ingested_id = service._get_ingested_data_tracker_item_id("ETH/USD")
        expected_ingested = "ETH_USD_latest_ingested_ts"
        self.assertEqual(ingested_id, expected_ingested)

    def test_run_no_latest_data_timestamp(self):
        """Test run when no latest data timestamp is available."""
        # Mock tracker to return None for latest data timestamp
        self.mock_tracker_instance.get_last_processed_timestamp.return_value = None

        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance
        service.strategy_processor = self.mock_processor_instance
        service.fibonacci_windows_config = [60, 120]

        service.run()

        # Should skip processing and log warning
        self.mock_processor_instance.generate_requests_for_timepoint.assert_not_called()
        self.mock_kafka_instance.publish_request.assert_not_called()

    def test_run_insufficient_advance(self):
        """Test run when data hasn't advanced sufficiently."""
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Mock tracker returns - latest data only 30 seconds newer than last processed
        def mock_get_timestamp(service_name, item_id):
            if "latest_ingested_ts" in item_id:
                return current_time_ms  # Latest data timestamp
            else:
                return current_time_ms - 30000  # Last processed (30 seconds ago)

        self.mock_tracker_instance.get_last_processed_timestamp.side_effect = (
            mock_get_timestamp
        )

        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance
        service.strategy_processor = self.mock_processor_instance
        service.fibonacci_windows_config = [60, 120]

        service.run()

        # Should skip processing due to insufficient advance (less than 1 minute)
        self.mock_processor_instance.generate_requests_for_timepoint.assert_not_called()
        self.mock_kafka_instance.publish_request.assert_not_called()

    def test_run_sufficient_advance_generates_requests(self):
        """Test run when data has advanced sufficiently."""
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Mock tracker returns - latest data 2 minutes newer than last processed
        def mock_get_timestamp(service_name, item_id):
            if "latest_ingested_ts" in item_id:
                return current_time_ms  # Latest data timestamp
            else:
                return current_time_ms - 120000  # Last processed (2 minutes ago)

        self.mock_tracker_instance.get_last_processed_timestamp.side_effect = (
            mock_get_timestamp
        )

        # Mock processor generates 2 requests
        mock_requests = [Mock(), Mock()]
        self.mock_processor_instance.generate_requests_for_timepoint.return_value = (
            mock_requests
        )

        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance
        service.strategy_processor = self.mock_processor_instance
        service.fibonacci_windows_config = [60, 120]

        service.run()

        # Should generate and publish requests
        self.assertEqual(
            self.mock_processor_instance.generate_requests_for_timepoint.call_count, 2
        )  # BTC and ETH
        self.assertEqual(
            self.mock_kafka_instance.publish_request.call_count, 4
        )  # 2 requests per pair

        # Should update tracker timestamps
        self.mock_tracker_instance.update_last_processed_timestamp.assert_called()

    def test_run_no_requests_generated(self):
        """Test run when processor generates no requests."""
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Mock sufficient advance
        def mock_get_timestamp(service_name, item_id):
            if "latest_ingested_ts" in item_id:
                return current_time_ms
            else:
                return current_time_ms - 120000

        self.mock_tracker_instance.get_last_processed_timestamp.side_effect = (
            mock_get_timestamp
        )

        # Mock processor generates no requests
        self.mock_processor_instance.generate_requests_for_timepoint.return_value = []

        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance
        service.strategy_processor = self.mock_processor_instance
        service.fibonacci_windows_config = [60, 120]

        service.run()

        # Should not publish anything or update tracker
        self.mock_kafka_instance.publish_request.assert_not_called()
        self.mock_tracker_instance.update_last_processed_timestamp.assert_not_called()

    def test_run_first_time_processing(self):
        """Test run when processing pair for first time (no prior SDRF state)."""
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Mock tracker returns - has latest data, no prior SDRF processing
        def mock_get_timestamp(service_name, item_id):
            if "latest_ingested_ts" in item_id:
                return current_time_ms  # Latest data timestamp
            else:
                return None  # No prior SDRF processing

        self.mock_tracker_instance.get_last_processed_timestamp.side_effect = (
            mock_get_timestamp
        )

        # Mock processor generates requests
        mock_requests = [Mock()]
        self.mock_processor_instance.generate_requests_for_timepoint.return_value = (
            mock_requests
        )

        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance
        service.strategy_processor = self.mock_processor_instance
        service.fibonacci_windows_config = [60]

        service.run()

        # Should process since it's first time (None gets converted to 0)
        self.mock_processor_instance.generate_requests_for_timepoint.assert_called()
        self.mock_kafka_instance.publish_request.assert_called()

    def test_run_error_handling_continues_processing(self):
        """Test that error in one pair doesn't stop processing of others."""
        current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Mock tracker behavior - first pair fails, second succeeds
        call_count = 0

        def mock_get_timestamp_with_error(service_name, item_id):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First pair's calls
                if call_count == 1:
                    raise Exception("Tracker error for first pair")
                return current_time_ms
            else:  # Second pair's calls
                if "latest_ingested_ts" in item_id:
                    return current_time_ms
                else:
                    return current_time_ms - 120000

        self.mock_tracker_instance.get_last_processed_timestamp.side_effect = (
            mock_get_timestamp_with_error
        )
        self.mock_processor_instance.generate_requests_for_timepoint.return_value = [
            Mock()
        ]

        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance
        service.strategy_processor = self.mock_processor_instance
        service.fibonacci_windows_config = [60]

        # Should not raise exception despite first pair failing
        service.run()

        # Should still process second pair
        self.mock_processor_instance.generate_requests_for_timepoint.assert_called()

    def test_run_all_pairs_fail_raises_exception(self):
        """Test that if all pairs fail, an exception is raised."""
        # Mock tracker to always raise exception
        self.mock_tracker_instance.get_last_processed_timestamp.side_effect = Exception(
            "All pairs fail"
        )

        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance
        service.strategy_processor = self.mock_processor_instance
        service.fibonacci_windows_config = [60]

        with self.assertRaises(Exception) as cm:
            service.run()
        self.assertIn("All currency pairs failed to process", str(cm.exception))

    def test_close_cleans_up_resources(self):
        """Test that close method cleans up all resources."""
        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance

        service.close()

        self.mock_kafka_instance.close.assert_called_once()
        self.mock_tracker_instance.close.assert_called_once()

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_entry_point_success(self, mock_exit):
        """Test main entry point with successful execution."""
        with patch.object(main.StrategyDiscoveryService, "run") as mock_run:
            main.main([])
            mock_run.assert_called_once()
            mock_exit.assert_not_called()

    @patch("services.strategy_discovery_request_factory.main.sys.exit")
    def test_main_entry_point_failure(self, mock_exit):
        """Test main entry point with execution failure."""
        with patch.object(main.StrategyDiscoveryService, "run") as mock_run:
            mock_run.side_effect = Exception("Service failed")

            main.main([])

            mock_run.assert_called_once()
            mock_exit.assert_called_once_with(1)

    def test_main_entry_point_too_many_args(self):
        """Test main entry point with too many arguments."""
        with self.assertRaises(Exception):  # app.UsageError
            main.main(["arg1", "arg2"])

    @patch("services.strategy_discovery_request_factory.main.logging")
    def test_logging_behavior(self, mock_logging):
        """Test that appropriate logging occurs."""
        service = main.StrategyDiscoveryService()
        service.kafka_publisher = self.mock_kafka_instance
        service.timestamp_tracker = self.mock_tracker_instance
        service.strategy_processor = self.mock_processor_instance
        service.fibonacci_windows_config = [60]

        # Mock no data available
        self.mock_tracker_instance.get_last_processed_timestamp.return_value = None

        service.run()

        # Verify logging calls
        mock_logging.info.assert_called()
        mock_logging.warning.assert_called()


if __name__ == "__main__":
    absltest.main()
