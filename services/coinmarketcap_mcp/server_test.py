"""Tests for the CoinMarketCap MCP server."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from services.coinmarketcap_mcp.cmc_client import CoinMarketCapClient
from services.coinmarketcap_mcp.server import (
    server,
    _set_cmc_client,
    _cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


@pytest.fixture
def mock_cmc():
    """Create a mock CMC client and set it on the server."""
    client = AsyncMock(spec=CoinMarketCapClient)
    _set_cmc_client(client)
    return client


class TestListTools:
    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        tools = await server._list_tools_handler()
        names = {t.name for t in tools}
        assert names == {
            "get_price",
            "get_market_cap",
            "get_volume",
            "get_trending",
            "get_exchange_rates",
        }


class TestGetPrice:
    @pytest.mark.asyncio
    async def test_get_price_success(self, mock_cmc):
        mock_cmc.get_quotes.return_value = {
            "BTC": [
                {
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "quote": {
                        "USD": {
                            "price": 65000.0,
                            "percent_change_1h": 0.5,
                            "percent_change_24h": 2.1,
                        }
                    },
                }
            ]
        }
        handler = server._call_tool_handler
        result = await handler("get_price", {"symbols": ["BTC"]})
        data = json.loads(result[0].text)
        assert "data" in data
        assert data["data"][0]["symbol"] == "BTC"
        assert data["data"][0]["price"] == 65000.0

    @pytest.mark.asyncio
    async def test_get_price_cached(self, mock_cmc):
        mock_cmc.get_quotes.return_value = {
            "ETH": [
                {
                    "name": "Ethereum",
                    "symbol": "ETH",
                    "quote": {"USD": {"price": 3500.0, "percent_change_1h": 0.1, "percent_change_24h": 1.0}},
                }
            ]
        }
        handler = server._call_tool_handler
        # First call populates cache
        await handler("get_price", {"symbols": ["ETH"]})
        # Second call should use cache
        result = await handler("get_price", {"symbols": ["ETH"]})
        data = json.loads(result[0].text)
        assert data["_metadata"]["cached"] is True
        # Only one API call should have been made
        assert mock_cmc.get_quotes.call_count == 1

    @pytest.mark.asyncio
    async def test_get_price_force_refresh(self, mock_cmc):
        mock_cmc.get_quotes.return_value = {
            "BTC": [
                {
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "quote": {"USD": {"price": 65000.0, "percent_change_1h": 0.5, "percent_change_24h": 2.1}},
                }
            ]
        }
        handler = server._call_tool_handler
        await handler("get_price", {"symbols": ["BTC"]})
        await handler("get_price", {"symbols": ["BTC"], "force_refresh": True})
        assert mock_cmc.get_quotes.call_count == 2


class TestGetMarketCap:
    @pytest.mark.asyncio
    async def test_get_market_cap_success(self, mock_cmc):
        mock_cmc.get_quotes.return_value = {
            "BTC": [
                {
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "quote": {
                        "USD": {
                            "market_cap": 1_300_000_000_000,
                            "market_cap_dominance": 52.0,
                            "fully_diluted_market_cap": 1_365_000_000_000,
                        }
                    },
                }
            ]
        }
        handler = server._call_tool_handler
        result = await handler("get_market_cap", {"symbols": ["BTC"]})
        data = json.loads(result[0].text)
        assert data["data"][0]["market_cap"] == 1_300_000_000_000


class TestGetVolume:
    @pytest.mark.asyncio
    async def test_get_volume_success(self, mock_cmc):
        mock_cmc.get_quotes.return_value = {
            "BTC": [
                {
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "quote": {
                        "USD": {
                            "volume_24h": 45_000_000_000,
                            "volume_change_24h": 5.2,
                        }
                    },
                }
            ]
        }
        handler = server._call_tool_handler
        result = await handler("get_volume", {"symbols": ["BTC"]})
        data = json.loads(result[0].text)
        assert data["data"][0]["volume_24h"] == 45_000_000_000


class TestGetTrending:
    @pytest.mark.asyncio
    async def test_get_trending_success(self, mock_cmc):
        mock_cmc.get_listings.return_value = [
            {
                "cmc_rank": 1,
                "name": "Bitcoin",
                "symbol": "BTC",
                "quote": {
                    "USD": {
                        "price": 65000.0,
                        "percent_change_24h": 2.1,
                        "market_cap": 1_300_000_000_000,
                        "volume_24h": 45_000_000_000,
                    }
                },
            }
        ]
        handler = server._call_tool_handler
        result = await handler("get_trending", {"limit": 1})
        data = json.loads(result[0].text)
        assert len(data["data"]) == 1
        assert data["data"][0]["rank"] == 1


class TestGetExchangeRates:
    @pytest.mark.asyncio
    async def test_get_exchange_rates_success(self, mock_cmc):
        mock_cmc.get_exchange_rates.return_value = {
            "name": "Bitcoin",
            "symbol": "BTC",
            "quote": {
                "USD": {
                    "price": 65000.0,
                    "last_updated": "2026-03-20T10:00:00Z",
                }
            },
        }
        handler = server._call_tool_handler
        result = await handler("get_exchange_rates", {"symbol": "BTC"})
        data = json.loads(result[0].text)
        assert data["data"]["price"] == 65000.0

    @pytest.mark.asyncio
    async def test_get_exchange_rates_not_found(self, mock_cmc):
        mock_cmc.get_exchange_rates.return_value = {}
        handler = server._call_tool_handler
        result = await handler("get_exchange_rates", {"symbol": "INVALID"})
        data = json.loads(result[0].text)
        assert "error" in data


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, mock_cmc):
        handler = server._call_tool_handler
        result = await handler("nonexistent", {})
        data = json.loads(result[0].text)
        assert "error" in data


class TestApiError:
    @pytest.mark.asyncio
    async def test_api_error_handled(self, mock_cmc):
        mock_cmc.get_quotes.side_effect = Exception("API rate limit exceeded")
        handler = server._call_tool_handler
        result = await handler("get_price", {"symbols": ["BTC"]})
        data = json.loads(result[0].text)
        assert "error" in data
        assert "rate limit" in data["error"]["message"]
