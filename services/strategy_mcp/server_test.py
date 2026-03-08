"""
Tests for the strategy MCP server.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.strategy_mcp.server import create_server


class TestMCPServer:
    """Test cases for the MCP server tools."""

    @pytest.fixture
    def postgres_client(self):
        """Create a mock PostgresClient."""
        return AsyncMock()

    @pytest.fixture
    def server(self, postgres_client):
        """Create a strategy MCP server instance."""
        return create_server(postgres_client)

    @pytest.mark.asyncio
    async def test_list_tools_returns_six(self, server):
        """Test that list_tools returns all 6 tools."""
        handlers = server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        assert list_tools_handler is not None

        result = await list_tools_handler(MagicMock())
        assert len(result.tools) == 6

        names = {t.name for t in result.tools}
        assert names == {
            "get_top_strategies",
            "get_spec",
            "get_performance",
            "list_strategy_types",
            "create_spec",
            "get_walk_forward",
        }

    @pytest.mark.asyncio
    async def test_get_top_strategies(self, server, postgres_client):
        """Test get_top_strategies tool."""
        postgres_client.get_top_strategies.return_value = [
            {
                "spec_name": "macd",
                "impl_id": "abc",
                "score": 1.5,
                "params": {},
                "strategy_type": "macd",
            }
        ]

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_top_strategies"
        request.params.arguments = {"symbol": "BTC/USD", "limit": 5}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert len(data) == 1
        assert data[0]["spec_name"] == "macd"
        postgres_client.get_top_strategies.assert_called_once_with(
            symbol="BTC/USD", limit=5, min_score=0.0
        )

    @pytest.mark.asyncio
    async def test_get_top_strategies_defaults(self, server, postgres_client):
        """Test get_top_strategies with default parameters."""
        postgres_client.get_top_strategies.return_value = []

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_top_strategies"
        request.params.arguments = {"symbol": "ETH/USD"}

        await call_tool_handler(request)

        postgres_client.get_top_strategies.assert_called_once_with(
            symbol="ETH/USD", limit=10, min_score=0.0
        )

    @pytest.mark.asyncio
    async def test_get_spec_found(self, server, postgres_client):
        """Test get_spec when spec exists."""
        postgres_client.get_spec.return_value = {
            "name": "macd_crossover",
            "indicators": {"macd": {}},
            "entry_conditions": {},
            "exit_conditions": {},
            "parameters": {},
            "source": "MIGRATED",
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_spec"
        request.params.arguments = {"spec_name": "macd_crossover"}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert data["name"] == "macd_crossover"

    @pytest.mark.asyncio
    async def test_get_spec_not_found(self, server, postgres_client):
        """Test get_spec when spec doesn't exist."""
        postgres_client.get_spec.return_value = None

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_spec"
        request.params.arguments = {"spec_name": "nonexistent"}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_performance(self, server, postgres_client):
        """Test get_performance tool."""
        postgres_client.get_performance.return_value = {
            "backtest": {"sharpe_ratio": 1.5},
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_performance"
        request.params.arguments = {"impl_id": "abc-123"}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert "backtest" in data
        postgres_client.get_performance.assert_called_once_with(
            impl_id="abc-123", environment=None
        )

    @pytest.mark.asyncio
    async def test_get_performance_with_environment(self, server, postgres_client):
        """Test get_performance with environment filter."""
        postgres_client.get_performance.return_value = {"backtest": {"sharpe_ratio": 1.5}}

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_performance"
        request.params.arguments = {"impl_id": "abc-123", "environment": "backtest"}

        await call_tool_handler(request)

        postgres_client.get_performance.assert_called_once_with(
            impl_id="abc-123", environment="backtest"
        )

    @pytest.mark.asyncio
    async def test_get_performance_not_found(self, server, postgres_client):
        """Test get_performance when impl doesn't exist."""
        postgres_client.get_performance.return_value = None

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_performance"
        request.params.arguments = {"impl_id": "nonexistent"}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_list_strategy_types(self, server, postgres_client):
        """Test list_strategy_types tool."""
        postgres_client.list_strategy_types.return_value = ["macd", "rsi"]

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "list_strategy_types"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert data == ["macd", "rsi"]

    @pytest.mark.asyncio
    async def test_create_spec(self, server, postgres_client):
        """Test create_spec tool."""
        postgres_client.create_spec.return_value = {"spec_id": "new-uuid"}

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "create_spec"
        request.params.arguments = {
            "name": "test_spec",
            "indicators": {"rsi": {"period": 14}},
            "entry_conditions": {"rsi_below": 30},
            "exit_conditions": {"rsi_above": 70},
            "parameters": {"period": {"min": 5, "max": 30}},
            "description": "A test strategy",
        }

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert data["spec_id"] == "new-uuid"
        postgres_client.create_spec.assert_called_once_with(
            name="test_spec",
            indicators={"rsi": {"period": 14}},
            entry_conditions={"rsi_below": 30},
            exit_conditions={"rsi_above": 70},
            parameters={"period": {"min": 5, "max": 30}},
            description="A test strategy",
        )

    @pytest.mark.asyncio
    async def test_get_walk_forward(self, server, postgres_client):
        """Test get_walk_forward tool."""
        postgres_client.get_walk_forward.return_value = {
            "validation_status": "APPROVED",
            "sharpe_degradation": 0.15,
            "in_sample_sharpe": 2.0,
            "out_of_sample_sharpe": 1.7,
            "window_results": [],
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_walk_forward"
        request.params.arguments = {"impl_id": "abc-123"}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert data["validation_status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_get_walk_forward_not_found(self, server, postgres_client):
        """Test get_walk_forward when results don't exist."""
        postgres_client.get_walk_forward.return_value = None

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_walk_forward"
        request.params.arguments = {"impl_id": "nonexistent"}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server, postgres_client):
        """Test calling an unknown tool."""
        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "unknown_tool"
        request.params.arguments = {}

        result = await call_tool_handler(request)

        data = json.loads(result.content[0].text)
        assert "error" in data
        assert "Unknown tool" in data["error"]
