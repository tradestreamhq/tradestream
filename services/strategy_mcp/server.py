"""
MCP server for strategy queries.
Exposes tools for querying strategy specs, implementations, and performance data.
"""

import json
import logging
import time
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.shared.mcp_cache import TtlCache
from services.shared.mcp_errors import (
    McpError,
    STRATEGY_NOT_FOUND,
    NO_SIGNAL,
    DATABASE_ERROR,
)
from services.shared.mcp_metadata import wrap_response, wrap_error
from services.strategy_mcp.postgres_client import PostgresClient

server = Server("strategy-mcp")
_cache = TtlCache(default_ttl=30.0)

_CACHE_TTLS = {
    "get_top_strategies": 30.0,
    "get_strategy_signal": 10.0,
    "get_strategy_consensus": 30.0,
}


def _set_postgres_client(client: PostgresClient) -> None:
    """Set the postgres client on the server instance."""
    server._postgres_client = client


def _get_postgres_client() -> PostgresClient:
    """Get the postgres client from the server instance."""
    return server._postgres_client


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="get_top_strategies",
            description="Get top-performing strategies by Sharpe ratio for a symbol",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol (e.g. BTC/USD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return",
                        "default": 10,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of strategies to skip for pagination",
                        "default": 0,
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["sharpe", "accuracy", "return"],
                        "default": "sharpe",
                        "description": "Ranking metric",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass cache and fetch fresh data",
                    },
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_spec",
            description="Get a strategy specification by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "spec_name": {
                        "type": "string",
                        "description": "Strategy spec name",
                    },
                },
                "required": ["spec_name"],
            },
        ),
        Tool(
            name="get_performance",
            description="Get performance metrics for a strategy implementation",
            inputSchema={
                "type": "object",
                "properties": {
                    "impl_id": {
                        "type": "string",
                        "description": "Strategy implementation UUID",
                    },
                    "environment": {
                        "type": "string",
                        "description": "Filter to specific environment",
                        "enum": ["backtest", "paper", "live"],
                    },
                },
                "required": ["impl_id"],
            },
        ),
        Tool(
            name="get_performance_batch",
            description="Get performance metrics for multiple strategy implementations",
            inputSchema={
                "type": "object",
                "properties": {
                    "impl_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of strategy implementation UUIDs",
                    },
                    "environment": {
                        "type": "string",
                        "description": "Filter to specific environment",
                        "enum": ["backtest", "paper", "live"],
                    },
                },
                "required": ["impl_ids"],
            },
        ),
        Tool(
            name="list_strategy_types",
            description="List distinct strategy types with validated or deployed implementations",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="create_spec",
            description="Create a new strategy specification",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique spec name"},
                    "indicators": {
                        "type": "object",
                        "description": "Indicator configurations",
                    },
                    "entry_conditions": {
                        "type": "object",
                        "description": "Entry rule definitions",
                    },
                    "exit_conditions": {
                        "type": "object",
                        "description": "Exit rule definitions",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parameter definitions with ranges",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description",
                    },
                },
                "required": [
                    "name",
                    "indicators",
                    "entry_conditions",
                    "exit_conditions",
                    "parameters",
                    "description",
                ],
            },
        ),
        Tool(
            name="get_walk_forward",
            description="Get walk-forward validation results for a strategy implementation",
            inputSchema={
                "type": "object",
                "properties": {
                    "impl_id": {
                        "type": "string",
                        "description": "Strategy implementation UUID",
                    },
                },
                "required": ["impl_id"],
            },
        ),
        Tool(
            name="get_strategy_signal",
            description="Get the current signal from a specific strategy for a symbol",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy_id": {
                        "type": "string",
                        "description": "Strategy identifier",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Trading pair e.g. ETH/USD",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass cache and fetch fresh data",
                    },
                },
                "required": ["strategy_id", "symbol"],
            },
        ),
        Tool(
            name="get_strategy_consensus",
            description="Get aggregated consensus across all active strategies for a symbol",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading pair e.g. ETH/USD",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass cache and fetch fresh data",
                    },
                },
                "required": ["symbol"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls with caching, structured errors, and response metadata."""
    start = time.monotonic()
    pg = _get_postgres_client()
    force_refresh = arguments.get("force_refresh", False)

    try:
        if name == "get_top_strategies":
            cache_key = f"top:{arguments['symbol']}:{arguments.get('limit', 10)}:{arguments.get('offset', 0)}:{arguments.get('metric', 'sharpe')}"
            if not force_refresh:
                cached = _cache.get(cache_key)
                if cached:
                    return wrap_response(
                        cached[0],
                        start_time=start,
                        cached=True,
                        cache_ttl_remaining=cached[1],
                        source="postgresql",
                    )
            result = await pg.get_top_strategies(
                symbol=arguments["symbol"],
                limit=arguments.get("limit", 10),
                min_score=arguments.get("min_score", 0.0),
            )
            _cache.set(cache_key, result, ttl=_CACHE_TTLS["get_top_strategies"])
            return wrap_response(result, start_time=start, source="postgresql")

        elif name == "get_spec":
            result = await pg.get_spec(spec_name=arguments["spec_name"])
            if result is None:
                return wrap_error(
                    McpError(
                        STRATEGY_NOT_FOUND,
                        f"Spec '{arguments['spec_name']}' not found",
                        details={"spec_name": arguments["spec_name"]},
                    ).to_dict(),
                    start_time=start,
                )
            return wrap_response(result, start_time=start, source="postgresql")

        elif name == "get_performance":
            result = await pg.get_performance(
                impl_id=arguments["impl_id"],
                environment=arguments.get("environment"),
            )
            if result is None:
                return wrap_error(
                    McpError(
                        STRATEGY_NOT_FOUND,
                        f"Implementation '{arguments['impl_id']}' not found",
                        details={"impl_id": arguments["impl_id"]},
                    ).to_dict(),
                    start_time=start,
                )
            return wrap_response(result, start_time=start, source="postgresql")

        elif name == "get_performance_batch":
            result = await pg.get_performance_batch(
                impl_ids=arguments["impl_ids"],
                environment=arguments.get("environment"),
            )
            return wrap_response(result, start_time=start, source="postgresql")

        elif name == "list_strategy_types":
            result = await pg.list_strategy_types()
            return wrap_response(result, start_time=start, source="postgresql")

        elif name == "create_spec":
            result = await pg.create_spec(
                name=arguments["name"],
                indicators=arguments["indicators"],
                entry_conditions=arguments["entry_conditions"],
                exit_conditions=arguments["exit_conditions"],
                parameters=arguments["parameters"],
                description=arguments["description"],
            )
            return wrap_response(result, start_time=start, source="postgresql")

        elif name == "get_walk_forward":
            result = await pg.get_walk_forward(impl_id=arguments["impl_id"])
            if result is None:
                return wrap_error(
                    McpError(
                        STRATEGY_NOT_FOUND,
                        "Walk-forward results not found",
                        details={"impl_id": arguments["impl_id"]},
                    ).to_dict(),
                    start_time=start,
                )
            return wrap_response(result, start_time=start, source="postgresql")

        elif name == "get_strategy_signal":
            cache_key = f"signal:{arguments['strategy_id']}:{arguments['symbol']}"
            if not force_refresh:
                cached = _cache.get(cache_key)
                if cached:
                    return wrap_response(
                        cached[0],
                        start_time=start,
                        cached=True,
                        cache_ttl_remaining=cached[1],
                        source="postgresql",
                    )
            result = await pg.get_strategy_signal(
                strategy_id=arguments["strategy_id"],
                symbol=arguments["symbol"],
            )
            if result is None:
                return wrap_error(
                    McpError(
                        NO_SIGNAL,
                        "No signal found for this strategy and symbol",
                        details={
                            "strategy_id": arguments["strategy_id"],
                            "symbol": arguments["symbol"],
                        },
                    ).to_dict(),
                    start_time=start,
                )
            _cache.set(cache_key, result, ttl=_CACHE_TTLS["get_strategy_signal"])
            return wrap_response(result, start_time=start, source="postgresql")

        elif name == "get_strategy_consensus":
            cache_key = f"consensus:{arguments['symbol']}"
            if not force_refresh:
                cached = _cache.get(cache_key)
                if cached:
                    return wrap_response(
                        cached[0],
                        start_time=start,
                        cached=True,
                        cache_ttl_remaining=cached[1],
                        source="postgresql",
                    )
            result = await pg.get_strategy_consensus(symbol=arguments["symbol"])
            _cache.set(cache_key, result, ttl=_CACHE_TTLS["get_strategy_consensus"])
            return wrap_response(result, start_time=start, source="postgresql")

        else:
            return wrap_error(
                McpError("UNKNOWN_TOOL", f"Unknown tool: {name}").to_dict(),
                start_time=start,
            )
    except Exception as e:
        logging.exception("Tool call %s failed", name)
        return wrap_error(McpError(DATABASE_ERROR, str(e)).to_dict(), start_time=start)
