"""Tests for the Strategy MCP wrapper."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.strategy_api.mcp_server import StrategyMCPWrapper, create_server


class TestStrategyMCPWrapper:
    @pytest.fixture
    def server(self):
        return create_server("http://localhost:8080")

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        handlers = server._tool_handlers
        # Get tool list
        tools_handler = server._list_tools_handler
        tools = await tools_handler()
        names = {t.name for t in tools}
        assert names == {
            "get_top_strategies",
            "evaluate_strategy",
            "get_strategy_signal",
            "list_specs",
            "get_spec",
            "create_spec",
        }

    @pytest.mark.asyncio
    async def test_get_top_strategies_calls_api(self, server):
        with patch.object(StrategyMCPWrapper, "_get") as mock_get:
            mock_get.return_value = {"data": [], "meta": {"total": 0}}
            handler = server._call_tool_handler
            result = await handler("get_top_strategies", {"limit": 5})
            mock_get.assert_called_once()
            args = mock_get.call_args
            assert args[0][0] == "/implementations"
            assert args[1]["params"]["limit"] == 5
            assert args[1]["params"]["order_by"] == "sharpe"

    @pytest.mark.asyncio
    async def test_evaluate_strategy_calls_api(self, server):
        with patch.object(StrategyMCPWrapper, "_post") as mock_post:
            mock_post.return_value = {"data": {"status": "SUBMITTED"}}
            handler = server._call_tool_handler
            result = await handler(
                "evaluate_strategy",
                {"implementation_id": "abc", "instrument": "BTC/USD", "days": 7},
            )
            mock_post.assert_called_once()
            args = mock_post.call_args
            assert "/implementations/abc/evaluate" in args[0][0]

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server):
        handler = server._call_tool_handler
        result = await handler("nonexistent", {})
        data = json.loads(result[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_api_error_handled(self, server):
        with patch.object(
            StrategyMCPWrapper, "_get", side_effect=Exception("connection refused")
        ):
            handler = server._call_tool_handler
            result = await handler("list_specs", {})
            data = json.loads(result[0].text)
            assert "error" in data
            assert "connection refused" in data["error"]
