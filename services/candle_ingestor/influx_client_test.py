import unittest
from unittest import mock

# Your module to test
from services.candle_ingestor import influx_client
from influxdb_client import (
    InfluxDBClient,
    Point,
    WritePrecision,
)  # Added Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError


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
        MockInfluxDBClient.return_value = (
            self.mock_client_instance
        )  # Ensure our mock is used
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
        MockInfluxDBClient.return_value.ping.return_value = (
            False  # Ensure client is None
        )
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
        MockInfluxDBClient.return_value.ping.return_value = (
            False  # Ensure client is None
        )
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
        MockInfluxDBClient.return_value.ping.return_value = False  # Client is None
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        manager.close()  # Should not throw error

        # Assert
        self.mock_client_instance.close.assert_not_called()  # close on the *instance*

    def test_write_candles_batch_success(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        test_candles = [
            {
                "currency_pair": "btcusd",
                "timestamp_ms": 1678886400000,
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000.0,
            }
        ]

        # Act
        result = manager.write_candles_batch(test_candles)

        # Assert
        self.assertEqual(result, 1)  # Should return number of points written
        self.mock_write_api_instance.write.assert_called_once()

    def test_write_candles_batch_empty_data(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        result = manager.write_candles_batch([])

        # Assert
        self.assertEqual(result, 0)
        self.mock_write_api_instance.write.assert_not_called()

    def test_write_candles_batch_client_not_initialized(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value.ping.return_value = False  # Client is None
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        test_candles = [
            {
                "currency_pair": "btcusd",
                "timestamp_ms": 1678886400000,
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,  
                "volume": 1000.0,
            }
        ]

        # Act
        result = manager.write_candles_batch(test_candles)

        # Assert
        self.assertEqual(result, 0)

    def test_write_candles_batch_malformed_data(self, MockInfluxDBClient):
        # Arrange
        MockInfluxDBClient.return_value = self.mock_client_instance
        self.mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        test_candles = [
            {  # Missing 'open' field
                "currency_pair": "btcusd",
                "timestamp_ms": 1678886400000,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000.0,
            },
            {  # Valid candle
                "currency_pair": "ethusd",
                "timestamp_ms": 1678886460000,
                "open": 200.0,
                "high": 210.0,
                "low": 190.0,
                "close": 205.0,
                "volume": 2000.0,
            },
        ]

        # Act
        result = manager.write_candles_batch(test_candles)

        # Assert
        self.assertEqual(result, 1)  # Only the valid candle should be written
        self.mock_write_api_instance.write.assert_called_once()

    def test_write_candles_batch_influxdb_error(self, MockInfluxDBClient):
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

        self.mock_write_api_instance.write.side_effect = InfluxDBError(
            response=mock_response
        )

        test_candles = [
            {
                "currency_pair": "btcusd",
                "timestamp_ms": 1678886400000,
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 105.0,
                "volume": 1000.0,
            }
        ]

        # Act
        result = manager.write_candles_batch(test_candles)

        # Assert
        self.assertEqual(result, 0)  # Should return 0 on error
        # Should retry 5 times due to tenacity
        self.assertEqual(self.mock_write_api_instance.write.call_count, 5)


if __name__ == "__main__":
    unittest.main()
