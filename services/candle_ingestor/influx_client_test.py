import unittest
from unittest import mock
from unittest.mock import MagicMock, patch # Ensure MagicMock and patch are imported

# Your module to test
from services.candle_ingestor import influx_client
from services.candle_ingestor.influx_client import (
    INGESTOR_PROCESSING_STATE_MEASUREMENT,
    InfluxDBManager, # Already imported by test file structure
    Point # Import Point for type checking
)
import requests # For ConnectionError testing


# Mock the InfluxDBClient itself and its methods
@patch("services.candle_ingestor.influx_client.InfluxDBClient")
class TestInfluxDBManager(unittest.TestCase):
    def setUp(self):
        self.test_url = "http://fake-influx:8086"
        self.test_token = "fake-token"
        self.test_org = "fake-org"
        self.test_bucket = "fake-bucket"

        # For tests of methods other than _connect, we want _connect to "succeed" easily
        # by providing a readily available mock client.
        # The class decorator already mocks InfluxDBClient.
        # We can further refine the behavior of the instance returned by MockInfluxDBClient().
        self.mock_influx_client_instance = MagicMock()
        self.mock_query_api_instance = MagicMock()
        self.mock_write_api_instance = MagicMock()
        
        self.mock_influx_client_instance.query_api.return_value = self.mock_query_api_instance
        self.mock_influx_client_instance.write_api.return_value = self.mock_write_api_instance


    # The MockInfluxDBClient arg is passed by the class decorator
    def test_connect_success(self, MockInfluxDBClient):
        # Arrange
        # For _connect tests, we re-configure the mock_client_instance that _connect will use
        mock_client_instance_for_connect_test = MockInfluxDBClient.return_value
        mock_client_instance_for_connect_test.ping.return_value = True
        
        # Act
        # _connect is called in __init__
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        MockInfluxDBClient.assert_called_once_with(
            url=self.test_url, token=self.test_token, org=self.test_org
        )
        mock_client_instance.ping.assert_called_once()
        self.assertIsNotNone(manager.get_client())
        self.assertEqual(manager.get_bucket(), self.test_bucket)
        self.assertEqual(manager.get_org(), self.test_org)

    def test_connect_ping_fails(self, MockInfluxDBClient):
        # Arrange
        mock_client_instance = MockInfluxDBClient.return_value
        mock_client_instance.ping.return_value = False

        # Act
        # _connect is called in __init__
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        # Since _connect is decorated with tenacity, and ping() failing raises ConnectionError,
        # tenacity will retry. If all retries fail, _connect will re-raise the ConnectionError.
        # The __init__ catches this and sets self.client to None.
        self.assertIsNone(manager.client) # Check internal client state

    def test_connect_exception_on_client_creation(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.side_effect = Exception("Connection refused")

        # Act
        # _connect is called in __init__
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        self.assertIsNone(manager.client) # Check internal client state

    def test_connect_exception_on_ping(self, MockInfluxDBClient):
        # Arrange
        mock_client_instance_for_connect_test = MockInfluxDBClient.return_value
        # Simulate ping raising ConnectionError, as _connect does now
        mock_client_instance_for_connect_test.ping.side_effect = requests.exceptions.ConnectionError("Ping network error")

        # Act
        # _connect is called in __init__
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        self.assertIsNone(manager.get_client())

        # Assert
        self.assertIsNone(manager.client) # Check internal client state
    
    # For the following tests, we mock _connect to avoid its actual execution during InfluxDBManager initialization,
    # allowing us to set up the manager.client with our pre-configured mocks directly.
    @patch.object(InfluxDBManager, '_connect')
    def test_get_write_api_success(self, mock_connect, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        manager.client = self.mock_influx_client_instance # Assign pre-configured mock client

        # Act
        write_api = manager.get_write_api()

        # Assert
        self.assertEqual(write_api, self.mock_write_api_instance)
        self.mock_influx_client_instance.write_api.assert_called_once()

    @patch.object(InfluxDBManager, '_connect')
    def test_get_write_api_client_not_initialized(self, mock_connect, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        manager.client = None # Simulate client not being initialized

        # Act
        write_api = manager.get_write_api()

        # Assert
        self.assertIsNone(write_api)

    @patch.object(InfluxDBManager, '_connect')
    def test_get_query_api_success(self, mock_connect, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        manager.client = self.mock_influx_client_instance

        # Act
        query_api = manager.get_query_api()

        # Assert
        self.assertEqual(query_api, self.mock_query_api_instance)
        self.mock_influx_client_instance.query_api.assert_called_once()

    @patch.object(InfluxDBManager, '_connect')
    def test_get_query_api_client_not_initialized(self, mock_connect, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        manager.client = None

        # Act
        query_api = manager.get_query_api()

        # Assert
        self.assertIsNone(query_api)

    @patch.object(InfluxDBManager, '_connect')
    def test_close_client(self, mock_connect, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        manager.client = self.mock_influx_client_instance
        
        # Act
        manager.close()

        # Assert
        self.mock_influx_client_instance.close.assert_called_once()

    @patch.object(InfluxDBManager, '_connect')
    def test_close_client_not_initialized(self, mock_connect, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        manager.client = None # Simulate client not initialized
        # Also ensure get_client() returns None by making _connect (if called by get_client) effectively fail
        mock_connect.side_effect = requests.exceptions.ConnectionError("Simulated connect failure")


        # Act
        manager.close()  # Should not throw error

        # Assert
        self.mock_influx_client_instance.close.assert_not_called() # Original mock client shouldn't be used
        # Check that manager.client remains None after failed reconnection attempt in get_client
        self.assertIsNone(manager.client)


    # --- Tests for get_last_processed_timestamp ---
    @patch.object(InfluxDBManager, '_connect') # Patch _connect for these tests
    def test_get_last_processed_timestamp_found(self, mock_connect_ignored, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(self.test_url, self.test_token, self.test_org, self.test_bucket)
        manager.client = self.mock_influx_client_instance # Use pre-configured mock

        mock_table = MagicMock()
        mock_record = MagicMock()
        mock_record.values = {"last_processed_timestamp_ms": 1678886400000}
        mock_table.records = [mock_record]
        self.mock_query_api_instance.query.return_value = [mock_table]

        # Act
        timestamp = manager.get_last_processed_timestamp("btcusd", "backfill")

        # Assert
        self.assertEqual(timestamp, 1678886400000)
        expected_query = f"""
        from(bucket: "{self.test_bucket}")
          |> range(start: 0)
          |> filter(fn: (r) => r._measurement == "{INGESTOR_PROCESSING_STATE_MEASUREMENT}")
          |> filter(fn: (r) => r.symbol == "btcusd")
          |> filter(fn: (r) => r.ingestion_type == "backfill")
          |> sort(columns: ["_time"], desc: true)
          |> tail(n: 1)
          |> keep(columns: ["last_processed_timestamp_ms"])
        """
        self.mock_query_api_instance.query.assert_called_once_with(expected_query, org=self.test_org)

    @patch.object(InfluxDBManager, '_connect')
    def test_get_last_processed_timestamp_not_found_empty_result(self, mock_connect_ignored, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(self.test_url, self.test_token, self.test_org, self.test_bucket)
        manager.client = self.mock_influx_client_instance
        self.mock_query_api_instance.query.return_value = [] # No tables

        # Act
        timestamp = manager.get_last_processed_timestamp("ethusd", "polling")

        # Assert
        self.assertIsNone(timestamp)

    @patch.object(InfluxDBManager, '_connect')
    def test_get_last_processed_timestamp_not_found_no_records(self, mock_connect_ignored, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(self.test_url, self.test_token, self.test_org, self.test_bucket)
        manager.client = self.mock_influx_client_instance
        mock_table = MagicMock()
        mock_table.records = [] # No records in table
        self.mock_query_api_instance.query.return_value = [mock_table]

        # Act
        timestamp = manager.get_last_processed_timestamp("solusd", "backfill")

        # Assert
        self.assertIsNone(timestamp)

    @patch.object(InfluxDBManager, '_connect')
    @patch('services.candle_ingestor.influx_client.logging') # Mock logging
    def test_get_last_processed_timestamp_query_api_error(self, mock_logging, mock_connect_ignored, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(self.test_url, self.test_token, self.test_org, self.test_bucket)
        manager.client = self.mock_influx_client_instance
        self.mock_query_api_instance.query.side_effect = requests.exceptions.ConnectionError("API error")

        # Act
        timestamp = manager.get_last_processed_timestamp("solusd", "backfill")

        # Assert
        self.assertIsNone(timestamp)
        # Check if logging.error was called (method has its own logging for errors not caught by tenacity)
        # The method itself catches generic Exception and logs, then returns None.
        # Tenacity handles ConnectionError, so the method's own except block might not be hit for ConnectionError.
        # However, the method's structure has a general try-except that logs.
        # Let's assume the method's internal try-except for query is hit if tenacity fails or if it's a non-tenacity error
        # For this unit test, we are testing the method's behavior given the mocked call raises an error.
        # If tenacity is active on this method, it would retry. To test the non-retry path directly,
        # we'd typically mock what tenacity calls. But since tenacity itself calls query_api.query,
        # this setup is fine. The method's own try-except will be triggered if query_api.query raises
        # an error that is *not* handled by tenacity to the point of successful retry.
        # The current method get_last_processed_timestamp does have a try/except that logs error.
        # This test will verify that logging IF the exception somehow bypassed tenacity or if tenacity itself re-raised.
        # Given tenacity is on the method, if ConnectionError is raised by query(), tenacity should catch it.
        # The method's internal try-except will only be hit if tenacity re-raises after exhausting retries.
        # For this unit test, we'll assume the method's internal error logging is what we want to check
        # when the query_api.query call (which tenacity would make) ultimately fails.
        # A more direct test of the inner logic would involve mocking tenacity itself or testing a non-decorated version.
        # However, the current setup should show logging if the call fails after retries.
        # The method's final `except Exception as e:` block handles logging.
        # Tenacity should re-raise the original exception after retries are exhausted.
        # So, the method's `except Exception as e` should be hit.
        self.assertTrue(any("Error querying last processed timestamp" in call.args[0] for call in mock_logging.error.call_args_list))


    # --- Tests for update_last_processed_timestamp ---
    @patch.object(InfluxDBManager, '_connect')
    def test_update_last_processed_timestamp_success(self, mock_connect_ignored, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(self.test_url, self.test_token, self.test_org, self.test_bucket)
        manager.client = self.mock_influx_client_instance
        
        symbol = "btcusd"
        ingestion_type = "backfill"
        timestamp_ms = 1678886400000

        # Act
        manager.update_last_processed_timestamp(symbol, ingestion_type, timestamp_ms)

        # Assert
        self.mock_write_api_instance.write.assert_called_once()
        args, kwargs = self.mock_write_api_instance.write.call_args
        
        self.assertEqual(kwargs['bucket'], self.test_bucket)
        self.assertEqual(kwargs['org'], self.test_org)
        
        written_point = kwargs['record']
        self.assertIsInstance(written_point, Point)
        
        # Point's internal structure might vary slightly on access, typically _name, _tags, _fields
        self.assertEqual(written_point._name, INGESTOR_PROCESSING_STATE_MEASUREMENT)
        self.assertEqual(written_point._tags['symbol'], symbol)
        self.assertEqual(written_point._tags['ingestion_type'], ingestion_type)
        self.assertEqual(written_point._fields['last_processed_timestamp_ms'], timestamp_ms)

    @patch.object(InfluxDBManager, '_connect')
    @patch('services.candle_ingestor.influx_client.logging') # Mock logging
    def test_update_last_processed_timestamp_write_api_error(self, mock_logging, mock_connect_ignored, MockInfluxDBClient):
        # Arrange
        manager = InfluxDBManager(self.test_url, self.test_token, self.test_org, self.test_bucket)
        manager.client = self.mock_influx_client_instance
        self.mock_write_api_instance.write.side_effect = requests.exceptions.ConnectionError("API write error")

        # Act
        manager.update_last_processed_timestamp("ethusd", "polling", 1678886500000)

        # Assert
        # Similar to the query error, tenacity decorates this method.
        # The method's own try-except will be hit if tenacity re-raises.
        self.assertTrue(any("Error writing last processed timestamp" in call.args[0] for call in mock_logging.error.call_args_list))


if __name__ == "__main__":
    unittest.main()
