"""Tests for the strategy monitor MCP server."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.strategy_monitor_mcp.server import StrategyMonitorMcpServer


@pytest.fixture
def mock_pg():
    """Create a mock PostgresClient."""
    client = AsyncMock()
    client.get_strategies = AsyncMock(
        return_value={
            "strategies": [
                {
                    "id": "strat-1",
                    "symbol": "BTC/USD",
                    "strategy_type": "SMA_EMA_CROSSOVER",
                    "current_score": 1.5,
                }
            ],
            "count": 1,
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }
    )
    client.get_strategy_by_id = AsyncMock(
        return_value={
            "id": "strat-1",
            "symbol": "BTC/USD",
            "strategy_type": "SMA_EMA_CROSSOVER",
            "current_score": 1.5,
        }
    )
    client.get_metrics = AsyncMock(
        return_value={
            "total_strategies": 100,
            "avg_score": 0.8,
            "by_type": [{"strategy_type": "SMA_EMA_CROSSOVER", "count": 50}],
        }
    )
    client.get_symbols = AsyncMock(return_value=["BTC/USD", "ETH/USD"])
    client.get_strategy_types = AsyncMock(
        return_value=["SMA_EMA_CROSSOVER", "EMA_MACD"]
    )
    return client


@pytest.fixture
def server(mock_pg):
    """Create a StrategyMonitorMcpServer with mock client."""
    return StrategyMonitorMcpServer(mock_pg)


class TestToolDefinitions:
    def test_defines_expected_tools(self, server):
        tools = server.tool_definitions()
        names = {t.name for t in tools}
        assert names == {
            "get_strategies",
            "get_strategy_by_id",
            "get_metrics",
            "get_symbols",
            "get_strategy_types",
        }

    def test_all_tools_have_descriptions(self, server):
        for tool in server.tool_definitions():
            assert tool.description, f"Tool {tool.name} missing description"

    def test_all_tools_have_schemas(self, server):
        for tool in server.tool_definitions():
            assert tool.input_schema["type"] == "object"


class TestHandleTool:
    @pytest.mark.asyncio
    async def test_get_strategies(self, server, mock_pg):
        result = await server.handle_tool(
            "get_strategies", {"symbol": "BTC/USD", "limit": 10}
        )
        assert result["count"] == 1
        mock_pg.get_strategies.assert_called_once_with(
            symbol="BTC/USD",
            strategy_type=None,
            min_score=None,
            limit=10,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_get_strategy_by_id(self, server, mock_pg):
        result = await server.handle_tool(
            "get_strategy_by_id", {"strategy_id": "strat-1"}
        )
        assert result["id"] == "strat-1"
        mock_pg.get_strategy_by_id.assert_called_once_with("strat-1")

    @pytest.mark.asyncio
    async def test_get_strategy_by_id_not_found(self, server, mock_pg):
        mock_pg.get_strategy_by_id.return_value = None
        with pytest.raises(KeyError, match="Strategy not found"):
            await server.handle_tool("get_strategy_by_id", {"strategy_id": "missing"})

    @pytest.mark.asyncio
    async def test_get_metrics(self, server, mock_pg):
        result = await server.handle_tool("get_metrics", {})
        assert result["total_strategies"] == 100
        mock_pg.get_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_symbols(self, server, mock_pg):
        result = await server.handle_tool("get_symbols", {})
        assert result == ["BTC/USD", "ETH/USD"]

    @pytest.mark.asyncio
    async def test_get_strategy_types(self, server, mock_pg):
        result = await server.handle_tool("get_strategy_types", {})
        assert result == ["SMA_EMA_CROSSOVER", "EMA_MACD"]

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server):
        with pytest.raises(ValueError, match="Unknown tool"):
            await server.handle_tool("nonexistent", {})
