"""
Tests for the strategy database MCP server.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.strategy_db_mcp.server import create_server


class TestStrategyDbMcpServer:
    """Test cases for the strategy database MCP server tools."""

    @pytest.fixture
    def postgres_client(self):
        """Create a mock PostgreSQL client."""
        return AsyncMock()

    @pytest.fixture
    def server(self, postgres_client):
        """Create a strategy database MCP server instance."""
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
        assert "get_top_specs" in tool_names
        assert "get_implementations" in tool_names
        assert "submit_new_spec" in tool_names

    @pytest.mark.asyncio
    async def test_get_top_specs(self, server, postgres_client):
        """Test get_top_specs tool."""
        postgres_client.get_top_specs.return_value = {
            "items": [
                {
                    "spec_id": "spec-001",
                    "name": "momentum_crossover",
                    "indicators": [{"name": "SMA", "period": 20}],
                    "avg_sharpe": 2.1,
                    "implementations_count": 5,
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
        request.params.name = "get_top_specs"
        request.params.arguments = {"limit": 10}

        result = await call_tool_handler(request)

        postgres_client.get_top_specs.assert_called_once_with(
            limit=10,
            offset=0,
            source="ALL",
        )
        response = json.loads(result.content[0].text)
        assert "data" in response
        assert "_metadata" in response
        assert len(response["data"]["items"]) == 1
        assert response["data"]["items"][0]["name"] == "momentum_crossover"
        assert response["data"]["items"][0]["avg_sharpe"] == 2.1
        assert isinstance(response["_metadata"]["latency_ms"], int)
        assert response["_metadata"]["source"] == "postgresql"

    @pytest.mark.asyncio
    async def test_get_top_specs_with_source_filter(self, server, postgres_client):
        """Test get_top_specs with source filter."""
        postgres_client.get_top_specs.return_value = {
            "items": [],
            "pagination": {"offset": 0, "limit": 10, "total": 0, "has_more": False},
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_top_specs"
        request.params.arguments = {"source": "LLM_GENERATED", "limit": 5}

        result = await call_tool_handler(request)

        postgres_client.get_top_specs.assert_called_once_with(
            limit=5,
            offset=0,
            source="LLM_GENERATED",
        )

    @pytest.mark.asyncio
    async def test_get_implementations(self, server, postgres_client):
        """Test get_implementations tool."""
        postgres_client.get_implementations.return_value = {
            "items": [
                {
                    "impl_id": "impl-001",
                    "parameters": {"sma_period": 20, "rsi_period": 14},
                    "symbol": "BTC/USD",
                    "forward_sharpe": 1.8,
                    "forward_accuracy": 0.62,
                    "status": "VALIDATED",
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
        request.params.name = "get_implementations"
        request.params.arguments = {"spec_id": "spec-001"}

        result = await call_tool_handler(request)

        postgres_client.get_implementations.assert_called_once_with(
            spec_id="spec-001",
            status="VALIDATED",
            limit=10,
            offset=0,
        )
        response = json.loads(result.content[0].text)
        assert "data" in response
        assert "_metadata" in response
        assert len(response["data"]["items"]) == 1
        assert response["data"]["items"][0]["forward_sharpe"] == 1.8
        assert isinstance(response["_metadata"]["latency_ms"], int)
        assert response["_metadata"]["source"] == "postgresql"

    @pytest.mark.asyncio
    async def test_get_implementations_all_status(self, server, postgres_client):
        """Test get_implementations with ALL status filter."""
        postgres_client.get_implementations.return_value = {
            "items": [],
            "pagination": {"offset": 0, "limit": 10, "total": 0, "has_more": False},
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_implementations"
        request.params.arguments = {"spec_id": "spec-001", "status": "ALL"}

        result = await call_tool_handler(request)

        postgres_client.get_implementations.assert_called_once_with(
            spec_id="spec-001",
            status="ALL",
            limit=10,
            offset=0,
        )

    @pytest.mark.asyncio
    async def test_submit_new_spec(self, server, postgres_client):
        """Test submit_new_spec tool."""
        postgres_client.submit_new_spec.return_value = {
            "spec_id": "spec-new-001",
            "created": True,
            "validation_errors": [],
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "submit_new_spec"
        request.params.arguments = {
            "name": "rsi_mean_reversion",
            "indicators": [{"name": "RSI", "period": 14}],
            "entry_conditions": [{"rsi_below": 30}],
            "exit_conditions": [{"rsi_above": 70}],
            "parameters": [{"name": "rsi_period", "min": 7, "max": 21}],
            "description": "RSI-based mean reversion strategy",
            "reasoning": "Historical analysis shows RSI extremes provide good entry points",
        }

        result = await call_tool_handler(request)

        postgres_client.submit_new_spec.assert_called_once_with(
            name="rsi_mean_reversion",
            indicators=[{"name": "RSI", "period": 14}],
            entry_conditions=[{"rsi_below": 30}],
            exit_conditions=[{"rsi_above": 70}],
            parameters=[{"name": "rsi_period", "min": 7, "max": 21}],
            description="RSI-based mean reversion strategy",
            reasoning="Historical analysis shows RSI extremes provide good entry points",
        )
        response = json.loads(result.content[0].text)
        assert "data" in response
        assert "_metadata" in response
        assert response["data"]["created"] is True
        assert response["data"]["spec_id"] == "spec-new-001"
        assert response["data"]["validation_errors"] == []
        assert isinstance(response["_metadata"]["latency_ms"], int)
        assert response["_metadata"]["source"] == "postgresql"

    @pytest.mark.asyncio
    async def test_submit_new_spec_duplicate(self, server, postgres_client):
        """Test submit_new_spec returns error for duplicate name."""
        postgres_client.submit_new_spec.return_value = {
            "spec_id": "spec-existing",
            "created": False,
            "validation_errors": [
                "A spec with name 'existing_strategy' already exists"
            ],
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "submit_new_spec"
        request.params.arguments = {
            "name": "existing_strategy",
            "indicators": [],
            "entry_conditions": [],
            "exit_conditions": [],
            "parameters": [],
        }

        result = await call_tool_handler(request)

        response = json.loads(result.content[0].text)
        assert "data" in response
        assert "_metadata" in response
        assert response["data"]["created"] is False
        assert len(response["data"]["validation_errors"]) > 0

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
        assert response["error"]["code"] == "UNKNOWN_TOOL"
        assert "_metadata" in response
