"""
Tests for the market MCP server.
"""

import json
import pytest
from unittest.mock import MagicMock

from services.market_mcp.server import create_server


class TestMarketMcpServer:
    """Test cases for the market MCP server tools."""

    @pytest.fixture
    def influxdb_client(self):
        """Create a mock InfluxDB client."""
        return MagicMock()

    @pytest.fixture
    def redis_client(self):
        """Create a mock Redis client."""
        return MagicMock()

    @pytest.fixture
    def server(self, influxdb_client, redis_client):
        """Create a market MCP server instance."""
        return create_server(influxdb_client, redis_client)

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        """Test that all 5 tools are listed."""
        handlers = server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        assert list_tools_handler is not None

        result = await list_tools_handler(MagicMock())
        assert len(result.tools) == 5

        tool_names = [t.name for t in result.tools]
        assert "get_candles" in tool_names
        assert "get_latest_price" in tool_names
        assert "get_volatility" in tool_names
        assert "get_symbols" in tool_names
        assert "get_market_summary" in tool_names

    @pytest.mark.asyncio
    async def test_get_candles(self, server, influxdb_client):
        """Test get_candles tool."""
        influxdb_client.get_candles.return_value = [
            {
                "timestamp": "2026-03-08T12:00:00+00:00",
                "open": 50000.0,
                "high": 50500.0,
                "low": 49800.0,
                "close": 50200.0,
                "volume": 100.5,
            }
        ]

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_candles"
        request.params.arguments = {
            "symbol": "BTC/USD",
            "timeframe": "1m",
            "limit": 50,
        }

        result = await call_tool_handler(request)

        influxdb_client.get_candles.assert_called_once_with(
            symbol="BTC/USD",
            timeframe="1m",
            start=None,
            end=None,
            limit=50,
        )
        response = json.loads(result.content[0].text)
        assert len(response) == 1
        assert response[0]["close"] == 50200.0

    @pytest.mark.asyncio
    async def test_get_candles_defaults(self, server, influxdb_client):
        """Test get_candles with default parameters."""
        influxdb_client.get_candles.return_value = []

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_candles"
        request.params.arguments = {"symbol": "ETH/USD", "timeframe": "5m"}

        result = await call_tool_handler(request)

        influxdb_client.get_candles.assert_called_once_with(
            symbol="ETH/USD",
            timeframe="5m",
            start=None,
            end=None,
            limit=100,
        )

    @pytest.mark.asyncio
    async def test_get_latest_price(self, server, influxdb_client):
        """Test get_latest_price tool."""
        influxdb_client.get_latest_price.return_value = {
            "symbol": "BTC/USD",
            "price": 50200.0,
            "volume_24h": 12345.67,
            "change_24h": 2.5,
            "timestamp": "2026-03-08T12:00:00+00:00",
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_latest_price"
        request.params.arguments = {"symbol": "BTC/USD"}

        result = await call_tool_handler(request)

        influxdb_client.get_latest_price.assert_called_once_with(
            symbol="BTC/USD",
        )
        response = json.loads(result.content[0].text)
        assert response["price"] == 50200.0
        assert response["symbol"] == "BTC/USD"

    @pytest.mark.asyncio
    async def test_get_volatility(self, server, influxdb_client):
        """Test get_volatility tool."""
        influxdb_client.get_volatility.return_value = {
            "symbol": "BTC/USD",
            "volatility": 0.015,
            "atr": 250.0,
            "period": 60,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_volatility"
        request.params.arguments = {"symbol": "BTC/USD", "period_minutes": 120}

        result = await call_tool_handler(request)

        influxdb_client.get_volatility.assert_called_once_with(
            symbol="BTC/USD",
            period_minutes=120,
        )
        response = json.loads(result.content[0].text)
        assert response["volatility"] == 0.015
        assert response["atr"] == 250.0

    @pytest.mark.asyncio
    async def test_get_volatility_defaults(self, server, influxdb_client):
        """Test get_volatility with default period."""
        influxdb_client.get_volatility.return_value = {
            "symbol": "ETH/USD",
            "volatility": None,
            "atr": None,
            "period": 60,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_volatility"
        request.params.arguments = {"symbol": "ETH/USD"}

        result = await call_tool_handler(request)

        influxdb_client.get_volatility.assert_called_once_with(
            symbol="ETH/USD",
            period_minutes=60,
        )

    @pytest.mark.asyncio
    async def test_get_symbols(self, server, redis_client):
        """Test get_symbols tool."""
        redis_client.get_symbols.return_value = [
            {
                "id": "btcusd",
                "asset_class": "crypto",
                "base": "BTC",
                "quote": "USD",
                "exchange": "multi",
            },
            {
                "id": "ethusd",
                "asset_class": "crypto",
                "base": "ETH",
                "quote": "USD",
                "exchange": "multi",
            },
        ]

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_symbols"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        redis_client.get_symbols.assert_called_once()
        response = json.loads(result.content[0].text)
        assert len(response) == 2
        assert response[0]["base"] == "BTC"

    @pytest.mark.asyncio
    async def test_get_market_summary(self, server, influxdb_client):
        """Test get_market_summary tool."""
        influxdb_client.get_market_summary.return_value = {
            "symbol": "BTC/USD",
            "price": 50200.0,
            "change_1h": 0.5,
            "change_24h": 2.5,
            "volume_24h": 12345.67,
            "volatility": 0.015,
            "high_24h": 51000.0,
            "low_24h": 49000.0,
            "vwap": 50100.0,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_market_summary"
        request.params.arguments = {"symbol": "BTC/USD"}

        result = await call_tool_handler(request)

        influxdb_client.get_market_summary.assert_called_once_with(
            symbol="BTC/USD",
        )
        response = json.loads(result.content[0].text)
        assert response["price"] == 50200.0
        assert response["vwap"] == 50100.0
        assert response["high_24h"] == 51000.0

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server):
        """Test calling an unknown tool returns error."""
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "nonexistent_tool"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        response = json.loads(result.content[0].text)
        assert "error" in response
