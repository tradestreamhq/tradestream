import unittest
from unittest.mock import Mock, patch, MagicMock, call
from influxdb_client.client.exceptions import InfluxDBError
from tenacity import RetryError

# Import the class under test
from shared.persistence.influxdb_last_processed_tracker import (
    InfluxDBLastProcessedTracker,
)
from absl import logging

# It's good practice to ensure logging is configured for tests if the module uses it.
logging.set_verbosity(logging.INFO)


class TestInfluxDBLastProcessedTracker(unittest.TestCase):
    """Comprehensive test suite for InfluxDBLastProcessedTracker"""

    def setUp(self):
        """Set up test fixtures"""
        self.url = "http://localhost:8086"
        self.token = "test-token"
        self.org = "test-org"
        self.bucket = "test-bucket"

        # Mock InfluxDBClient to avoid actual connections in tests
        self.mock_client_patcher = patch(
            "shared.persistence.influxdb_last_processed_tracker.InfluxDBClient"
        )
        self.mock_client_class = self.mock_client_patcher.start()
        self.mock_client_instance = Mock()
        self.mock_client_class.return_value = self.mock_client_instance

        # Setup default successful ping
        self.mock_client_instance.ping.return_value = True

    def tearDown(self):
        """Clean up test fixtures"""
        self.mock_client_patcher.stop()

    def test_successful_initialization(self):
        """Test successful initialization and connection"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Verify client was created with correct parameters
        self.mock_client_class.assert_called_once_with(
            url=self.url, token=self.token, org=self.org
        )

        # Verify ping was called
        self.mock_client_instance.ping.assert_called_once()

        # Verify instance variables
        self.assertEqual(tracker.url, self.url)
        self.assertEqual(tracker.token, self.token)
        self.assertEqual(tracker.org, self.org)
        self.assertEqual(tracker.bucket, self.bucket)
        self.assertEqual(tracker.client, self.mock_client_instance)

    def test_initialization_ping_failure(self):
        """Test initialization when ping fails"""
        self.mock_client_instance.ping.return_value = False

        with self.assertRaises(InfluxDBError):
            InfluxDBLastProcessedTracker(self.url, self.token, self.org, self.bucket)

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_initialization_connection_error(self, mock_logging):
        """Test initialization when connection fails"""
        self.mock_client_class.side_effect = ConnectionError("Connection failed")

        with self.assertRaises(ConnectionError):
            InfluxDBLastProcessedTracker(self.url, self.token, self.org, self.bucket)

    def test_get_last_processed_timestamp_success(self):
        """Test successful retrieval of last processed timestamp"""
        # Setup
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        mock_query_api = Mock()
        self.mock_client_instance.query_api.return_value = mock_query_api

        # Mock query result
        mock_record = Mock()
        mock_record.get_value.return_value = 1234567890123
        mock_table = Mock()
        mock_table.records = [mock_record]
        mock_query_api.query.return_value = [mock_table]

        # Execute
        result = tracker.get_last_processed_timestamp("test_service", "test_key")

        # Verify
        self.assertEqual(result, 1234567890123)
        mock_query_api.query.assert_called_once()

        # Verify the Flux query was constructed correctly
        call_args = mock_query_api.query.call_args
        query = call_args[1]["query"]
        self.assertIn("test_service", query)
        self.assertIn("test_key", query)
        self.assertIn("processing_state", query)

    def test_get_last_processed_timestamp_no_results(self):
        """Test retrieval when no prior state exists"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        mock_query_api = Mock()
        self.mock_client_instance.query_api.return_value = mock_query_api
        mock_query_api.query.return_value = []  # No results

        result = tracker.get_last_processed_timestamp("test_service", "test_key")

        self.assertIsNone(result)

    def test_get_last_processed_timestamp_client_not_initialized(self):
        """Test retrieval when client is not initialized"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        tracker.client = None

        result = tracker.get_last_processed_timestamp("test_service", "test_key")

        self.assertIsNone(result)

    def test_get_last_processed_timestamp_query_api_failure(self):
        """Test retrieval when query_api returns None"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.mock_client_instance.query_api.return_value = None

        result = tracker.get_last_processed_timestamp("test_service", "test_key")

        self.assertIsNone(result)

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_get_last_processed_timestamp_retry_error(self, mock_logging):
        """Test retrieval with retry error"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Mock the retryable method to raise RetryError
        with patch.object(
            tracker,
            "_get_last_processed_timestamp_retryable",
            side_effect=RetryError("All retries failed"),
        ):
            result = tracker.get_last_processed_timestamp("test_service", "test_key")

            self.assertIsNone(result)

    def test_update_last_processed_timestamp_success(self):
        """Test successful update of last processed timestamp"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        mock_write_api = Mock()
        self.mock_client_instance.write_api.return_value = mock_write_api

        # Execute
        tracker.update_last_processed_timestamp(
            "test_service", "test_key", 1234567890123
        )

        # Verify write_api was called
        self.mock_client_instance.write_api.assert_called_once()
        mock_write_api.write.assert_called_once()

        # Verify the write call parameters
        call_args = mock_write_api.write.call_args
        self.assertEqual(call_args[1]["bucket"], self.bucket)
        self.assertEqual(call_args[1]["org"], self.org)

    def test_update_last_processed_timestamp_client_not_initialized(self):
        """Test update when client is not initialized"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        tracker.client = None

        # Should not raise exception, just log error
        tracker.update_last_processed_timestamp(
            "test_service", "test_key", 1234567890123
        )

    def test_update_last_processed_timestamp_write_api_failure(self):
        """Test update when write_api returns None"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.mock_client_instance.write_api.return_value = None

        # Should not raise exception, just log error
        tracker.update_last_processed_timestamp(
            "test_service", "test_key", 1234567890123
        )

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_update_last_processed_timestamp_retry_error(self, mock_logging):
        """Test update with retry error"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Mock the retryable method to raise RetryError
        with patch.object(
            tracker,
            "_update_last_processed_timestamp_retryable",
            side_effect=RetryError("All retries failed"),
        ):
            # Should not raise exception, just log error
            tracker.update_last_processed_timestamp(
                "test_service", "test_key", 1234567890123
            )

    def test_close_success(self):
        """Test successful client closure"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        tracker.close()

        self.mock_client_instance.close.assert_called_once()
        self.assertIsNone(tracker.client)

    def test_close_with_exception(self):
        """Test client closure when close() raises exception"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.mock_client_instance.close.side_effect = Exception("Close failed")

        # Should not raise exception
        tracker.close()

        # Client should still be set to None
        self.assertIsNone(tracker.client)

    def test_close_when_client_is_none(self):
        """Test close when client is already None"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        tracker.client = None

        # Should not raise exception
        tracker.close()

    @patch("shared.persistence.influxdb_last_processed_tracker.retry")
    def test_retry_decorator_parameters(self, mock_retry):
        """Test that retry decorators are configured correctly"""
        # This test verifies the retry configuration is applied
        # The actual retry behavior is tested implicitly in other tests

        # Just create an instance to trigger the decorators
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Verify retry was called (decorators are applied at import time)
        self.assertTrue(mock_retry.called)

    def test_reconnect_on_get_failure(self):
        """Test that get operation attempts reconnect when client is None"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Simulate client becoming None
        tracker.client = None

        # Setup mock for reconnection
        new_mock_client = Mock()
        new_mock_client.ping.return_value = True
        new_mock_client.query_api.return_value = Mock()
        new_mock_client.query_api.return_value.query.return_value = []

        with patch.object(tracker, "_connect_with_retry") as mock_connect:

            def mock_reconnect():
                tracker.client = new_mock_client

            mock_connect.side_effect = mock_reconnect

            result = tracker.get_last_processed_timestamp("test_service", "test_key")

            # Verify reconnection was attempted
            mock_connect.assert_called_once()
            self.assertIsNone(result)  # No results in mock

    def test_reconnect_on_update_failure(self):
        """Test that update operation attempts reconnect when client is None"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Simulate client becoming None
        tracker.client = None

        # Setup mock for reconnection
        new_mock_client = Mock()
        new_mock_client.ping.return_value = True
        new_mock_client.write_api.return_value = Mock()

        with patch.object(tracker, "_connect_with_retry") as mock_connect:

            def mock_reconnect():
                tracker.client = new_mock_client

            mock_connect.side_effect = mock_reconnect

            tracker.update_last_processed_timestamp(
                "test_service", "test_key", 1234567890123
            )

            # Verify reconnection was attempted
            mock_connect.assert_called_once()

    def test_influxdb_error_handling(self):
        """Test handling of InfluxDB specific errors"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        mock_query_api = Mock()
        self.mock_client_instance.query_api.return_value = mock_query_api
        mock_query_api.query.side_effect = InfluxDBError("Database error")

        with patch.object(
            tracker,
            "_get_last_processed_timestamp_retryable",
            side_effect=InfluxDBError("Database error"),
        ):
            # The retry mechanism should handle this, but if all retries fail,
            # it should return None gracefully
            result = tracker.get_last_processed_timestamp("test_service", "test_key")
            self.assertIsNone(result)

    def test_measurement_name_constant(self):
        """Test that the measurement name is correctly defined"""
        self.assertEqual(
            InfluxDBLastProcessedTracker.MEASUREMENT_NAME, "processing_state"
        )

    def test_point_construction(self):
        """Test that InfluxDB points are constructed correctly"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        mock_write_api = Mock()
        self.mock_client_instance.write_api.return_value = mock_write_api

        # Mock Point to capture how it's constructed
        with patch(
            "shared.persistence.influxdb_last_processed_tracker.Point"
        ) as mock_point_class:
            mock_point = Mock()
            mock_point_class.return_value = mock_point

            # Chain method calls
            mock_point.tag.return_value = mock_point
            mock_point.field.return_value = mock_point

            tracker.update_last_processed_timestamp(
                "test_service", "test_key", 1234567890123
            )

            # Verify Point was created with correct measurement
            mock_point_class.assert_called_once_with("processing_state")

            # Verify tags and fields were set
            mock_point.tag.assert_any_call("service_identifier", "test_service")
            mock_point.tag.assert_any_call("key", "test_key")
            mock_point.field.assert_called_once_with(
                "last_processed_timestamp_ms", 1234567890123
            )


class TestInfluxDBLastProcessedTrackerIntegration(unittest.TestCase):
    """Integration-style tests that test multiple components together"""

    @patch("shared.persistence.influxdb_last_processed_tracker.InfluxDBClient")
    def test_full_workflow(self, mock_client_class):
        """Test a complete workflow of init -> get -> update -> close"""
        # Setup mocks
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.ping.return_value = True

        # Mock query (no existing data)
        mock_query_api = Mock()
        mock_client.query_api.return_value = mock_query_api
        mock_query_api.query.return_value = []

        # Mock write
        mock_write_api = Mock()
        mock_client.write_api.return_value = mock_write_api

        # Execute workflow
        tracker = InfluxDBLastProcessedTracker("http://test", "token", "org", "bucket")

        # Get (should return None - no existing data)
        result = tracker.get_last_processed_timestamp("service1", "key1")
        self.assertIsNone(result)

        # Update
        tracker.update_last_processed_timestamp("service1", "key1", 9999999999)

        # Close
        tracker.close()

        # Verify all operations were called
        mock_client.ping.assert_called()
        mock_query_api.query.assert_called()
        mock_write_api.write.assert_called()
        mock_client.close.assert_called()


class TestInfluxDBLastProcessedTrackerAdvanced(unittest.TestCase):
    """Additional tests for more advanced scenarios, adapted from pytest style."""

    def setUp(self):
        self.patcher = patch(
            "shared.persistence.influxdb_last_processed_tracker.InfluxDBClient"
        )
        self.mock_client_class = self.patcher.start()
        self.mock_client_instance = Mock()
        self.mock_client_class.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        self.tracker = InfluxDBLastProcessedTracker(
            "http://test", "token", "org", "bucket"
        )
        # Store mock_client_instance on tracker for access in tests, similar to pytest fixture
        self.tracker.mock_client = self.mock_client_instance

    def tearDown(self):
        self.patcher.stop()

    def test_concurrent_operations_simulation(self):
        """Test behavior under concurrent-like conditions (simulated)"""
        mock_query_api = Mock()
        self.tracker.mock_client.query_api.return_value = mock_query_api
        mock_query_api.query.return_value = []

        # Multiple rapid calls
        for i in range(10):
            result = self.tracker.get_last_processed_timestamp(
                f"service_{i}", f"key_{i}"
            )
            self.assertIsNone(result)

    def test_various_service_key_combinations(self):
        """Test with various service and key name combinations"""
        test_cases = [
            ("service1", "key1", 1000000000000),
            ("service_with_special_chars", "key-with-dashes", 2000000000000),
            ("UPPER_SERVICE", "UPPER_KEY", 3000000000000),
            ("service.with.dots", "key_with_underscores", 4000000000000),
        ]

        mock_write_api = Mock()
        self.tracker.mock_client.write_api.return_value = mock_write_api

        for service, key, timestamp in test_cases:
            with self.subTest(service=service, key=key, timestamp=timestamp):
                mock_write_api.reset_mock()  # Reset mock for each subtest
                self.tracker.update_last_processed_timestamp(service, key, timestamp)
                # Verify the write was called
                mock_write_api.write.assert_called_once()


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
