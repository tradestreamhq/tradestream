"""
MCP server for agent decision history.
Exposes tools for querying and saving agent decisions.
"""

import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.decisions_mcp.postgres_client import PostgresClient


def create_server(postgres_client: PostgresClient) -> Server:
    """Create and configure the decisions MCP server with all tools."""
    server = Server("decisions-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_recent_decisions",
                description="Get recent agent decisions for a symbol with optional action filter.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Optional filter by trading pair.",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["BUY", "SELL", "HOLD"],
                            "description": "Optional filter by decision action.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "maximum": 100,
                            "description": "Maximum decisions to return.",
                        },
                        "offset": {
                            "type": "integer",
                            "default": 0,
                            "description": "Number of decisions to skip for pagination.",
                        },
                    },
                },
            ),
            Tool(
                name="save_decision",
                description="Save an agent decision to the database for auditing and learning.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading pair (e.g., BTC/USD).",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["BUY", "SELL", "HOLD"],
                            "description": "The decision action.",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence score between 0 and 1.",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Explanation of the decision rationale.",
                        },
                        "opportunity_score": {
                            "type": "number",
                            "description": "Optional opportunity score.",
                        },
                        "tool_calls": {
                            "type": "array",
                            "description": "Optional list of tool calls that informed this decision.",
                        },
                    },
                    "required": ["symbol", "action", "confidence", "reasoning"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        if name == "get_recent_decisions":
            result = await postgres_client.get_recent_decisions(
                symbol=arguments.get("symbol"),
                action=arguments.get("action"),
                limit=arguments.get("limit", 10),
                offset=arguments.get("offset", 0),
            )
            return [TextContent(type="text", text=json.dumps(result, default=str))]

        elif name == "save_decision":
            result = await postgres_client.save_decision(
                symbol=arguments["symbol"],
                action=arguments["action"],
                confidence=arguments["confidence"],
                reasoning=arguments["reasoning"],
                opportunity_score=arguments.get("opportunity_score"),
                tool_calls=arguments.get("tool_calls"),
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
