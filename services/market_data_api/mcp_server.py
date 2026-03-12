"""
MCP wrapper for the Market Data REST API.
"""

import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.rest_api_shared.mcp_wrapper import MCPAPIWrapper

logger = logging.getLogger(__name__)


def create_server(api_base_url: str) -> Server:
    """Create an MCP server wrapping the Market Data REST API."""
    wrapper = MCPAPIWrapper(api_base_url)
    server = Server("market-data-api-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="list_instruments",
                description="List available trading instruments",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_candles",
                description="Get OHLCV candle data for an instrument",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading instrument (e.g., BTC/USD)",
                        },
                        "interval": {
                            "type": "string",
                            "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                            "description": "Candle interval",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 100,
                            "description": "Max candles to return",
                        },
                        "from": {
                            "type": "string",
                            "description": "Start time (RFC3339 or relative)",
                        },
                    },
                    "required": ["symbol", "interval"],
                },
            ),
            Tool(
                name="get_price",
                description="Get current price for an instrument",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading instrument (e.g., BTC/USD)",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            Tool(
                name="get_orderbook",
                description="Get order book for an instrument",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading instrument",
                        },
                        "depth": {
                            "type": "integer",
                            "default": 10,
                            "description": "Order book depth",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "list_instruments":
                result = wrapper._get("/instruments")
                return wrapper._text(result)

            elif name == "get_candles":
                params = {
                    "interval": arguments["interval"],
                    "limit": arguments.get("limit", 100),
                }
                if arguments.get("from"):
                    params["from"] = arguments["from"]
                result = wrapper._get(
                    f"/instruments/{arguments['symbol']}/candles", params=params
                )
                return wrapper._text(result)

            elif name == "get_price":
                result = wrapper._get(f"/instruments/{arguments['symbol']}/price")
                return wrapper._text(result)

            elif name == "get_orderbook":
                params = {"depth": arguments.get("depth", 10)}
                result = wrapper._get(
                    f"/instruments/{arguments['symbol']}/orderbook", params=params
                )
                return wrapper._text(result)

            else:
                return wrapper._error_text(f"Unknown tool: {name}")

        except Exception as e:
            logger.error("Market Data MCP tool '%s' failed: %s", name, e)
            return wrapper._error_text(str(e))

    return server
