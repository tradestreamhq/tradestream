"""
MCP server for backtest execution and historical performance.
Exposes tools for running backtests and querying historical strategy performance.
"""

import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.backtest_mcp.postgres_client import PostgresClient


def create_server(postgres_client: PostgresClient) -> Server:
    """Create and configure the backtest MCP server with all tools."""
    server = Server("backtest-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="run_backtest",
                description="Run a backtest for a strategy configuration on a symbol.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": "Strategy implementation UUID.",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Trading pair (e.g., BTC/USD).",
                        },
                        "start_date": {
                            "type": "string",
                            "format": "date",
                            "description": "Backtest start date (YYYY-MM-DD). Optional.",
                        },
                        "end_date": {
                            "type": "string",
                            "format": "date",
                            "description": "Backtest end date (YYYY-MM-DD). Optional.",
                        },
                    },
                    "required": ["strategy_id", "symbol"],
                },
            ),
            Tool(
                name="get_historical_performance",
                description="Get historical performance metrics for a strategy implementation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": "Strategy implementation UUID.",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Optional trading pair filter.",
                        },
                        "period": {
                            "type": "string",
                            "enum": ["1w", "1m", "3m", "6m", "1y"],
                            "default": "3m",
                            "description": "Lookback period.",
                        },
                    },
                    "required": ["strategy_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        if name == "run_backtest":
            result = await postgres_client.run_backtest(
                strategy_id=arguments["strategy_id"],
                symbol=arguments["symbol"],
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
            )
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        elif name == "get_historical_performance":
            result = await postgres_client.get_historical_performance(
                strategy_id=arguments["strategy_id"],
                symbol=arguments.get("symbol"),
                period=arguments.get("period", "3m"),
            )
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": f"Unknown tool: {name}"}),
                )
            ]

    return server
