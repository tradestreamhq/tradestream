"""
Async CoinMarketCap API client for the MCP server.

Wraps the CoinMarketCap Pro API with caching-friendly response formatting.
"""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

CMC_BASE_URL = "https://pro-api.coinmarketcap.com"


class CoinMarketCapClient:
    """Async HTTP client for CoinMarketCap Pro API."""

    def __init__(self, api_key: str, timeout: float = 15.0):
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=CMC_BASE_URL,
            timeout=timeout,
            headers={
                "Accepts": "application/json",
                "X-CMC_PRO_API_KEY": api_key,
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_listings(
        self, limit: int = 100, convert: str = "USD"
    ) -> list[dict[str, Any]]:
        """Get latest cryptocurrency listings sorted by market cap."""
        resp = await self._client.get(
            "/v1/cryptocurrency/listings/latest",
            params={"start": "1", "limit": str(limit), "convert": convert},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    async def get_quotes(
        self, symbols: list[str], convert: str = "USD"
    ) -> dict[str, Any]:
        """Get latest quotes for specific symbols."""
        resp = await self._client.get(
            "/v2/cryptocurrency/quotes/latest",
            params={"symbol": ",".join(symbols), "convert": convert},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def get_global_metrics(self, convert: str = "USD") -> dict[str, Any]:
        """Get global cryptocurrency market metrics."""
        resp = await self._client.get(
            "/v1/global-metrics/quotes/latest",
            params={"convert": convert},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def get_exchange_rates(
        self, symbol: str = "BTC", convert: str = "USD"
    ) -> dict[str, Any]:
        """Get exchange rate for a cryptocurrency."""
        resp = await self._client.get(
            "/v2/cryptocurrency/quotes/latest",
            params={"symbol": symbol, "convert": convert},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        # CMC v2 returns {symbol: [list of matches]}
        entries = data.get(symbol.upper(), [])
        if entries:
            return entries[0]
        return {}
