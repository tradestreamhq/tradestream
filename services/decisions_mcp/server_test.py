"""
Tests for the decisions MCP server.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.decisions_mcp.server import create_server


class TestDecisionsMcpServer:
    """Test cases for the decisions MCP server tools."""

    @pytest.fixture
    def postgres_client(self):
        """Create a mock PostgreSQL client."""
        return AsyncMock()

    @pytest.fixture
    def server(self, postgres_client):
        """Create a decisions MCP server instance."""
        return create_server(postgres_client)

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        """Test that all 2 tools are listed."""
        handlers = server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        assert list_tools_handler is not None

        result = await list_tools_handler(MagicMock())
        assert len(result.tools) == 2

        tool_names = [t.name for t in result.tools]
        assert "get_recent_decisions" in tool_names
        assert "save_decision" in tool_names

    @pytest.mark.asyncio
    async def test_get_recent_decisions(self, server, postgres_client):
        """Test get_recent_decisions tool."""
        postgres_client.get_recent_decisions.return_value = {
            "items": [
                {
                    "decision_id": "dec-001",
                    "symbol": "BTC/USD",
                    "action": "BUY",
                    "confidence": 0.85,
                    "opportunity_score": 0.72,
                    "reasoning": "Strong bullish consensus across strategies",
                    "tool_calls": None,
                    "created_at": "2026-03-15T10:00:00",
                }
            ],
            "pagination": {
                "offset": 0,
                "limit": 10,
                "total": 1,
                "has_more": False,
            },
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_recent_decisions"
        request.params.arguments = {"symbol": "BTC/USD"}

        result = await call_tool_handler(request)

        postgres_client.get_recent_decisions.assert_called_once_with(
            symbol="BTC/USD",
            action=None,
            limit=10,
            offset=0,
        )
        response = json.loads(result.content[0].text)
        assert len(response["items"]) == 1
        assert response["items"][0]["action"] == "BUY"
        assert response["items"][0]["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_get_recent_decisions_with_action_filter(
        self, server, postgres_client
    ):
        """Test get_recent_decisions with action filter."""
        postgres_client.get_recent_decisions.return_value = {
            "items": [],
            "pagination": {"offset": 0, "limit": 10, "total": 0, "has_more": False},
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_recent_decisions"
        request.params.arguments = {
            "symbol": "ETH/USD",
            "action": "SELL",
            "limit": 5,
        }

        result = await call_tool_handler(request)

        postgres_client.get_recent_decisions.assert_called_once_with(
            symbol="ETH/USD",
            action="SELL",
            limit=5,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_save_decision(self, server, postgres_client):
        """Test save_decision tool."""
        postgres_client.save_decision.return_value = {
            "decision_id": "dec-002",
            "saved": True,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "save_decision"
        request.params.arguments = {
            "symbol": "BTC/USD",
            "action": "BUY",
            "confidence": 0.9,
            "reasoning": "Multiple strategies showing bullish signals",
            "opportunity_score": 0.8,
        }

        result = await call_tool_handler(request)

        postgres_client.save_decision.assert_called_once_with(
            symbol="BTC/USD",
            action="BUY",
            confidence=0.9,
            reasoning="Multiple strategies showing bullish signals",
            opportunity_score=0.8,
            tool_calls=None,
        )
        response = json.loads(result.content[0].text)
        assert response["saved"] is True
        assert response["decision_id"] == "dec-002"

    @pytest.mark.asyncio
    async def test_save_decision_with_tool_calls(self, server, postgres_client):
        """Test save_decision with tool_calls parameter."""
        postgres_client.save_decision.return_value = {
            "decision_id": "dec-003",
            "saved": True,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "save_decision"
        request.params.arguments = {
            "symbol": "ETH/USD",
            "action": "HOLD",
            "confidence": 0.5,
            "reasoning": "Mixed signals",
            "tool_calls": [
                {"tool": "get_top_strategies", "result": "mixed"},
            ],
        }

        result = await call_tool_handler(request)

        postgres_client.save_decision.assert_called_once_with(
            symbol="ETH/USD",
            action="HOLD",
            confidence=0.5,
            reasoning="Mixed signals",
            opportunity_score=None,
            tool_calls=[{"tool": "get_top_strategies", "result": "mixed"}],
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
