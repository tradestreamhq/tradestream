"""
MCP wrapper for the PnL Attribution REST API.
"""

import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.rest_api_shared.mcp_wrapper import MCPAPIWrapper

logger = logging.getLogger(__name__)


def create_server(api_base_url: str) -> Server:
    """Create an MCP server wrapping the PnL Attribution REST API."""
    wrapper = MCPAPIWrapper(api_base_url)
    server = Server("pnl-attribution-api-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_pnl_attribution",
                description="Get full PnL attribution breakdown by strategy, asset, direction, and time",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "enum": ["daily", "weekly", "monthly"],
                            "description": "Time bucketing granularity",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start date ISO-8601",
                        },
                        "end": {
                            "type": "string",
                            "description": "End date ISO-8601",
                        },
                    },
                },
            ),
            Tool(
                name="get_strategy_attribution",
                description="Get PnL attribution by strategy with hit rate and avg win/loss",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "string",
                            "description": "Start date ISO-8601",
                        },
                        "end": {
                            "type": "string",
                            "description": "End date ISO-8601",
                        },
                    },
                },
            ),
            Tool(
                name="get_asset_attribution",
                description="Get PnL attribution by asset/symbol",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "string",
                            "description": "Start date ISO-8601",
                        },
                        "end": {
                            "type": "string",
                            "description": "End date ISO-8601",
                        },
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "get_pnl_attribution":
                params = {}
                if "period" in arguments:
                    params["period"] = arguments["period"]
                if "start" in arguments:
                    params["start"] = arguments["start"]
                if "end" in arguments:
                    params["end"] = arguments["end"]
                result = wrapper._get("/attribution", params=params)
                return wrapper._text(result)

            elif name == "get_strategy_attribution":
                params = {}
                if "start" in arguments:
                    params["start"] = arguments["start"]
                if "end" in arguments:
                    params["end"] = arguments["end"]
                result = wrapper._get("/attribution/strategies", params=params)
                return wrapper._text(result)

            elif name == "get_asset_attribution":
                params = {}
                if "start" in arguments:
                    params["start"] = arguments["start"]
                if "end" in arguments:
                    params["end"] = arguments["end"]
                result = wrapper._get("/attribution/assets", params=params)
                return wrapper._text(result)

            else:
                return wrapper._error_text(f"Unknown tool: {name}")

        except Exception as e:
            logger.error("PnL Attribution MCP tool '%s' failed: %s", name, e)
            return wrapper._error_text(str(e))

    return server
