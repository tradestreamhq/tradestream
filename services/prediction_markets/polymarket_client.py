"""Client for the Polymarket Insider Tracker API.

Fetches insider activity alerts and watched markets from the
polymarket-insider-tracker service. Operates gracefully when
the tracker is unavailable.
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

api_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
    ),
    reraise=True,
)


class PolymarketInsiderClient:
    """Client for fetching insider alerts from polymarket-insider-tracker."""

    def __init__(self, base_url: str, request_timeout: float = 5.0,
                 cache_ttl_seconds: int = 60,
                 stale_cache_max_age_seconds: int = 300):
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.cache_ttl_seconds = cache_ttl_seconds
        self.stale_cache_max_age_seconds = stale_cache_max_age_seconds
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
    def get_recent_alerts(self, min_confidence: str = "HIGH",
                          limit: int = 5) -> dict:
        """Fetch recent insider alerts.

        Args:
            min_confidence: Minimum confidence level (LOW, MEDIUM, HIGH, CRITICAL).
            limit: Maximum alerts to return.

        Returns:
            Dict with alert data or cached fallback.
        """
        cache_key = f"alerts_{min_confidence}_{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        response = self.session.get(
            f"{self.base_url}/api/alerts/recent",
            params={"min_confidence": min_confidence, "limit": limit},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._set_cache(cache_key, data)
        return data

    @retry(**api_retry_params)
    def get_watchlist_markets(self) -> dict:
        """Fetch markets with active insider signals.

        Returns:
            Dict with market watchlist data.
        """
        cache_key = "watchlist_markets"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        response = self.session.get(
            f"{self.base_url}/api/markets/watchlist",
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._set_cache(cache_key, data)
        return data

    @retry(**api_retry_params)
    def get_watchlist_wallets(self) -> dict:
        """Fetch watched wallet addresses.

        Returns:
            Dict with wallet watchlist data.
        """
        cache_key = "watchlist_wallets"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        response = self.session.get(
            f"{self.base_url}/api/wallets/watchlist",
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._set_cache(cache_key, data)
        return data

    def get_recent_alerts_safe(self, min_confidence: str = "HIGH",
                               limit: int = 5) -> dict:
        """Fetch alerts with graceful degradation.

        Returns cached data on failure, or empty result if no cache.
        """
        try:
            return self.get_recent_alerts(min_confidence, limit)
        except Exception as e:
            logging.warning(f"Polymarket insider API unavailable: {e}")
            cache_key = f"alerts_{min_confidence}_{limit}"
            stale = self._get_cached(cache_key, allow_stale=True)
            if stale is not None:
                return {"data": stale.get("data", []), "stale": True}
            return {"data": [], "unavailable": True}

    def get_watchlist_markets_safe(self) -> dict:
        """Fetch watchlist markets with graceful degradation."""
        try:
            return self.get_watchlist_markets()
        except Exception as e:
            logging.warning(f"Polymarket watchlist API unavailable: {e}")
            stale = self._get_cached("watchlist_markets", allow_stale=True)
            if stale is not None:
                return {"data": stale.get("data", []), "stale": True}
            return {"data": [], "unavailable": True}

    def close(self):
        """Close the HTTP session."""
        self.session.close()
