"""
MCP server for the Strategy Knowledge Graph.
Exposes tools for indicator relationships, market condition mappings,
strategy recommendations, composite strategies, and graph exploration.
"""

import json
import logging
import time
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.shared.mcp_cache import TtlCache
from services.shared.mcp_errors import (
    McpError,
    SPEC_NOT_FOUND,
    DATABASE_ERROR,
)
from services.shared.mcp_metadata import wrap_response, wrap_error
from services.strategy_knowledge_graph_mcp.postgres_client import PostgresClient

_CACHE_TTLS = {
    "indicator_relationships": 300.0,
    "market_conditions": 300.0,
    "recommend_strategies": 60.0,
    "composite_strategies": 120.0,
    "explore_graph": 60.0,
}


def create_server(postgres_client: PostgresClient) -> Server:
    """Create and configure the strategy knowledge graph MCP server."""
    server = Server("strategy-knowledge-graph-mcp")
    cache = TtlCache(default_ttl=120.0)

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_indicator_relationships",
                description="Get relationships between technical indicators (complementary, conflicting, redundant, confirming).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "indicator_name": {
                            "type": "string",
                            "description": "Filter by indicator name (e.g. RSI, MACD, SMA).",
                        },
                        "relationship_type": {
                            "type": "string",
                            "enum": ["complementary", "conflicting", "redundant", "confirming"],
                            "description": "Filter by relationship type.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "maximum": 100,
                            "description": "Maximum relationships to return.",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache.",
                        },
                    },
                },
            ),
            Tool(
                name="get_complementary_indicators",
                description="Find indicators that complement a given indicator for building effective strategy combinations.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "indicator_name": {
                            "type": "string",
                            "description": "The indicator to find complements for (e.g. RSI).",
                        },
                        "min_strength": {
                            "type": "number",
                            "default": 0.5,
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Minimum relationship strength (0-1).",
                        },
                    },
                    "required": ["indicator_name"],
                },
            ),
            Tool(
                name="get_market_conditions",
                description="Browse the market condition taxonomy: trending/ranging × high/low volatility × volume levels.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trend": {
                            "type": "string",
                            "enum": ["trending_up", "trending_down", "ranging"],
                            "description": "Market trend direction.",
                        },
                        "volatility": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Volatility level.",
                        },
                        "volume": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Volume level.",
                        },
                    },
                },
            ),
            Tool(
                name="recommend_strategies",
                description="Recommend optimal strategies for given market conditions based on historical performance by regime.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "trend": {
                            "type": "string",
                            "enum": ["trending_up", "trending_down", "ranging"],
                            "description": "Current market trend.",
                        },
                        "volatility": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Current volatility level.",
                        },
                        "volume": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Current volume level.",
                        },
                        "instrument": {
                            "type": "string",
                            "description": "Optional instrument filter (e.g. BTC/USD).",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "maximum": 50,
                            "description": "Max recommendations to return.",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache.",
                        },
                    },
                    "required": ["trend", "volatility", "volume"],
                },
            ),
            Tool(
                name="create_composite_strategy",
                description="Create an ensemble strategy by combining multiple simple strategies with weights and a combination method.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Unique name for the composite strategy.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the ensemble approach.",
                        },
                        "component_spec_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of strategy spec UUIDs to combine.",
                        },
                        "weights": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Optional weights for each component (must match spec_ids length).",
                        },
                        "combination_method": {
                            "type": "string",
                            "enum": ["majority_vote", "weighted_average", "unanimous", "any"],
                            "default": "weighted_average",
                            "description": "How to combine component signals.",
                        },
                        "min_agreement": {
                            "type": "number",
                            "default": 0.5,
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Minimum agreement threshold.",
                        },
                    },
                    "required": ["name", "description", "component_spec_ids"],
                },
            ),
            Tool(
                name="get_composite_strategy",
                description="Get a composite strategy with its components and weights.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "composite_id": {
                            "type": "string",
                            "description": "Composite strategy UUID.",
                        },
                    },
                    "required": ["composite_id"],
                },
            ),
            Tool(
                name="list_composite_strategies",
                description="List all composite (ensemble) strategies.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "active_only": {
                            "type": "boolean",
                            "default": True,
                            "description": "Only show active composites.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "maximum": 100,
                            "description": "Max composites to return.",
                        },
                    },
                },
            ),
            Tool(
                name="get_performance_attribution",
                description="Get performance attribution showing how each component of a composite strategy contributed to returns.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "composite_id": {
                            "type": "string",
                            "description": "Composite strategy UUID.",
                        },
                        "instrument": {
                            "type": "string",
                            "description": "Optional instrument filter.",
                        },
                    },
                    "required": ["composite_id"],
                },
            ),
            Tool(
                name="explore_strategy_graph",
                description="Explore the knowledge graph around a strategy: its indicators, tags, composites it belongs to, and best market conditions.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "spec_id": {
                            "type": "string",
                            "description": "Strategy spec UUID to explore.",
                        },
                    },
                    "required": ["spec_id"],
                },
            ),
            Tool(
                name="find_similar_strategies",
                description="Find strategies similar to a given one based on shared indicators and tags.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "spec_id": {
                            "type": "string",
                            "description": "Strategy spec UUID to find similar strategies for.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "maximum": 50,
                            "description": "Max similar strategies to return.",
                        },
                    },
                    "required": ["spec_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        start = time.monotonic()
        force_refresh = arguments.get("force_refresh", False)

        try:
            if name == "get_indicator_relationships":
                cache_key = f"ir:{arguments.get('indicator_name', '')}:{arguments.get('relationship_type', '')}:{arguments.get('limit', 50)}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(cached[0], start_time=start, cached=True, cache_ttl_remaining=cached[1], source="postgresql")
                result = await postgres_client.get_indicator_relationships(
                    indicator_name=arguments.get("indicator_name"),
                    relationship_type=arguments.get("relationship_type"),
                    limit=arguments.get("limit", 50),
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["indicator_relationships"])
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "get_complementary_indicators":
                cache_key = f"ci:{arguments['indicator_name']}:{arguments.get('min_strength', 0.5)}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(cached[0], start_time=start, cached=True, cache_ttl_remaining=cached[1], source="postgresql")
                result = await postgres_client.get_complementary_indicators(
                    indicator_name=arguments["indicator_name"],
                    min_strength=arguments.get("min_strength", 0.5),
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["indicator_relationships"])
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "get_market_conditions":
                cache_key = f"mc:{arguments.get('trend', '')}:{arguments.get('volatility', '')}:{arguments.get('volume', '')}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(cached[0], start_time=start, cached=True, cache_ttl_remaining=cached[1], source="postgresql")
                result = await postgres_client.get_market_conditions(
                    trend=arguments.get("trend"),
                    volatility=arguments.get("volatility"),
                    volume=arguments.get("volume"),
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["market_conditions"])
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "recommend_strategies":
                cache_key = f"rs:{arguments['trend']}:{arguments['volatility']}:{arguments['volume']}:{arguments.get('instrument', '')}:{arguments.get('limit', 10)}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(cached[0], start_time=start, cached=True, cache_ttl_remaining=cached[1], source="postgresql")
                result = await postgres_client.recommend_strategies(
                    trend=arguments["trend"],
                    volatility=arguments["volatility"],
                    volume=arguments["volume"],
                    instrument=arguments.get("instrument"),
                    limit=arguments.get("limit", 10),
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["recommend_strategies"])
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "create_composite_strategy":
                result = await postgres_client.create_composite_strategy(
                    name=arguments["name"],
                    description=arguments["description"],
                    component_spec_ids=arguments["component_spec_ids"],
                    weights=arguments.get("weights"),
                    combination_method=arguments.get("combination_method", "weighted_average"),
                    min_agreement=arguments.get("min_agreement", 0.5),
                )
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "get_composite_strategy":
                cache_key = f"gcs:{arguments['composite_id']}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(cached[0], start_time=start, cached=True, cache_ttl_remaining=cached[1], source="postgresql")
                result = await postgres_client.get_composite_strategy(
                    composite_id=arguments["composite_id"],
                )
                if result is None:
                    return wrap_error(
                        McpError(SPEC_NOT_FOUND, f"Composite strategy {arguments['composite_id']} not found").to_dict(),
                        start_time=start,
                    )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["composite_strategies"])
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "list_composite_strategies":
                result = await postgres_client.list_composite_strategies(
                    active_only=arguments.get("active_only", True),
                    limit=arguments.get("limit", 20),
                )
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "get_performance_attribution":
                result = await postgres_client.get_performance_attribution(
                    composite_id=arguments["composite_id"],
                    instrument=arguments.get("instrument"),
                )
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "explore_strategy_graph":
                cache_key = f"esg:{arguments['spec_id']}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(cached[0], start_time=start, cached=True, cache_ttl_remaining=cached[1], source="postgresql")
                result = await postgres_client.explore_strategy_graph(
                    spec_id=arguments["spec_id"],
                )
                if result is None:
                    return wrap_error(
                        McpError(SPEC_NOT_FOUND, f"Strategy spec {arguments['spec_id']} not found").to_dict(),
                        start_time=start,
                    )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["explore_graph"])
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "find_similar_strategies":
                cache_key = f"fss:{arguments['spec_id']}:{arguments.get('limit', 10)}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(cached[0], start_time=start, cached=True, cache_ttl_remaining=cached[1], source="postgresql")
                result = await postgres_client.find_similar_strategies(
                    spec_id=arguments["spec_id"],
                    limit=arguments.get("limit", 10),
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["explore_graph"])
                return wrap_response(result, start_time=start, source="postgresql")

            else:
                return wrap_error(
                    McpError("UNKNOWN_TOOL", f"Unknown tool: {name}").to_dict(),
                    start_time=start,
                )
        except Exception as e:
            logging.exception("Tool call %s failed", name)
            return wrap_error(
                McpError(DATABASE_ERROR, str(e)).to_dict(), start_time=start
            )

    return server
