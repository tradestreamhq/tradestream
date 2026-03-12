"""
MCP wrapper for the Portfolio REST API.
"""

import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.rest_api_shared.mcp_wrapper import MCPAPIWrapper

logger = logging.getLogger(__name__)


def create_server(api_base_url: str) -> Server:
    """Create an MCP server wrapping the Portfolio REST API."""
    wrapper = MCPAPIWrapper(api_base_url)
    server = Server("portfolio-api-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_portfolio_state",
                description="Get current portfolio state with all positions and trade stats",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_positions",
                description="List all open positions",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_position",
                description="Get position for a specific instrument",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instrument": {
                            "type": "string",
                            "description": "Trading instrument symbol",
                        },
                    },
                    "required": ["instrument"],
                },
            ),
            Tool(
                name="get_balance",
                description="Get account balance with realized and unrealized P&L",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_risk",
                description="Get risk metrics including exposure and concentration",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="validate_trade",
                description="Validate a proposed trade against risk limits",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instrument": {
                            "type": "string",
                            "description": "Trading instrument symbol",
                        },
                        "side": {
                            "type": "string",
                            "enum": ["BUY", "SELL"],
                            "description": "Trade direction",
                        },
                        "size": {
                            "type": "number",
                            "description": "Trade size",
                        },
                    },
                    "required": ["instrument", "side", "size"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "get_portfolio_state":
                result = wrapper._get("/state")
                return wrapper._text(result)

            elif name == "get_positions":
                result = wrapper._get("/positions")
                return wrapper._text(result)

            elif name == "get_position":
                result = wrapper._get(f"/positions/{arguments['instrument']}")
                return wrapper._text(result)

            elif name == "get_balance":
                result = wrapper._get("/balance")
                return wrapper._text(result)

            elif name == "get_risk":
                result = wrapper._get("/risk")
                return wrapper._text(result)

            elif name == "validate_trade":
                result = wrapper._post(
                    "/validate",
                    json_body={
                        "instrument": arguments["instrument"],
                        "side": arguments["side"],
                        "size": arguments["size"],
                    },
                )
                return wrapper._text(result)

            else:
                return wrapper._error_text(f"Unknown tool: {name}")

        except Exception as e:
            logger.error("Portfolio MCP tool '%s' failed: %s", name, e)
            return wrapper._error_text(str(e))

    return server
