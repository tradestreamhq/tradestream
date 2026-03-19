"""
MCP server for portfolio state queries.
Exposes tools for querying positions, balance, and validating trades.
"""

import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.portfolio_mcp.postgres_client import PostgresClient


def create_server(postgres_client: PostgresClient) -> Server:
    """Create and configure the portfolio MCP server with all tools."""
    server = Server("portfolio-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_positions",
                description="Get current open positions with optional symbol filter.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Optional filter by trading pair (e.g., BTC/USD)",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "maximum": 200,
                            "description": "Maximum number of positions to return.",
                        },
                        "offset": {
                            "type": "integer",
                            "default": 0,
                            "description": "Number of positions to skip for pagination.",
                        },
                    },
                },
            ),
            Tool(
                name="get_balance",
                description="Get account balance and available margin.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="validate_trade",
                description="Validate a proposed trade against risk rules.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading pair (e.g., BTC/USD)",
                        },
                        "side": {
                            "type": "string",
                            "enum": ["BUY", "SELL"],
                            "description": "Trade direction.",
                        },
                        "size": {
                            "type": "number",
                            "description": "Trade size in base currency.",
                        },
                        "price": {
                            "type": "number",
                            "description": "Optional limit price for validation.",
                        },
                    },
                    "required": ["symbol", "side", "size"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        if name == "get_positions":
            result = await postgres_client.get_positions(
                symbol=arguments.get("symbol"),
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
            )
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        elif name == "get_balance":
            result = await postgres_client.get_balance()
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        elif name == "validate_trade":
            result = await postgres_client.validate_trade(
                symbol=arguments["symbol"],
                side=arguments["side"],
                size=arguments["size"],
                price=arguments.get("price"),
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
