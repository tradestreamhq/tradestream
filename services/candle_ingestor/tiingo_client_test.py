import unittest
from unittest import mock
from datetime import datetime, timezone


import requests

from services.candle_ingestor import tiingo_client


class TestTiingoClient(unittest.TestCase):
    @mock.patch("services.candle_ingestor.tiingo_client.requests.get")
    def test_get_historical_candles_success(self, mock_get):
        # Arrange
        mock_api_key = "test_tiingo_key"
        mock_ticker = "btcusd"
        mock_start_date = "2023-01-01"
        mock_end_date = "2023-01-02"
        mock_resample_freq = "1day"

        mock_response_data = [
            {
                "ticker": "btcusd",
                "priceData": [
                    {
                        "date": "2023-01-01T00:00:00.000Z",
                        "open": 100.0,
                        "high": 110.0,
                        "low": 90.0,
                        "close": 105.0,
                        "volume": 1000.0,
                    },
                    {
                        "date": "2023-01-02T00:00:00Z", # Test with Z suffix
                        "open": 105.0,
                        "high": 115.0,
                        "low": 95.0,
                        "close": 110.0,
                        "volume": 1200.0,
                    },
                ],
            }
        ]
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        # Act
        candles = tiingo_client.get_historical_candles_tiingo(
            mock_api_key,
            mock_ticker,
            mock_start_date,
            mock_end_date,
            mock_resample_freq,
        )

        # Assert
        expected_params = {
            "tickers": mock_ticker,
            "startDate": mock_start_date,
            "endDate": mock_end_date,
            "resampleFreq": mock_resample_freq,
            "token": mock_api_key,
            "format": "json",
        }
        mock_get.assert_called_once_with(
            "https://api.tiingo.com/tiingo/crypto/prices",
            params=expected_params,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0]["open"], 100.0)
        self.assertEqual(candles[1]["close"], 110.0)
        self.assertEqual(
            candles[0]["timestamp_ms"],
            datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp() * 1000,
        )
        self.assertEqual(
            candles[1]["timestamp_ms"],
            datetime(2023, 1, 2, tzinfo=timezone.utc).timestamp() * 1000,
        )
        self.assertEqual(candles[0]["currency_pair"], "btcusd")


    @mock.patch("services.candle_ingestor.tiingo_client.requests.get")
    def test_get_historical_candles_empty_response(self, mock_get):
        # Arrange
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []  # Empty list from API
        mock_get.return_value = mock_response

        # Act
        candles = tiingo_client.get_historical_candles_tiingo(
            "k", "t", "sd", "ed", "rf"
        )

        # Assert
        self.assertEqual(candles, [])

    @mock.patch("services.candle_ingestor.tiingo_client.requests.get")
    def test_get_historical_candles_http_error(self, mock_get):
        # Arrange
        mock_response = mock.MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = (
            requests.exceptions.HTTPError(
                "Server Error", response=mock_response
            )
        )
        mock_get.return_value = mock_response

        # Act
        candles = tiingo_client.get_historical_candles_tiingo(
            "k", "t", "sd", "ed", "rf"
        )

        # Assert
        self.assertEqual(candles, [])

    @mock.patch("services.candle_ingestor.tiingo_client.requests.get")
    def test_get_historical_candles_malformed_candle_item(self, mock_get):
         # Arrange
        mock_api_key = "test_tiingo_key"
        mock_ticker = "btcusd"
        mock_start_date = "2023-01-01"
        mock_end_date = "2023-01-01"
        mock_resample_freq = "1day"

        mock_response_data = [
            {
                "ticker": "btcusd",
                "priceData": [
                    { # Malformed - missing 'open'
                        "date": "2023-01-01T00:00:00.000Z",
                        "high": 110.0,
                        "low": 90.0,
                        "close": 105.0,
                        "volume": 1000.0,
                    },
                     { # Good candle
                        "date": "2023-01-02T00:00:00.000Z",
                        "open": 105.0,
                        "high": 115.0,
                        "low": 95.0,
                        "close": 110.0,
                        "volume": 1200.0,
                    },
                ],
            }
        ]
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        # Act
        candles = tiingo_client.get_historical_candles_tiingo(
            mock_api_key, mock_ticker, mock_start_date, mock_end_date, mock_resample_freq
        )
        # Assert
        self.assertEqual(len(candles), 1) # Only the good candle should be parsed
        self.assertEqual(candles[0]["open"], 105.0)


if __name__ == "__main__":
    unittest.main()
