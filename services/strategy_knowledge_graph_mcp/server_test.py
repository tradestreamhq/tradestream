"""
Tests for the Strategy Knowledge Graph MCP server.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.strategy_knowledge_graph_mcp.server import create_server


class TestStrategyKnowledgeGraphServer:
    """Test cases for the strategy knowledge graph MCP server tools."""

    @pytest.fixture
    def postgres_client(self):
        """Create a mock PostgreSQL client."""
        return AsyncMock()

    @pytest.fixture
    def server(self, postgres_client):
        """Create a strategy knowledge graph MCP server instance."""
        return create_server(postgres_client)

    @pytest.mark.asyncio
    async def test_list_tools(self, server):
        """Test that all 10 tools are listed."""
        handlers = server.request_handlers
        list_tools_handler = handlers.get("tools/list")
        assert list_tools_handler is not None

        result = await list_tools_handler(MagicMock())
        assert len(result.tools) == 10

        tool_names = [t.name for t in result.tools]
        assert "get_indicator_relationships" in tool_names
        assert "get_complementary_indicators" in tool_names
        assert "get_market_conditions" in tool_names
        assert "recommend_strategies" in tool_names
        assert "create_composite_strategy" in tool_names
        assert "get_composite_strategy" in tool_names
        assert "list_composite_strategies" in tool_names
        assert "get_performance_attribution" in tool_names
        assert "explore_strategy_graph" in tool_names
        assert "find_similar_strategies" in tool_names

    @pytest.mark.asyncio
    async def test_get_indicator_relationships(self, server, postgres_client):
        """Test get_indicator_relationships tool."""
        postgres_client.get_indicator_relationships.return_value = {
            "items": [
                {
                    "indicator_a": "RSI",
                    "category_a": "momentum",
                    "indicator_b": "MACD",
                    "category_b": "momentum",
                    "relationship_type": "complementary",
                    "strength": 0.8,
                    "reasoning": "RSI + MACD provides confirmation",
                }
            ],
            "count": 1,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_indicator_relationships"
        request.params.arguments = {"indicator_name": "RSI"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "data" in response
        assert "_metadata" in response
        assert len(response["data"]["items"]) == 1
        assert response["data"]["items"][0]["indicator_a"] == "RSI"
        assert response["data"]["items"][0]["strength"] == 0.8
        assert response["_metadata"]["source"] == "postgresql"

    @pytest.mark.asyncio
    async def test_get_indicator_relationships_with_type_filter(self, server, postgres_client):
        """Test get_indicator_relationships with relationship type filter."""
        postgres_client.get_indicator_relationships.return_value = {
            "items": [],
            "count": 0,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_indicator_relationships"
        request.params.arguments = {"relationship_type": "redundant", "limit": 10}

        await call_tool_handler(request)

        postgres_client.get_indicator_relationships.assert_called_once_with(
            indicator_name=None,
            relationship_type="redundant",
            limit=10,
        )

    @pytest.mark.asyncio
    async def test_get_complementary_indicators(self, server, postgres_client):
        """Test get_complementary_indicators tool."""
        postgres_client.get_complementary_indicators.return_value = {
            "indicator": "RSI",
            "complementary": [
                {
                    "indicator": "MACD",
                    "category": "momentum",
                    "strength": 0.8,
                    "reasoning": "RSI momentum confirmed by MACD trend",
                },
                {
                    "indicator": "BOLLINGER",
                    "category": "volatility",
                    "strength": 0.85,
                    "reasoning": "Bollinger squeezes with RSI divergence",
                },
            ],
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_complementary_indicators"
        request.params.arguments = {"indicator_name": "RSI"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["data"]["indicator"] == "RSI"
        assert len(response["data"]["complementary"]) == 2
        assert response["data"]["complementary"][0]["indicator"] == "MACD"

    @pytest.mark.asyncio
    async def test_get_market_conditions(self, server, postgres_client):
        """Test get_market_conditions tool."""
        postgres_client.get_market_conditions.return_value = {
            "items": [
                {
                    "condition_id": "cond-001",
                    "trend": "trending_up",
                    "volatility": "medium",
                    "volume": "high",
                    "sentiment": "bullish",
                    "description": "Steady uptrend with strong volume",
                }
            ],
            "count": 1,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_market_conditions"
        request.params.arguments = {"trend": "trending_up"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert len(response["data"]["items"]) == 1
        assert response["data"]["items"][0]["trend"] == "trending_up"

    @pytest.mark.asyncio
    async def test_recommend_strategies(self, server, postgres_client):
        """Test recommend_strategies tool."""
        postgres_client.recommend_strategies.return_value = {
            "market_condition": {
                "trend": "trending_up",
                "volatility": "medium",
                "volume": "high",
                "description": "Steady uptrend with strong volume",
            },
            "recommendations": [
                {
                    "spec_id": "spec-001",
                    "spec_name": "MACD_TREND_FOLLOW",
                    "description": "MACD trend following",
                    "indicators": [{"type": "MACD"}],
                    "instrument": "BTC/USD",
                    "performance": {
                        "sample_size": 150,
                        "win_rate": 0.62,
                        "avg_return": 0.035,
                        "sharpe_ratio": 1.8,
                        "max_drawdown": -0.12,
                    },
                }
            ],
            "count": 1,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "recommend_strategies"
        request.params.arguments = {
            "trend": "trending_up",
            "volatility": "medium",
            "volume": "high",
        }

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["data"]["market_condition"]["trend"] == "trending_up"
        assert len(response["data"]["recommendations"]) == 1
        assert response["data"]["recommendations"][0]["spec_name"] == "MACD_TREND_FOLLOW"
        assert response["data"]["recommendations"][0]["performance"]["sharpe_ratio"] == 1.8

    @pytest.mark.asyncio
    async def test_create_composite_strategy(self, server, postgres_client):
        """Test create_composite_strategy tool."""
        postgres_client.create_composite_strategy.return_value = {
            "composite_id": "comp-001",
            "created": True,
            "components_count": 3,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "create_composite_strategy"
        request.params.arguments = {
            "name": "momentum_ensemble",
            "description": "Ensemble of momentum strategies",
            "component_spec_ids": ["spec-001", "spec-002", "spec-003"],
            "weights": [0.5, 0.3, 0.2],
            "combination_method": "weighted_average",
        }

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["data"]["created"] is True
        assert response["data"]["composite_id"] == "comp-001"
        assert response["data"]["components_count"] == 3

    @pytest.mark.asyncio
    async def test_create_composite_strategy_duplicate(self, server, postgres_client):
        """Test create_composite_strategy with duplicate name."""
        postgres_client.create_composite_strategy.return_value = {
            "composite_id": "comp-existing",
            "created": False,
            "error": "Composite strategy 'existing' already exists",
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "create_composite_strategy"
        request.params.arguments = {
            "name": "existing",
            "description": "test",
            "component_spec_ids": ["spec-001"],
        }

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["data"]["created"] is False

    @pytest.mark.asyncio
    async def test_get_composite_strategy(self, server, postgres_client):
        """Test get_composite_strategy tool."""
        postgres_client.get_composite_strategy.return_value = {
            "composite_id": "comp-001",
            "name": "momentum_ensemble",
            "description": "Ensemble of momentum strategies",
            "combination_method": "weighted_average",
            "min_agreement": 0.5,
            "is_active": True,
            "components": [
                {
                    "spec_id": "spec-001",
                    "spec_name": "RSI_REVERSAL",
                    "indicators": [{"type": "RSI"}],
                    "weight": 0.5,
                    "role": "signal",
                },
                {
                    "spec_id": "spec-002",
                    "spec_name": "MACD_CROSS",
                    "indicators": [{"type": "MACD"}],
                    "weight": 0.5,
                    "role": "confirmation",
                },
            ],
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_composite_strategy"
        request.params.arguments = {"composite_id": "comp-001"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["data"]["name"] == "momentum_ensemble"
        assert len(response["data"]["components"]) == 2

    @pytest.mark.asyncio
    async def test_get_composite_strategy_not_found(self, server, postgres_client):
        """Test get_composite_strategy when not found."""
        postgres_client.get_composite_strategy.return_value = None

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_composite_strategy"
        request.params.arguments = {"composite_id": "nonexistent"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "error" in response

    @pytest.mark.asyncio
    async def test_list_composite_strategies(self, server, postgres_client):
        """Test list_composite_strategies tool."""
        postgres_client.list_composite_strategies.return_value = {
            "items": [
                {
                    "composite_id": "comp-001",
                    "name": "momentum_ensemble",
                    "description": "Ensemble of momentum strategies",
                    "combination_method": "weighted_average",
                    "is_active": True,
                    "components_count": 3,
                }
            ],
            "count": 1,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "list_composite_strategies"
        request.params.arguments = {}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert len(response["data"]["items"]) == 1
        assert response["data"]["items"][0]["components_count"] == 3

    @pytest.mark.asyncio
    async def test_get_performance_attribution(self, server, postgres_client):
        """Test get_performance_attribution tool."""
        postgres_client.get_performance_attribution.return_value = {
            "composite_id": "comp-001",
            "attributions": [
                {
                    "component_name": "RSI_REVERSAL",
                    "component_spec_id": "spec-001",
                    "instrument": "BTC/USD",
                    "total_signals": 100,
                    "total_agreed": 75,
                    "total_pnl": 1250.50,
                    "avg_contribution_pct": 0.45,
                    "avg_accuracy": 0.62,
                },
                {
                    "component_name": "MACD_CROSS",
                    "component_spec_id": "spec-002",
                    "instrument": "BTC/USD",
                    "total_signals": 85,
                    "total_agreed": 60,
                    "total_pnl": 980.25,
                    "avg_contribution_pct": 0.35,
                    "avg_accuracy": 0.58,
                },
            ],
            "count": 2,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_performance_attribution"
        request.params.arguments = {"composite_id": "comp-001"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert len(response["data"]["attributions"]) == 2
        assert response["data"]["attributions"][0]["component_name"] == "RSI_REVERSAL"
        assert response["data"]["attributions"][0]["total_pnl"] == 1250.50
        assert response["data"]["attributions"][0]["avg_contribution_pct"] == 0.45

    @pytest.mark.asyncio
    async def test_explore_strategy_graph(self, server, postgres_client):
        """Test explore_strategy_graph tool."""
        postgres_client.explore_strategy_graph.return_value = {
            "spec_id": "spec-001",
            "name": "RSI_REVERSAL",
            "description": "RSI-based mean reversion",
            "indicators": [{"type": "RSI", "params": {"period": 14}}],
            "entry_conditions": [{"type": "UNDER_CONSTANT", "indicator": "rsi", "value": 30}],
            "exit_conditions": [{"type": "OVER_CONSTANT", "indicator": "rsi", "value": 70}],
            "tags": ["mean_reversion", "momentum", "oscillator"],
            "composites": [
                {
                    "composite_id": "comp-001",
                    "composite_name": "momentum_ensemble",
                    "weight": 0.5,
                    "role": "signal",
                }
            ],
            "best_conditions": [
                {
                    "trend": "ranging",
                    "volatility": "medium",
                    "volume": "medium",
                    "sentiment": "neutral",
                    "sharpe_ratio": 2.1,
                    "win_rate": 0.65,
                    "sample_size": 200,
                    "instrument": "BTC/USD",
                }
            ],
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "explore_strategy_graph"
        request.params.arguments = {"spec_id": "spec-001"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["data"]["name"] == "RSI_REVERSAL"
        assert len(response["data"]["tags"]) == 3
        assert len(response["data"]["composites"]) == 1
        assert len(response["data"]["best_conditions"]) == 1
        assert response["data"]["best_conditions"][0]["sharpe_ratio"] == 2.1

    @pytest.mark.asyncio
    async def test_explore_strategy_graph_not_found(self, server, postgres_client):
        """Test explore_strategy_graph when spec not found."""
        postgres_client.explore_strategy_graph.return_value = None

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "explore_strategy_graph"
        request.params.arguments = {"spec_id": "nonexistent"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "error" in response

    @pytest.mark.asyncio
    async def test_find_similar_strategies(self, server, postgres_client):
        """Test find_similar_strategies tool."""
        postgres_client.find_similar_strategies.return_value = {
            "source_spec_id": "spec-001",
            "similar": [
                {
                    "spec_id": "spec-005",
                    "name": "STOCHASTIC_REVERSAL",
                    "description": "Stochastic-based mean reversion",
                    "indicators": [{"type": "STOCHASTIC"}],
                    "tag_overlap": 2,
                    "indicator_overlap": 0,
                    "similarity_score": 2,
                }
            ],
            "count": 1,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "find_similar_strategies"
        request.params.arguments = {"spec_id": "spec-001"}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert response["data"]["source_spec_id"] == "spec-001"
        assert len(response["data"]["similar"]) == 1
        assert response["data"]["similar"][0]["name"] == "STOCHASTIC_REVERSAL"

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

    @pytest.mark.asyncio
    async def test_database_error_handling(self, server, postgres_client):
        """Test that database errors are properly caught and returned."""
        postgres_client.get_indicator_relationships.side_effect = Exception("Connection lost")

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_indicator_relationships"
        request.params.arguments = {}

        result = await call_tool_handler(request)
        response = json.loads(result.content[0].text)

        assert "error" in response
        assert "_metadata" in response

    @pytest.mark.asyncio
    async def test_caching_behavior(self, server, postgres_client):
        """Test that repeated calls use cache."""
        postgres_client.get_market_conditions.return_value = {
            "items": [{"condition_id": "cond-001", "trend": "ranging", "volatility": "low", "volume": "low", "sentiment": "neutral", "description": "Consolidation"}],
            "count": 1,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_market_conditions"
        request.params.arguments = {"trend": "ranging"}

        # First call
        result1 = await call_tool_handler(request)
        resp1 = json.loads(result1.content[0].text)
        assert resp1["_metadata"]["cached"] is False

        # Second call should be cached
        result2 = await call_tool_handler(request)
        resp2 = json.loads(result2.content[0].text)
        assert resp2["_metadata"]["cached"] is True

        # Only one actual DB call
        assert postgres_client.get_market_conditions.call_count == 1

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(self, server, postgres_client):
        """Test that force_refresh bypasses cache."""
        postgres_client.get_indicator_relationships.return_value = {
            "items": [],
            "count": 0,
        }

        call_tool_handler = server.request_handlers.get("tools/call")
        request = MagicMock()
        request.params.name = "get_indicator_relationships"
        request.params.arguments = {"force_refresh": True}

        # First call
        await call_tool_handler(request)
        # Second call with force_refresh
        await call_tool_handler(request)

        assert postgres_client.get_indicator_relationships.call_count == 2
