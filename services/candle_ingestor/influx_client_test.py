import unittest
from unittest import mock

# Your module to test
from services.candle_ingestor import influx_client


# Mock the InfluxDBClient itself and its methods
@mock.patch("services.candle_ingestor.influx_client.InfluxDBClient")
class TestInfluxDBManager(unittest.TestCase):
    def setUp(self):
        self.test_url = "http://fake-influx:8086"
        self.test_token = "fake-token"
        self.test_org = "fake-org"
        self.test_bucket = "fake-bucket"

    def test_connect_success(self, MockInfluxDBClient):
        # Arrange
        mock_client_instance = MockInfluxDBClient.return_value
        mock_client_instance.ping.return_value = True

        # Act
        manager = influx_client.InfluxDBManager(
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
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        self.assertIsNone(manager.get_client())  # Client should be set to None

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
        mock_client_instance = MockInfluxDBClient.return_value
        mock_client_instance.ping.side_effect = Exception("Ping network error")

        # Act
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Assert
        self.assertIsNone(manager.get_client())

    def test_get_write_api_success(self, MockInfluxDBClient):
        # Arrange
        mock_client_instance = MockInfluxDBClient.return_value
        mock_client_instance.ping.return_value = True
        mock_write_api = mock.MagicMock()
        mock_client_instance.write_api.return_value = mock_write_api

        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        write_api = manager.get_write_api()

        # Assert
        self.assertEqual(write_api, mock_write_api)
        mock_client_instance.write_api.assert_called_once()

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
        mock_client_instance = MockInfluxDBClient.return_value
        mock_client_instance.ping.return_value = True
        mock_query_api = mock.MagicMock()
        mock_client_instance.query_api.return_value = mock_query_api

        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        query_api = manager.get_query_api()

        # Assert
        self.assertEqual(query_api, mock_query_api)
        mock_client_instance.query_api.assert_called_once()

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
        mock_client_instance = MockInfluxDBClient.return_value
        mock_client_instance.ping.return_value = True
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )
        self.assertIsNotNone(manager.get_client())  # Ensure client was set

        # Act
        manager.close()

        # Assert
        mock_client_instance.close.assert_called_once()

    def test_close_client_not_initialized(self, MockInfluxDBClient):
        # Arrange
        mock_client_instance = MockInfluxDBClient.return_value
        mock_client_instance.ping.return_value = False  # Ensure client is None
        manager = influx_client.InfluxDBManager(
            self.test_url, self.test_token, self.test_org, self.test_bucket
        )

        # Act
        manager.close()  # Should not throw error

        # Assert
        mock_client_instance.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
