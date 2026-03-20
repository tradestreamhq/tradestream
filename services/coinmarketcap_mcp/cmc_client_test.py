"""Tests for the CoinMarketCap async client."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.coinmarketcap_mcp.cmc_client import CoinMarketCapClient


@pytest.fixture
def client():
    return CoinMarketCapClient(api_key="test-key")


class TestGetListings:
    @pytest.mark.asyncio
    async def test_get_listings_success(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "data": [
                    {"symbol": "BTC", "name": "Bitcoin"},
                    {"symbol": "ETH", "name": "Ethereum"},
                ]
            },
            request=httpx.Request("GET", "https://test"),
        )
        with patch.object(client._client, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await client.get_listings(limit=2)
            assert len(result) == 2
            assert result[0]["symbol"] == "BTC"

    @pytest.mark.asyncio
    async def test_get_listings_empty(self, client):
        mock_response = httpx.Response(
            200,
            json={"data": []},
            request=httpx.Request("GET", "https://test"),
        )
        with patch.object(client._client, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await client.get_listings()
            assert result == []


class TestGetQuotes:
    @pytest.mark.asyncio
    async def test_get_quotes_success(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "data": {
                    "BTC": [{"symbol": "BTC", "quote": {"USD": {"price": 65000}}}]
                }
            },
            request=httpx.Request("GET", "https://test"),
        )
        with patch.object(client._client, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await client.get_quotes(["BTC"])
            assert "BTC" in result


class TestGetGlobalMetrics:
    @pytest.mark.asyncio
    async def test_get_global_metrics(self, client):
        mock_response = httpx.Response(
            200,
            json={"data": {"total_market_cap": 2_500_000_000_000}},
            request=httpx.Request("GET", "https://test"),
        )
        with patch.object(client._client, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await client.get_global_metrics()
            assert "total_market_cap" in result


class TestGetExchangeRates:
    @pytest.mark.asyncio
    async def test_get_exchange_rates_found(self, client):
        mock_response = httpx.Response(
            200,
            json={
                "data": {
                    "BTC": [{"symbol": "BTC", "quote": {"USD": {"price": 65000}}}]
                }
            },
            request=httpx.Request("GET", "https://test"),
        )
        with patch.object(client._client, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await client.get_exchange_rates(symbol="BTC")
            assert result["symbol"] == "BTC"

    @pytest.mark.asyncio
    async def test_get_exchange_rates_not_found(self, client):
        mock_response = httpx.Response(
            200,
            json={"data": {}},
            request=httpx.Request("GET", "https://test"),
        )
        with patch.object(client._client, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await client.get_exchange_rates(symbol="NOEXIST")
            assert result == {}
