"""
MCP server for strategy queries.
Exposes tools for querying strategy specs, implementations, and performance data.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.strategy_mcp.postgres_client import PostgresClient

server = Server("strategy-mcp")


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
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum Sharpe ratio",
                        "default": 0.0,
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
                        "description": "Filter to specific environment (backtest, paper, live)",
                        "enum": ["backtest", "paper", "live"],
                    },
                },
                "required": ["impl_id"],
            },
        ),
        Tool(
            name="list_strategy_types",
            description="List distinct strategy types with validated or deployed implementations",
            inputSchema={
                "type": "object",
                "properties": {},
            },
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
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    pg = _get_postgres_client()

    if name == "get_top_strategies":
        result = await pg.get_top_strategies(
            symbol=arguments["symbol"],
            limit=arguments.get("limit", 10),
            min_score=arguments.get("min_score", 0.0),
        )
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    elif name == "get_spec":
        result = await pg.get_spec(spec_name=arguments["spec_name"])
        if result is None:
            return [
                TextContent(type="text", text=json.dumps({"error": "Spec not found"}))
            ]
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    elif name == "get_performance":
        result = await pg.get_performance(
            impl_id=arguments["impl_id"],
            environment=arguments.get("environment"),
        )
        if result is None:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": "Implementation not found"})
                )
            ]
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    elif name == "list_strategy_types":
        result = await pg.list_strategy_types()
        return [TextContent(type="text", text=json.dumps(result))]

    elif name == "create_spec":
        result = await pg.create_spec(
            name=arguments["name"],
            indicators=arguments["indicators"],
            entry_conditions=arguments["entry_conditions"],
            exit_conditions=arguments["exit_conditions"],
            parameters=arguments["parameters"],
            description=arguments["description"],
        )
        return [TextContent(type="text", text=json.dumps(result))]

    elif name == "get_walk_forward":
        result = await pg.get_walk_forward(impl_id=arguments["impl_id"])
        if result is None:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": "Walk-forward results not found"}),
                )
            ]
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    else:
        return [
            TextContent(
                type="text", text=json.dumps({"error": f"Unknown tool: {name}"})
            )
        ]
