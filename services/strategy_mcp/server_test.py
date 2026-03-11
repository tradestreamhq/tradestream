"""
Tests for the strategy MCP server.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch

from services.strategy_mcp.server import (
    server,
    call_tool,
    list_tools,
    _set_postgres_client,
)


class TestMCPServer:
    """Test cases for the MCP server tools."""

    @pytest.fixture
    def mock_pg(self):
        """Create a mock PostgresClient."""
        pg = AsyncMock()
        _set_postgres_client(pg)
        return pg

    @pytest.mark.asyncio
    async def test_list_tools_returns_seven(self):
        """Test that list_tools returns all 7 tools."""
        tools = await list_tools()
        assert len(tools) == 7
        names = {t.name for t in tools}
        assert names == {
            "get_top_strategies",
            "get_spec",
            "get_performance",
            "get_performance_batch",
            "list_strategy_types",
            "create_spec",
            "get_walk_forward",
        }

    @pytest.mark.asyncio
    async def test_get_top_strategies(self, mock_pg):
        """Test get_top_strategies tool."""
        mock_pg.get_top_strategies.return_value = [
            {
                "spec_name": "macd",
                "impl_id": "abc",
                "score": 1.5,
                "params": {},
                "strategy_type": "macd",
            }
        ]

        result = await call_tool(
            "get_top_strategies", {"symbol": "BTC/USD", "limit": 5}
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["spec_name"] == "macd"
        mock_pg.get_top_strategies.assert_called_once_with(
            symbol="BTC/USD", limit=5, min_score=0.0
        )

    @pytest.mark.asyncio
    async def test_get_top_strategies_defaults(self, mock_pg):
        """Test get_top_strategies with default parameters."""
        mock_pg.get_top_strategies.return_value = []

        result = await call_tool("get_top_strategies", {"symbol": "ETH/USD"})

        mock_pg.get_top_strategies.assert_called_once_with(
            symbol="ETH/USD", limit=10, min_score=0.0
        )

    @pytest.mark.asyncio
    async def test_get_spec_found(self, mock_pg):
        """Test get_spec when spec exists."""
        mock_pg.get_spec.return_value = {
            "name": "macd_crossover",
            "indicators": {"macd": {}},
            "entry_conditions": {},
            "exit_conditions": {},
            "parameters": {},
            "source": "MIGRATED",
        }

        result = await call_tool("get_spec", {"spec_name": "macd_crossover"})

        data = json.loads(result[0].text)
        assert data["name"] == "macd_crossover"

    @pytest.mark.asyncio
    async def test_get_spec_not_found(self, mock_pg):
        """Test get_spec when spec doesn't exist."""
        mock_pg.get_spec.return_value = None

        result = await call_tool("get_spec", {"spec_name": "nonexistent"})

        data = json.loads(result[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_performance(self, mock_pg):
        """Test get_performance tool."""
        mock_pg.get_performance.return_value = {
            "backtest": {"sharpe_ratio": 1.5},
        }

        result = await call_tool("get_performance", {"impl_id": "abc-123"})

        data = json.loads(result[0].text)
        assert "backtest" in data
        mock_pg.get_performance.assert_called_once_with(
            impl_id="abc-123", environment=None
        )

    @pytest.mark.asyncio
    async def test_get_performance_with_environment(self, mock_pg):
        """Test get_performance with environment filter."""
        mock_pg.get_performance.return_value = {"backtest": {"sharpe_ratio": 1.5}}

        await call_tool(
            "get_performance", {"impl_id": "abc-123", "environment": "backtest"}
        )

        mock_pg.get_performance.assert_called_once_with(
            impl_id="abc-123", environment="backtest"
        )

    @pytest.mark.asyncio
    async def test_get_performance_not_found(self, mock_pg):
        """Test get_performance when impl doesn't exist."""
        mock_pg.get_performance.return_value = None

        result = await call_tool("get_performance", {"impl_id": "nonexistent"})

        data = json.loads(result[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_performance_batch(self, mock_pg):
        """Test get_performance_batch tool."""
        mock_pg.get_performance_batch.return_value = {
            "impl-1": {"backtest": {"sharpe_ratio": 1.5}},
            "impl-2": {"backtest": {"sharpe_ratio": 2.0}},
        }

        result = await call_tool(
            "get_performance_batch", {"impl_ids": ["impl-1", "impl-2"]}
        )

        data = json.loads(result[0].text)
        assert "impl-1" in data
        assert "impl-2" in data
        mock_pg.get_performance_batch.assert_called_once_with(
            impl_ids=["impl-1", "impl-2"], environment=None
        )

    @pytest.mark.asyncio
    async def test_get_performance_batch_with_environment(self, mock_pg):
        """Test get_performance_batch with environment filter."""
        mock_pg.get_performance_batch.return_value = {
            "impl-1": {"backtest": {"sharpe_ratio": 1.5}},
        }

        await call_tool(
            "get_performance_batch",
            {"impl_ids": ["impl-1"], "environment": "backtest"},
        )

        mock_pg.get_performance_batch.assert_called_once_with(
            impl_ids=["impl-1"], environment="backtest"
        )

    @pytest.mark.asyncio
    async def test_list_strategy_types(self, mock_pg):
        """Test list_strategy_types tool."""
        mock_pg.list_strategy_types.return_value = ["macd", "rsi"]

        result = await call_tool("list_strategy_types", {})

        data = json.loads(result[0].text)
        assert data == ["macd", "rsi"]

    @pytest.mark.asyncio
    async def test_create_spec(self, mock_pg):
        """Test create_spec tool."""
        mock_pg.create_spec.return_value = {"spec_id": "new-uuid"}

        args = {
            "name": "test_spec",
            "indicators": {"rsi": {"period": 14}},
            "entry_conditions": {"rsi_below": 30},
            "exit_conditions": {"rsi_above": 70},
            "parameters": {"period": {"min": 5, "max": 30}},
            "description": "A test strategy",
        }

        result = await call_tool("create_spec", args)

        data = json.loads(result[0].text)
        assert data["spec_id"] == "new-uuid"
        mock_pg.create_spec.assert_called_once_with(
            name="test_spec",
            indicators={"rsi": {"period": 14}},
            entry_conditions={"rsi_below": 30},
            exit_conditions={"rsi_above": 70},
            parameters={"period": {"min": 5, "max": 30}},
            description="A test strategy",
        )

    @pytest.mark.asyncio
    async def test_get_walk_forward(self, mock_pg):
        """Test get_walk_forward tool."""
        mock_pg.get_walk_forward.return_value = {
            "validation_status": "APPROVED",
            "sharpe_degradation": 0.15,
            "in_sample_sharpe": 2.0,
            "out_of_sample_sharpe": 1.7,
            "window_results": [],
        }

        result = await call_tool("get_walk_forward", {"impl_id": "abc-123"})

        data = json.loads(result[0].text)
        assert data["validation_status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_get_walk_forward_not_found(self, mock_pg):
        """Test get_walk_forward when results don't exist."""
        mock_pg.get_walk_forward.return_value = None

        result = await call_tool("get_walk_forward", {"impl_id": "nonexistent"})

        data = json.loads(result[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_unknown_tool(self, mock_pg):
        """Test calling an unknown tool."""
        result = await call_tool("unknown_tool", {})

        data = json.loads(result[0].text)
        assert "error" in data
        assert "Unknown tool" in data["error"]
