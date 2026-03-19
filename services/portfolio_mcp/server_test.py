"""
Tests for the portfolio MCP server.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.portfolio_mcp.server import create_server


class TestPortfolioMcpServer:
    """Test cases for the portfolio MCP server tools."""

    @pytest.fixture
    def postgres_client(self):
        """Create a mock PostgreSQL client."""
        return AsyncMock()

    @pytest.fixture
    def server(self, postgres_client):
        """Create a portfolio MCP server instance."""
        return create_server(postgres_client)

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        """Test that all 3 tools are listed."""
        handlers = server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        assert list_tools_handler is not None

        result = await list_tools_handler(MagicMock())
        assert len(result.tools) == 3

        tool_names = [t.name for t in result.tools]
        assert "get_positions" in tool_names
        assert "get_balance" in tool_names
        assert "validate_trade" in tool_names

    @pytest.mark.asyncio
    async def test_get_positions(self, server, postgres_client):
        """Test get_positions tool."""
        postgres_client.get_positions.return_value = {
            "items": [
                {
                    "symbol": "BTC/USD",
                    "side": "LONG",
                    "size": 0.5,
                    "entry_price": 50000.0,
                    "current_price": 51000.0,
                    "unrealized_pnl": 500.0,
                    "opened_at": "2026-03-15T10:00:00",
                }
            ],
            "pagination": {
                "offset": 0,
                "limit": 50,
                "total": 1,
                "has_more": False,
            },
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_positions"
        request.params.arguments = {"symbol": "BTC/USD"}

        result = await call_tool_handler(request)

        postgres_client.get_positions.assert_called_once_with(
            symbol="BTC/USD",
            limit=50,
            offset=0,
        )
        response = json.loads(result.content[0].text)
        assert len(response["items"]) == 1
        assert response["items"][0]["symbol"] == "BTC/USD"
        assert response["items"][0]["unrealized_pnl"] == 500.0

    @pytest.mark.asyncio
    async def test_get_positions_no_filter(self, server, postgres_client):
        """Test get_positions without symbol filter."""
        postgres_client.get_positions.return_value = {
            "items": [],
            "pagination": {"offset": 0, "limit": 50, "total": 0, "has_more": False},
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_positions"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        postgres_client.get_positions.assert_called_once_with(
            symbol=None,
            limit=50,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_get_balance(self, server, postgres_client):
        """Test get_balance tool."""
        postgres_client.get_balance.return_value = {
            "total_balance": 100000.0,
            "available_balance": 75000.0,
            "margin_used": 25000.0,
            "unrealized_pnl": 1500.0,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_balance"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        postgres_client.get_balance.assert_called_once()
        response = json.loads(result.content[0].text)
        assert response["total_balance"] == 100000.0
        assert response["available_balance"] == 75000.0

    @pytest.mark.asyncio
    async def test_validate_trade(self, server, postgres_client):
        """Test validate_trade tool."""
        postgres_client.validate_trade.return_value = {
            "valid": True,
            "reason": "Trade passes all risk checks",
            "max_size": 1.5,
            "risk_score": 0.33,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "validate_trade"
        request.params.arguments = {
            "symbol": "BTC/USD",
            "side": "BUY",
            "size": 0.5,
            "price": 50000.0,
        }

        result = await call_tool_handler(request)

        postgres_client.validate_trade.assert_called_once_with(
            symbol="BTC/USD",
            side="BUY",
            size=0.5,
            price=50000.0,
        )
        response = json.loads(result.content[0].text)
        assert response["valid"] is True
        assert response["risk_score"] == 0.33

    @pytest.mark.asyncio
    async def test_validate_trade_no_price(self, server, postgres_client):
        """Test validate_trade without price parameter."""
        postgres_client.validate_trade.return_value = {
            "valid": True,
            "reason": "Trade passes all risk checks",
            "max_size": 7500.0,
            "risk_score": 0.1,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "validate_trade"
        request.params.arguments = {
            "symbol": "ETH/USD",
            "side": "SELL",
            "size": 10.0,
        }

        result = await call_tool_handler(request)

        postgres_client.validate_trade.assert_called_once_with(
            symbol="ETH/USD",
            side="SELL",
            size=10.0,
            price=None,
        )

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
