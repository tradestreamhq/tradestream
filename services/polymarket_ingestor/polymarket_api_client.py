"""Client for the Polymarket CLOB API."""

from absl import logging
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

API_BASE_URL = "https://clob.polymarket.com"

api_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type(
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
    ),
    reraise=True,
)


class PolymarketApiClient:
    """Client for fetching data from the Polymarket CLOB API."""

    def __init__(self, base_url: str = API_BASE_URL, request_timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    @retry(**api_retry_params)
    def get_markets(self, next_cursor: str = "") -> dict:
        """Fetch active markets from Polymarket.

        Args:
            next_cursor: Pagination cursor for fetching next page.

        Returns:
            Dict with 'data' (list of markets) and 'next_cursor'.
        """
        params = {}
        if next_cursor:
            params["next_cursor"] = next_cursor
        response = self.session.get(
            f"{self.base_url}/markets",
            params=params,
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    @retry(**api_retry_params)
    def get_market(self, condition_id: str) -> dict:
        """Fetch a single market by condition ID.

        Args:
            condition_id: The market condition ID.

        Returns:
            Market data dict.
        """
        response = self.session.get(
            f"{self.base_url}/markets/{condition_id}",
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    @retry(**api_retry_params)
    def get_order_book(self, token_id: str) -> dict:
        """Fetch the order book for a token.

        Args:
            token_id: The token ID to fetch the order book for.

        Returns:
            Order book data with bids and asks.
        """
        response = self.session.get(
            f"{self.base_url}/book",
            params={"token_id": token_id},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_all_active_markets(self, max_pages: int = 10) -> list:
        """Fetch all active markets with pagination.

        Args:
            max_pages: Maximum number of pages to fetch.

        Returns:
            List of all market dicts.
        """
        all_markets = []
        next_cursor = ""
        for page in range(max_pages):
            result = self.get_markets(next_cursor=next_cursor)
            markets = result.get("data", [])
            if not markets:
                break
            all_markets.extend(markets)
            next_cursor = result.get("next_cursor", "")
            if next_cursor == "LTE=":
                break
            logging.info(
                f"Fetched page {page + 1}: {len(markets)} markets "
                f"(total: {len(all_markets)})"
            )
        return all_markets

    def close(self):
        """Close the HTTP session."""
        self.session.close()
