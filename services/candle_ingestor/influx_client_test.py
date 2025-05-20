import unittest
from unittest import mock

# Your module to test
from services.candle_ingestor import influx_client
from influxdb_client import InfluxDBClient, Point, WritePrecision # Added Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError # Added InfluxDBError


# Mock the InfluxDBClient itself and its methods
@mock.patch("services.candle_ingestor.influx_client.InfluxDBClient")
class TestInfluxDBManager(unittest.TestCase):
    def setUp(self):
        self.test_url = "http://fake-influx:8086"
        self.test_token = "fake-token"
        self.test_org = "fake-org"
        self.test_bucket = "fake-bucket"

        # Mock instances that will be returned by InfluxDBClient()
        self.mock_client_instance = mock.MagicMock(spec=InfluxDBClient)
        self.mock_write_api_instance = mock.MagicMock()
        self.mock_query_api_instance = mock.MagicMock()

        # Configure client instance to return mock APIs
        self.mock_client_instance.write_api.return_value = self.mock_write_api_instance
        self.mock_client_instance.query_api.return_value = self.mock_query_api_instance


    def test_connect_success(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance # Ensure our mock is used
        self.mock_client_instance.ping.return_value = True

        # Act
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        MockInfluxDBClient.assert_called_once_with(
            url=self.test_url, token=self.test_token, org=self.test_org
        )
        self.mock_client_instance.ping.assert_called_once()
        self.assertIsNotNone(manager.get_client())
        self.assertEqual(manager.get_bucket(), self.test_bucket)
        self.assertEqual(manager.get_org(), self.test_org)

    def test_connect_ping_fails(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = False

        # Act
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        self.assertIsNone(manager.get_client())

    def test_connect_exception_on_client_creation(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.side_effect = Exception("Connection refused")

        # Act
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        self.assertIsNone(manager.get_client())

    def test_connect_exception_on_ping(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.side_effect = Exception("Ping network error")

        # Act
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        self.assertIsNone(manager.get_client())

    def test_get_write_api_success(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        # self.mock_write_api_instance is already set up in setUp

        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        write_api = manager.get_write_api()

        # Assert
        self.assertEqual(write_api, self.mock_write_api_instance)
        self.mock_client_instance.write_api.assert_called_once()

    def test_get_write_api_client_not_initialized(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value.ping.return_value = False  # Ensure client is None
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        write_api = manager.get_write_api()

        # Assert
        self.assertIsNone(write_api)

    def test_get_query_api_success(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        # self.mock_query_api_instance is already set up in setUp

        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        query_api = manager.get_query_api()

        # Assert
        self.assertEqual(query_api, self.mock_query_api_instance)
        self.mock_client_instance.query_api.assert_called_once()

    def test_get_query_api_client_not_initialized(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value.ping.return_value = False  # Ensure client is None
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        query_api = manager.get_query_api()

        # Assert
        self.assertIsNone(query_api)

    def test_close_client(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        self.assertIsNotNone(manager.get_client())

        # Act
        manager.close()

        # Assert
        self.mock_client_instance.close.assert_called_once()

    def test_close_client_not_initialized(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value.ping.return_value = False # Client is None
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        manager.close()  # Should not throw error

        # Assert
        self.mock_client_instance.close.assert_not_called() # close on the *instance*

    # --- New tests for state management ---

    def test_get_last_processed_timestamp_success(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        mock_table = mock.MagicMock()
        mock_record = mock.MagicMock()
        mock_record.get_value.return_value = 1678886400000 # Example timestamp
        mock_table.records = [mock_record]
        self.mock_query_api_instance.query.return_value = [mock_table]

        symbol = "btcusd"
        ingestion_type = "backfill"

        # Act
        timestamp = manager.get_last_processed_timestamp(symbol, ingestion_type)

        # Assert
        self.assertEqual(timestamp, 1678886400000)
        expected_query = f'''
        from(bucket: "{self.test_bucket}")
          |> range(start: 0)
          |> filter(fn: (r) => r._measurement == "ingestor_processing_state")
          |> filter(fn: (r) => r.symbol == "{symbol}")
          |> filter(fn: (r) => r.ingestion_type == "{ingestion_type}")
          |> filter(fn: (r) => r._field == "last_processed_timestamp_ms")
          |> sort(columns: ["_time"], desc: true)
          |> limit(n: 1)
          |> yield(name: "last")
        '''
        self.mock_query_api_instance.query.assert_called_once_with(query=mock.ANY, org=self.test_org)
        # More precise query matching if needed, by capturing the query argument
        args, kwargs = self.mock_query_api_instance.query.call_args
        self.assertEqual(kwargs['query'].strip(), expected_query.strip())


    def test_get_last_processed_timestamp_no_data(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        self.mock_query_api_instance.query.return_value = [] # No tables/records

        # Act
        timestamp = manager.get_last_processed_timestamp("ethusd", "polling")

        # Assert
        self.assertIsNone(timestamp)

    def test_get_last_processed_timestamp_influxdb_error(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        
        # Create a mock response object for InfluxDBError
        mock_response = mock.MagicMock()
        mock_response.data = "Simulated DB Error"
        mock_response.status = 500
        
        self.mock_query_api_instance.query.side_effect = InfluxDBError(response=mock_response)

        # Act
        timestamp = manager.get_last_processed_timestamp("adausd", "backfill")

        # Assert
        self.assertIsNone(timestamp) # Should handle error and return None

    def test_update_last_processed_timestamp_writes_correct_point(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        symbol = "btcusd"
        ingestion_type = "backfill"
        timestamp_ms = 1678886400000

        # Act
        manager.update_last_processed_timestamp(symbol, ingestion_type, timestamp_ms)

        # Assert
        self.mock_write_api_instance.write.assert_called_once()
        args, kwargs = self.mock_write_api_instance.write.call_args
        written_record = kwargs['record']

        # Assuming it's a single Point object for simplicity in this test
        self.assertIsInstance(written_record, Point)
        self.assertEqual(written_record._name, "ingestor_processing_state")
        self.assertIn(("symbol", symbol), written_record._tags.items())
        self.assertIn(("ingestion_type", ingestion_type), written_record._tags.items())
        self.assertIn(("last_processed_timestamp_ms", timestamp_ms), written_record._fields.items())


    def test_update_last_processed_timestamp_influxdb_error(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        
        # Create a mock response object for InfluxDBError
        mock_response = mock.MagicMock()
        mock_response.data = "Simulated DB Write Error"
        mock_response.status = 500
        
        self.mock_write_api_instance.write.side_effect = InfluxDBError(response=mock_response)

        # Act
        # This should not raise an exception out of the method due to try-except
        manager.update_last_processed_timestamp("ethusd", "polling", 1678886400000)

        # Assert
        self.mock_write_api_instance.write.assert_called_once() # Still called


if __name__ == "__main__":
    unittest.main()
