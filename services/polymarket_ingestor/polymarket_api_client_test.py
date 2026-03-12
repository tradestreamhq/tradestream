"""Tests for the Polymarket API client."""

from unittest import mock
from absl.testing import absltest
import requests

from services.polymarket_ingestor.polymarket_api_client import PolymarketApiClient


class PolymarketApiClientTest(absltest.TestCase):
    def setUp(self):
        self.client = PolymarketApiClient(
            base_url="https://clob.polymarket.com",
            request_timeout=10,
        )
        self.mock_response = mock.MagicMock()
        self.mock_response.raise_for_status = mock.MagicMock()

    def tearDown(self):
        self.client.close()

    @mock.patch("requests.Session.get")
    def test_get_markets_returns_data(self, mock_get):
        expected = {
            "data": [
                {"condition_id": "abc123", "question": "Will X happen?"},
                {"condition_id": "def456", "question": "Will Y happen?"},
            ],
            "next_cursor": "LTE=",
        }
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_markets()

        self.assertEqual(result, expected)
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn("/markets", call_args[0][0])

    @mock.patch("requests.Session.get")
    def test_get_markets_with_cursor(self, mock_get):
        expected = {"data": [], "next_cursor": "LTE="}
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_markets(next_cursor="abc123")

        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["next_cursor"], "abc123")

    @mock.patch("requests.Session.get")
    def test_get_markets_without_cursor_sends_no_cursor_param(self, mock_get):
        self.mock_response.json.return_value = {"data": [], "next_cursor": "LTE="}
        mock_get.return_value = self.mock_response

        self.client.get_markets()

        call_args = mock_get.call_args
        self.assertNotIn("next_cursor", call_args[1].get("params", {}))

    @mock.patch("requests.Session.get")
    def test_get_market_single(self, mock_get):
        expected = {"condition_id": "abc123", "question": "Test?"}
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_market("abc123")

        self.assertEqual(result, expected)
        self.assertIn("abc123", mock_get.call_args[0][0])

    @mock.patch("requests.Session.get")
    def test_get_order_book(self, mock_get):
        expected = {
            "bids": [{"price": "0.55", "size": "100"}],
            "asks": [{"price": "0.60", "size": "50"}],
        }
        self.mock_response.json.return_value = expected
        mock_get.return_value = self.mock_response

        result = self.client.get_order_book("token123")

        self.assertEqual(result, expected)
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["token_id"], "token123")

    @mock.patch("requests.Session.get")
    def test_get_all_active_markets_pagination(self, mock_get):
        page1 = {
            "data": [{"condition_id": "m1"}],
            "next_cursor": "cursor2",
        }
        page2 = {
            "data": [{"condition_id": "m2"}],
            "next_cursor": "LTE=",
        }
        self.mock_response.json.side_effect = [page1, page2]
        mock_get.return_value = self.mock_response

        result = self.client.get_all_active_markets(max_pages=5)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["condition_id"], "m1")
        self.assertEqual(result[1]["condition_id"], "m2")

    @mock.patch("requests.Session.get")
    def test_get_all_active_markets_empty_page_stops(self, mock_get):
        page1 = {"data": [], "next_cursor": ""}
        self.mock_response.json.return_value = page1
        mock_get.return_value = self.mock_response

        result = self.client.get_all_active_markets()

        self.assertEqual(len(result), 0)

    @mock.patch("requests.Session.get")
    def test_get_all_active_markets_max_pages_limit(self, mock_get):
        """Pagination stops when max_pages is reached even with more data."""
        page = {
            "data": [{"condition_id": "m1"}],
            "next_cursor": "has_more",
        }
        self.mock_response.json.return_value = page
        mock_get.return_value = self.mock_response

        result = self.client.get_all_active_markets(max_pages=2)

        self.assertEqual(len(result), 2)
        self.assertEqual(mock_get.call_count, 2)

    @mock.patch("requests.Session.get")
    def test_get_markets_raises_on_http_error(self, mock_get):
        self.mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404"
        )
        mock_get.return_value = self.mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.get_markets()

    @mock.patch("requests.Session.get")
    def test_get_market_raises_on_http_error(self, mock_get):
        self.mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500"
        )
        mock_get.return_value = self.mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.get_market("abc123")

    @mock.patch("requests.Session.get")
    def test_get_order_book_raises_on_http_error(self, mock_get):
        self.mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "503"
        )
        mock_get.return_value = self.mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.get_order_book("token123")

    @mock.patch("requests.Session.get")
    def test_get_markets_passes_timeout(self, mock_get):
        """Verifies request timeout is forwarded to the HTTP call."""
        self.mock_response.json.return_value = {"data": [], "next_cursor": "LTE="}
        mock_get.return_value = self.mock_response

        self.client.get_markets()

        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["timeout"], 10)

    def test_base_url_trailing_slash_stripped(self):
        client = PolymarketApiClient(base_url="https://example.com/")
        self.assertEqual(client.base_url, "https://example.com")
        client.close()

    @mock.patch("requests.Session.get")
    def test_session_headers_set(self, mock_get):
        """Verifies the session sets Accept: application/json header."""
        self.assertEqual(self.client.session.headers["Accept"], "application/json")

    @mock.patch("requests.Session.get")
    def test_get_all_active_markets_no_next_cursor_key(self, mock_get):
        """Handles response missing 'next_cursor' key gracefully."""
        page = {"data": [{"condition_id": "m1"}]}
        self.mock_response.json.return_value = page
        mock_get.return_value = self.mock_response

        result = self.client.get_all_active_markets(max_pages=2)

        # next_cursor defaults to "" which is falsy but not "LTE=",
        # so it should continue to next page (empty string cursor)
        self.assertGreaterEqual(len(result), 1)

    @mock.patch("requests.Session.get")
    def test_get_all_active_markets_accumulates_from_multiple_pages(self, mock_get):
        """Ensures markets from all pages are combined into a single list."""
        page1 = {
            "data": [{"condition_id": f"m{i}"} for i in range(3)],
            "next_cursor": "c2",
        }
        page2 = {
            "data": [{"condition_id": f"m{i}"} for i in range(3, 5)],
            "next_cursor": "LTE=",
        }
        self.mock_response.json.side_effect = [page1, page2]
        mock_get.return_value = self.mock_response

        result = self.client.get_all_active_markets(max_pages=10)

        self.assertEqual(len(result), 5)


if __name__ == "__main__":
    absltest.main()
