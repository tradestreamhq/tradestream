import unittest
from unittest.mock import Mock, patch, MagicMock, call
from influxdb_client import InfluxDBClient
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

        with patch(
            "shared.persistence.influxdb_last_processed_tracker.logging"
        ) as mock_logging:
            tracker = InfluxDBLastProcessedTracker(
                self.url, self.token, self.org, self.bucket
            )
            self.assertIsNone(tracker.client)

            # Use a more flexible assertion approach
            error_calls = [str(call) for call in mock_logging.error.call_args_list]
            expected_message = f"InfluxDBLastProcessedTracker: __init__ failed to connect to InfluxDB at {self.url} after all retries."

            found_expected_message = any(
                expected_message in call for call in error_calls
            )
            self.assertTrue(
                found_expected_message,
                f"Expected error message not found. Expected: '{expected_message}'. Actual calls: {error_calls}",
            )

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_initialization_connection_error(self, mock_logging):
        """Test initialization when connection fails and all retries are exhausted."""
        self.mock_client_class.side_effect = ConnectionError(
            "Connection failed on all attempts"
        )

        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Verify that error logging occurred (at least one error call should be made)
        self.assertTrue(mock_logging.error.called, "Expected error logging to occur")

        # Verify that client is None (this is the main behavioral assertion)
        self.assertIsNone(tracker.client)

        # Verify that multiple connection attempts were made due to retries
        self.assertEqual(self.mock_client_class.call_count, 5)

        # Optional: Check that the final error message contains key information
        error_calls = [str(call) for call in mock_logging.error.call_args_list]
        has_init_failure_message = any(
            "__init__ failed to connect" in call for call in error_calls
        )
        self.assertTrue(
            has_init_failure_message, "Expected __init__ failure message in logs"
        )

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

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_get_last_processed_timestamp_client_not_initialized_attempts_reconnect(
        self, mock_logging
    ):
        """Test get when client is initially None, attempts reconnect, and succeeds."""
        # Simulate __init__ failing to connect
        self.mock_client_class.side_effect = RetryError("Initial connection failed")

        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.assertIsNone(tracker.client)  # Client should be None after failed __init__

        # Reset side effect for InfluxDBClient constructor for the reconnect attempt
        # The first call to _connect_with_retry (from get_last_processed_timestamp_retryable) should succeed.
        mock_reconnected_client_instance = Mock()
        mock_reconnected_client_instance.ping.return_value = True
        mock_query_api = Mock()
        mock_reconnected_client_instance.query_api.return_value = mock_query_api
        mock_query_api.query.return_value = (
            []
        )  # Simulate no data found after reconnect for simplicity

        # Patch _connect_with_retry directly on the instance to control its behavior for this test
        with patch.object(
            tracker, "_connect_with_retry"
        ) as mock_instance_connect_with_retry:

            def side_effect_for_reconnect():
                # Simulate successful connection by setting the client on the tracker instance
                tracker.client = mock_reconnected_client_instance

            mock_instance_connect_with_retry.side_effect = side_effect_for_reconnect

            result = tracker.get_last_processed_timestamp("test_service", "test_key")

            mock_instance_connect_with_retry.assert_called_once()  # Ensure reconnect was attempted
            self.assertIsNone(result)  # Expecting None as query returns empty
            mock_query_api.query.assert_called_once()

    def test_get_last_processed_timestamp_query_api_failure(self):
        """Test retrieval when query_api returns None"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        # This scenario is less likely if client.ping() succeeded, but good to test
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
            # Check for the actual error message format
            found_error = False
            for call_args in mock_logging.error.call_args_list:
                if "Query for test_service / test_key failed after all retries" in str(
                    call_args
                ):
                    found_error = True
                    break
            self.assertTrue(
                found_error, "Expected error message not found in log calls"
            )

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

        # Verify the write call parameters
        call_args = mock_write_api.write.call_args
        self.assertEqual(call_args[1]["bucket"], self.bucket)
        self.assertEqual(call_args[1]["org"], self.org)

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_update_last_processed_timestamp_client_not_initialized(self, mock_logging):
        """Test update when client is not initialized, attempts reconnect"""
        # Simulate __init__ failing to connect
        self.mock_client_class.side_effect = RetryError("Initial connection failed")
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.assertIsNone(tracker.client)

        # Patch _connect_with_retry on the instance to simulate failed reconnect
        with patch.object(
            tracker, "_connect_with_retry", side_effect=RetryError("Reconnect failed")
        ):
            # Should not raise exception out of the public method, just log error
            tracker.update_last_processed_timestamp(
                "test_service", "test_key", 1234567890123
            )
            # Check for error message about update failing
            found_error = False
            for call_args in mock_logging.error.call_args_list:
                if (
                    "Update for test_service / test_key failed after all retries"
                    in str(call_args)
                ):
                    found_error = True
                    break
            self.assertTrue(
                found_error, "Expected error message not found in log calls"
            )

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_update_last_processed_timestamp_write_api_failure(self, mock_logging):
        """Test update when write_api returns None"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.mock_client_instance.write_api.return_value = None

        # Should not raise exception, just log error
        tracker.update_last_processed_timestamp(
            "test_service", "test_key", 1234567890123
        )
        mock_logging.error.assert_any_call(
            "InfluxDBLastProcessedTracker: Failed to get write_api in _update_last_processed_timestamp_retryable."
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
            side_effect=RetryError("All retries failed for update"),
        ):
            # Should not raise exception, just log error
            tracker.update_last_processed_timestamp(
                "test_service", "test_key", 1234567890123
            )
            # Check for error message about update failing
            found_error = False
            for call_args in mock_logging.error.call_args_list:
                if (
                    "Update for test_service / test_key failed after all retries"
                    in str(call_args)
                ):
                    found_error = True
                    break
            self.assertTrue(
                found_error, "Expected error message not found in log calls"
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
        # Simulate __init__ failing
        self.mock_client_class.side_effect = RetryError("Initial connection failed")
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.assertIsNone(tracker.client)

        # Should not raise exception
        tracker.close()
        # mock_client_instance.close should not have been called as tracker.client was None
        self.mock_client_instance.close.assert_not_called()

    def test_retry_decorator_configuration(self):
        """Test that retry decorators are properly configured by checking method attributes"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Check if the methods have retry attributes indicating they are decorated
        # The tenacity.retry decorator adds specific attributes to decorated functions
        self.assertTrue(hasattr(tracker._connect_with_retry, "__wrapped__"))
        self.assertTrue(
            hasattr(tracker._get_last_processed_timestamp_retryable, "__wrapped__")
        )
        self.assertTrue(
            hasattr(tracker._update_last_processed_timestamp_retryable, "__wrapped__")
        )

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_reconnect_on_get_failure(self, mock_logging):
        """Test that get operation attempts reconnect when client is None and reconnect succeeds."""
        # Simulate __init__ failing to connect initially
        self.mock_client_class.side_effect = RetryError("Initial connection failed")
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.assertIsNone(
            tracker.client, "Client should be None after failed initialization"
        )

        # Setup mock for a successful reconnection attempt
        mock_reconnected_client_instance = Mock(spec=InfluxDBClient)
        mock_reconnected_client_instance.ping.return_value = True
        mock_query_api = Mock()
        mock_reconnected_client_instance.query_api.return_value = mock_query_api
        # Simulate no data found after successful reconnect for simplicity
        mock_query_api.query.return_value = []

        # Patch _connect_with_retry on the *instance* of the tracker
        with patch.object(
            tracker, "_connect_with_retry"
        ) as mock_instance_connect_retry:
            # Define side effect for the patched _connect_with_retry
            def successful_reconnect_side_effect():
                tracker.client = mock_reconnected_client_instance  # Simulate client being set on successful reconnect

            mock_instance_connect_retry.side_effect = successful_reconnect_side_effect

            # Act
            result = tracker.get_last_processed_timestamp("test_service", "test_key")

            # Assert
            mock_instance_connect_retry.assert_called_once()  # Verify _connect_with_retry was called
            self.assertIsNotNone(tracker.client, "Client should be reconnected")
            self.assertEqual(tracker.client, mock_reconnected_client_instance)
            mock_query_api.query.assert_called_once()  # Verify query was made after reconnect
            self.assertIsNone(result)  # As query returns no data

    @patch("shared.persistence.influxdb_last_processed_tracker.logging")
    def test_reconnect_on_update_failure(self, mock_logging):
        """Test that update operation attempts reconnect when client is None and reconnect succeeds."""
        self.mock_client_class.side_effect = RetryError("Initial connection failed")
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )
        self.assertIsNone(
            tracker.client, "Client should be None after failed initialization"
        )

        mock_reconnected_client_instance = Mock(spec=InfluxDBClient)
        mock_reconnected_client_instance.ping.return_value = True
        mock_write_api = Mock()
        mock_reconnected_client_instance.write_api.return_value = mock_write_api

        with patch.object(
            tracker, "_connect_with_retry"
        ) as mock_instance_connect_retry:

            def successful_reconnect_side_effect():
                tracker.client = mock_reconnected_client_instance

            mock_instance_connect_retry.side_effect = successful_reconnect_side_effect

            tracker.update_last_processed_timestamp("test_service", "test_key", 12345)

            mock_instance_connect_retry.assert_called_once()
            self.assertIsNotNone(tracker.client)
            self.assertEqual(tracker.client, mock_reconnected_client_instance)
            mock_write_api.write.assert_called_once()

    def test_influxdb_error_handling(self):
        """Test handling of InfluxDB specific errors during query"""
        tracker = InfluxDBLastProcessedTracker(
            self.url, self.token, self.org, self.bucket
        )

        # Ensure client is valid initially
        self.assertIsNotNone(tracker.client)
        mock_query_api = Mock()
        self.mock_client_instance.query_api.return_value = mock_query_api

        # Create a proper mock response for InfluxDBError
        mock_response = Mock()
        mock_response.data = "error data"
        mock_response.status = 500
        mock_response.reason = "Internal Server Error"

        # Simulate InfluxDBError during the query operation, after initial connection
        mock_query_api.query.side_effect = InfluxDBError(response=mock_response)

        # The public method get_last_processed_timestamp should catch RetryError,
        # which wraps InfluxDBError after tenacity retries _get_last_processed_timestamp_retryable.
        result = tracker.get_last_processed_timestamp("test_service", "test_key")
        self.assertIsNone(result)
        # Verify query_api.query was called multiple times due to retries
        self.assertEqual(mock_query_api.query.call_count, 5)

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
            # Create a mock Point instance that will be returned by Point()
            mock_point_instance = MagicMock()
            mock_point_class.return_value = mock_point_instance
            # Ensure chained calls also return the mock_point_instance
            mock_point_instance.tag.return_value = mock_point_instance
            mock_point_instance.field.return_value = mock_point_instance

            tracker.update_last_processed_timestamp(
                "test_service", "test_key", 1234567890123
            )

            # Verify Point was created with correct measurement
            mock_point_class.assert_called_once_with("processing_state")

            # Verify tags and fields were set
            mock_point_instance.tag.assert_any_call(
                "service_identifier", "test_service"
            )
            mock_point_instance.tag.assert_any_call("key", "test_key")
            mock_point_instance.field.assert_called_once_with(
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
