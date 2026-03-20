"""Client for the Kalshi prediction market API.

Fetches market data, event details, and order books from Kalshi's
public trade API. Supports configurable caching and graceful degradation.
"""

import time
from absl import logging
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

KALSHI_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

# Kalshi rate limit: 10 req/sec — retry conservatively
api_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
    ),
    reraise=True,
)

# Event categories relevant to crypto markets
CRYPTO_RELEVANT_SERIES = ["FED", "SEC", "CFTC", "BTCETF", "ETHETF"]


class KalshiClient:
    """Client for the Kalshi prediction market REST API."""

    def __init__(
        self,
        base_url: str = KALSHI_BASE_URL,
        request_timeout: float = 5.0,
        cache_ttl_seconds: int = 60,
        stale_cache_max_age_seconds: int = 300,
        relevant_series: list = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.cache_ttl_seconds = cache_ttl_seconds
        self.stale_cache_max_age_seconds = stale_cache_max_age_seconds
        self.relevant_series = relevant_series or CRYPTO_RELEVANT_SERIES
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        # In-memory cache
        self._cache = {}
        self._cache_timestamps = {}

    def _get_cached(self, key: str, allow_stale: bool = False):
        """Return cached data if within TTL, or stale data if allowed."""
        if key not in self._cache:
            return None
        age = time.time() - self._cache_timestamps[key]
        if age <= self.cache_ttl_seconds:
            return self._cache[key]
        if allow_stale and age <= self.stale_cache_max_age_seconds:
            logging.warning(f"Using stale cache for {key} (age: {age:.0f}s)")
            return self._cache[key]
        return None

    def _set_cache(self, key: str, data):
        """Store data in cache with current timestamp."""
        self._cache[key] = data
        self._cache_timestamps[key] = time.time()

    @retry(**api_retry_params)
    def get_markets(
        self, series_ticker: str = "", status: str = "open", limit: int = 50
    ) -> dict:
        """Fetch active markets, optionally filtered by series.

        Args:
            series_ticker: Filter by event series (e.g. "FED").
            status: Market status filter.
            limit: Max markets to return.

        Returns:
            Dict with 'markets' list.
        """
        cache_key = f"markets_{series_ticker}_{status}_{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        params = {"status": status, "limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker

        response = self.session.get(
            f"{self.base_url}/markets",
            params=params,
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._set_cache(cache_key, data)
        return data

    @retry(**api_retry_params)
    def get_market_orderbook(self, ticker: str) -> dict:
        """Fetch order book for a specific market.

        Args:
            ticker: Market ticker (e.g. "FED-26MAR-T3.50").

        Returns:
            Dict with 'orderbook' containing bids/asks.
        """
        cache_key = f"orderbook_{ticker}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        response = self.session.get(
            f"{self.base_url}/markets/{ticker}/orderbook",
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._set_cache(cache_key, data)
        return data

    @retry(**api_retry_params)
    def get_event(self, event_ticker: str) -> dict:
        """Fetch event details.

        Args:
            event_ticker: Event ticker to look up.

        Returns:
            Dict with event details including markets.
        """
        cache_key = f"event_{event_ticker}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        response = self.session.get(
            f"{self.base_url}/events/{event_ticker}",
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._set_cache(cache_key, data)
        return data

    def get_crypto_relevant_markets(self) -> list:
        """Fetch all markets from crypto-relevant series.

        Returns:
            List of market dicts across all relevant series.
        """
        all_markets = []
        for series in self.relevant_series:
            try:
                result = self.get_markets(series_ticker=series)
                markets = result.get("markets", [])
                all_markets.extend(markets)
            except Exception as e:
                logging.warning(f"Failed to fetch Kalshi markets for {series}: {e}")
        return all_markets

    def get_crypto_relevant_markets_safe(self) -> dict:
        """Fetch crypto-relevant markets with graceful degradation."""
        try:
            markets = self.get_crypto_relevant_markets()
            return {"markets": markets, "available": True}
        except Exception as e:
            logging.warning(f"Kalshi API unavailable: {e}")
            # Try stale cache for each series
            all_stale = []
            for series in self.relevant_series:
                cache_key = f"markets_{series}_open_50"
                stale = self._get_cached(cache_key, allow_stale=True)
                if stale:
                    all_stale.extend(stale.get("markets", []))
            if all_stale:
                return {"markets": all_stale, "stale": True}
            return {"markets": [], "unavailable": True}

    def find_significant_movers(self, markets: list, min_change: float = 0.10) -> list:
        """Identify markets with significant price movements.

        Args:
            markets: List of market dicts from get_markets.
            min_change: Minimum absolute probability change to flag.

        Returns:
            List of markets with significant price movement.
        """
        movers = []
        for market in markets:
            yes_price = market.get("yes_price", 0) or market.get("last_price", 0)
            prev_price = market.get("previous_yes_price", 0) or market.get(
                "prev_price", 0
            )
            if prev_price > 0 and yes_price > 0:
                change = abs(yes_price - prev_price)
                if change >= min_change:
                    movers.append(
                        {
                            "ticker": market.get("ticker", ""),
                            "title": market.get("title", market.get("subtitle", "")),
                            "yes_price": yes_price,
                            "previous_price": prev_price,
                            "change": change,
                            "volume": market.get("volume", 0),
                        }
                    )
        return sorted(movers, key=lambda m: m["change"], reverse=True)

    def close(self):
        """Close the HTTP session."""
        self.session.close()
