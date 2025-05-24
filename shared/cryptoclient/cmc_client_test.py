import unittest
from unittest import mock

import requests

from shared.cryptoclient import cmc_client


class TestCMCClient(unittest.TestCase):
    @mock.patch("services.candle_ingestor.cmc_client.requests.get")
    def test_get_top_n_crypto_symbols_success(self, mock_get):
        # Arrange
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"symbol": "BTC", "name": "Bitcoin"},
                {"symbol": "ETH", "name": "Ethereum"},
                {"symbol": "ADA", "name": "Cardano"},
            ]
        }
        mock_get.return_value = mock_response
        api_key = "test_cmc_key"
        top_n = 2

        # Act
        symbols = cmc_client.get_top_n_crypto_symbols(api_key, top_n)

        # Assert
        mock_get.assert_called_once_with(
            "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest",
            params={"start": "1", "limit": str(top_n), "convert": "USD"},
            headers={"Accepts": "application/json", "X-CMC_PRO_API_KEY": api_key},
            timeout=10,
        )
        self.assertEqual(symbols, ["btcusd", "ethusd"])

    @mock.patch("services.candle_ingestor.cmc_client.requests.get")
    def test_get_top_n_crypto_symbols_api_error(self, mock_get):
        # Arrange
        mock_response = mock.MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Server Error"
        )
        mock_get.return_value = mock_response
        api_key = "test_cmc_key"
        top_n = 5

        # Act
        symbols = cmc_client.get_top_n_crypto_symbols(api_key, top_n)

        # Assert
        self.assertEqual(symbols, [])

    @mock.patch("services.candle_ingestor.cmc_client.requests.get")
    def test_get_top_n_crypto_symbols_json_decode_error(self, mock_get):
        # Arrange
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Decoding JSON has failed")
        mock_get.return_value = mock_response
        api_key = "test_cmc_key"
        top_n = 5

        # Act
        symbols = cmc_client.get_top_n_crypto_symbols(api_key, top_n)

        # Assert
        self.assertEqual(symbols, [])

    @mock.patch("services.candle_ingestor.cmc_client.requests.get")
    def test_get_top_n_crypto_symbols_missing_data_field(self, mock_get):
        # Arrange
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}  # Missing 'data'
        mock_get.return_value = mock_response
        api_key = "test_cmc_key"
        top_n = 3

        # Act
        symbols = cmc_client.get_top_n_crypto_symbols(api_key, top_n)

        # Assert
        self.assertEqual(symbols, [])

    @mock.patch("services.candle_ingestor.cmc_client.requests.get")
    def test_get_top_n_crypto_symbols_empty_data_list(self, mock_get):
        # Arrange
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response
        api_key = "test_cmc_key"
        top_n = 3

        # Act
        symbols = cmc_client.get_top_n_crypto_symbols(api_key, top_n)

        # Assert
        self.assertEqual(symbols, [])

    @mock.patch("services.candle_ingestor.cmc_client.requests.get")
    def test_get_top_n_crypto_symbols_less_than_n_results(self, mock_get):
        # Arrange
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"symbol": "BTC", "name": "Bitcoin"}]
        }
        mock_get.return_value = mock_response
        api_key = "test_cmc_key"
        top_n = 3  # Request 3, but only 1 available

        # Act
        symbols = cmc_client.get_top_n_crypto_symbols(api_key, top_n)

        # Assert
        self.assertEqual(symbols, ["btcusd"])


if __name__ == "__main__":
    unittest.main()
