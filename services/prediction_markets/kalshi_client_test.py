"""Tests for the Kalshi API client."""

from unittest import mock
from absl.testing import absltest
import requests

from services.prediction_markets.kalshi_client import KalshiClient


class KalshiClientTest(absltest.TestCase):
    def setUp(self):
        self.client = KalshiClient(
            base_url="https://api.elections.kalshi.com/trade-api/v2",
            request_timeout=5,
            cache_ttl_seconds=60,
            relevant_series=["FED", "BTCETF"],
        )
        self.mock_response = mock.MagicMock()
        self.mock_response.raise_for_status = mock.MagicMock()

    def tearDown(self):
        self.client.close()

    @mock.patch("requests.Session.get")
    def test_get_markets(self, mock_get):
        expected = {
            "markets": [
                {"ticker": "FED-26MAR-T3.50", "yes_price": 0.72},
                {"ticker": "FED-26MAR-T4.00", "yes_price": 0.35},
            ]
        }
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_markets(series_ticker="FED")

        self.assertEqual(result, expected)
        call_args = mock_get.call_args
        self.assertIn("/markets", call_args[0][0])
        self.assertEqual(call_args[1]["params"]["series_ticker"], "FED")

    @mock.patch("requests.Session.get")
    def test_get_market_orderbook(self, mock_get):
        expected = {
            "orderbook": {
                "yes": [["0.72", "100"], ["0.71", "200"]],
                "no": [["0.28", "150"]],
            }
        }
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_market_orderbook("FED-26MAR-T3.50")

        self.assertEqual(result, expected)
        self.assertIn("FED-26MAR-T3.50", mock_get.call_args[0][0])

    @mock.patch("requests.Session.get")
    def test_get_event(self, mock_get):
        expected = {"event_ticker": "FED-26MAR", "title": "Fed Rate Decision"}
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_event("FED-26MAR")

        self.assertEqual(result, expected)
        self.assertIn("FED-26MAR", mock_get.call_args[0][0])

    @mock.patch("requests.Session.get")
    def test_get_crypto_relevant_markets(self, mock_get):
        fed_markets = {"markets": [{"ticker": "FED-T3.50"}]}
        etf_markets = {"markets": [{"ticker": "BTCETF-APR"}]}
        self.mock_response.json.side_effect = [fed_markets, etf_markets]
        mock_get.return_value = self.mock_response

        result = self.client.get_crypto_relevant_markets()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["ticker"], "FED-T3.50")
        self.assertEqual(result[1]["ticker"], "BTCETF-APR")

    @mock.patch("requests.Session.get")
    def test_get_crypto_relevant_markets_safe_unavailable(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("down")

        result = self.client.get_crypto_relevant_markets_safe()

        self.assertEqual(result["markets"], [])
        # When individual series fetches fail silently, result has no markers
        # but still returns empty markets list

    @mock.patch("requests.Session.get")
    def test_caching_prevents_duplicate_requests(self, mock_get):
        expected = {"markets": [{"ticker": "FED-T3.50"}]}
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result1 = self.client.get_markets(series_ticker="FED")
        result2 = self.client.get_markets(series_ticker="FED")

        self.assertEqual(result1, result2)
        mock_get.assert_called_once()

    @mock.patch("requests.Session.get")
    def test_find_significant_movers(self, mock_get):
        markets = [
            {
                "ticker": "FED-1",
                "title": "Rate Cut",
                "yes_price": 0.72,
                "previous_yes_price": 0.45,
                "volume": 10000,
            },
            {
                "ticker": "FED-2",
                "title": "Rate Hold",
                "yes_price": 0.50,
                "previous_yes_price": 0.48,
                "volume": 5000,
            },
        ]

        movers = self.client.find_significant_movers(markets, min_change=0.10)

        self.assertEqual(len(movers), 1)
        self.assertEqual(movers[0]["ticker"], "FED-1")
        self.assertAlmostEqual(movers[0]["change"], 0.27, places=2)

    @mock.patch("requests.Session.get")
    def test_raises_on_http_error(self, mock_get):
        self.mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500"
        )
        mock_get.return_value = self.mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.get_markets()


if __name__ == "__main__":
    absltest.main()
