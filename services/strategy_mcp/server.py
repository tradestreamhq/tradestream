"""
MCP server for strategy queries.
Exposes tools for querying strategy specs, implementations, and performance data.
"""

import json
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.strategy_mcp.postgres_client import PostgresClient


def create_server(postgres_client: PostgresClient) -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("strategy-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
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
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        if name == "get_top_strategies":
            result = await postgres_client.get_top_strategies(
                symbol=arguments["symbol"],
                limit=arguments.get("limit", 10),
                min_score=arguments.get("min_score", 0.0),
            )
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        elif name == "get_spec":
            result = await postgres_client.get_spec(spec_name=arguments["spec_name"])
            if result is None:
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": "Spec not found"})
                    )
                ]
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        elif name == "get_performance":
            result = await postgres_client.get_performance(
                impl_id=arguments["impl_id"],
                environment=arguments.get("environment"),
            )
            if result is None:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Implementation not found"}),
                    )
                ]
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        elif name == "list_strategy_types":
            result = await postgres_client.list_strategy_types()
            return [TextContent(type="text", text=json.dumps(result))]

        elif name == "create_spec":
            result = await postgres_client.create_spec(
                name=arguments["name"],
                indicators=arguments["indicators"],
                entry_conditions=arguments["entry_conditions"],
                exit_conditions=arguments["exit_conditions"],
                parameters=arguments["parameters"],
                description=arguments["description"],
            )
            return [TextContent(type="text", text=json.dumps(result))]

        elif name == "get_walk_forward":
            result = await postgres_client.get_walk_forward(
                impl_id=arguments["impl_id"]
            )
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

    return server
