"""Tests for the Polymarket Insider Tracker client."""

import time
from unittest import mock
from absl.testing import absltest
import requests

from services.prediction_markets.polymarket_client import PolymarketInsiderClient


class PolymarketInsiderClientTest(absltest.TestCase):
    def setUp(self):
        self.client = PolymarketInsiderClient(
            base_url="http://localhost:8080",
            request_timeout=5,
            cache_ttl_seconds=60,
            stale_cache_max_age_seconds=300,
        )
        self.mock_response = mock.MagicMock()
        self.mock_response.raise_for_status = mock.MagicMock()

    def tearDown(self):
        self.client.close()

    @mock.patch("requests.Session.get")
    def test_get_recent_alerts_returns_data(self, mock_get):
        expected = {
            "data": [
                {
                    "wallet_address": "0x7a3f91",
                    "market_id": "market1",
                    "confidence": "HIGH",
                    "position_size": 15000,
                },
            ]
        }
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_recent_alerts(min_confidence="HIGH", limit=5)

        self.assertEqual(result, expected)
        call_args = mock_get.call_args
        self.assertIn("/api/alerts/recent", call_args[0][0])
        self.assertEqual(call_args[1]["params"]["min_confidence"], "HIGH")

    @mock.patch("requests.Session.get")
    def test_get_watchlist_markets(self, mock_get):
        expected = {"data": [{"market_id": "m1", "alert_count": 3}]}
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_watchlist_markets()

        self.assertEqual(result, expected)
        self.assertIn("/api/markets/watchlist", mock_get.call_args[0][0])

    @mock.patch("requests.Session.get")
    def test_get_watchlist_wallets(self, mock_get):
        expected = {"data": [{"wallet_address": "0xabc"}]}
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_watchlist_wallets()

        self.assertEqual(result, expected)
        self.assertIn("/api/wallets/watchlist", mock_get.call_args[0][0])

    @mock.patch("requests.Session.get")
    def test_caching_prevents_duplicate_requests(self, mock_get):
        expected = {"data": [{"alert_id": "1"}]}
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result1 = self.client.get_recent_alerts()
        result2 = self.client.get_recent_alerts()

        self.assertEqual(result1, result2)
        # Should only make one actual request due to caching
        mock_get.assert_called_once()

    @mock.patch("requests.Session.get")
    def test_get_recent_alerts_safe_returns_empty_on_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("down")

        result = self.client.get_recent_alerts_safe()

        self.assertEqual(result["data"], [])
        self.assertTrue(result.get("unavailable"))

    @mock.patch("requests.Session.get")
    def test_get_recent_alerts_safe_returns_stale_cache(self, mock_get):
        # First call succeeds
        expected = {"data": [{"alert_id": "1"}]}
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        self.client.get_recent_alerts()

        # Expire fresh cache but keep within stale window
        cache_key = "alerts_HIGH_5"
        self.client._cache_timestamps[cache_key] = time.time() - 120  # 2 min old

        # Second call fails
        mock_get.side_effect = requests.exceptions.ConnectionError("down")

        result = self.client.get_recent_alerts_safe()

        self.assertTrue(result.get("stale") or len(result.get("data", [])) > 0)

    @mock.patch("requests.Session.get")
    def test_get_watchlist_markets_safe_returns_empty_on_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("down")

        result = self.client.get_watchlist_markets_safe()

        self.assertEqual(result["data"], [])
        self.assertTrue(result.get("unavailable"))

    @mock.patch("requests.Session.get")
    def test_raises_on_http_error(self, mock_get):
        self.mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404"
        )
        mock_get.return_value = self.mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.get_recent_alerts()


if __name__ == "__main__":
    absltest.main()
