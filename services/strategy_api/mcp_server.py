"""
MCP wrapper for the Strategy Derivation REST API.

Thin MCP server that translates tool calls into REST API requests
against the Strategy API service.
"""

import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.rest_api_shared.mcp_wrapper import MCPAPIWrapper

logger = logging.getLogger(__name__)


class StrategyMCPWrapper(MCPAPIWrapper):
    """MCP wrapper for the Strategy REST API."""

    pass


def create_server(api_base_url: str) -> Server:
    """Create an MCP server wrapping the Strategy REST API."""
    wrapper = StrategyMCPWrapper(api_base_url)
    server = Server("strategy-api-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_top_strategies",
                description="Get top performing strategy implementations sorted by Sharpe ratio",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Max results to return",
                        },
                        "instrument": {
                            "type": "string",
                            "description": "Filter by trading instrument",
                        },
                        "min_sharpe": {
                            "type": "number",
                            "description": "Minimum Sharpe ratio filter",
                        },
                    },
                },
            ),
            Tool(
                name="evaluate_strategy",
                description="Run a backtest evaluation on a strategy implementation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "implementation_id": {
                            "type": "string",
                            "description": "Strategy implementation UUID",
                        },
                        "instrument": {
                            "type": "string",
                            "description": "Trading instrument to evaluate",
                        },
                        "days": {
                            "type": "integer",
                            "default": 30,
                            "description": "Number of days to backtest",
                        },
                    },
                    "required": ["implementation_id", "instrument"],
                },
            ),
            Tool(
                name="get_strategy_signal",
                description="Get current trading signal from a strategy implementation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "implementation_id": {
                            "type": "string",
                            "description": "Strategy implementation UUID",
                        },
                        "instrument": {
                            "type": "string",
                            "description": "Trading instrument",
                        },
                    },
                    "required": ["implementation_id", "instrument"],
                },
            ),
            Tool(
                name="list_specs",
                description="List all strategy specifications",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category/source",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "description": "Max results",
                        },
                    },
                },
            ),
            Tool(
                name="get_spec",
                description="Get a strategy specification by ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "spec_id": {
                            "type": "string",
                            "description": "Strategy spec UUID",
                        },
                    },
                    "required": ["spec_id"],
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
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "get_top_strategies":
                params = {"order_by": "sharpe", "limit": arguments.get("limit", 10)}
                if arguments.get("instrument"):
                    params["instrument"] = arguments["instrument"]
                if arguments.get("min_sharpe"):
                    params["min_sharpe"] = arguments["min_sharpe"]
                result = wrapper._get("/implementations", params=params)
                return wrapper._text(result)

            elif name == "evaluate_strategy":
                impl_id = arguments["implementation_id"]
                days = arguments.get("days", 30)
                result = wrapper._post(
                    f"/implementations/{impl_id}/evaluate",
                    json_body={
                        "instrument": arguments["instrument"],
                        "start_date": (date.today() - timedelta(days=days)).isoformat(),
                        "end_date": date.today().isoformat(),
                    },
                )
                return wrapper._text(result)

            elif name == "get_strategy_signal":
                impl_id = arguments["implementation_id"]
                result = wrapper._get(
                    f"/implementations/{impl_id}/signal",
                    params={"instrument": arguments["instrument"]},
                )
                return wrapper._text(result)

            elif name == "list_specs":
                params = {"limit": arguments.get("limit", 50)}
                if arguments.get("category"):
                    params["category"] = arguments["category"]
                result = wrapper._get("/specs", params=params)
                return wrapper._text(result)

            elif name == "get_spec":
                result = wrapper._get(f"/specs/{arguments['spec_id']}")
                return wrapper._text(result)

            elif name == "create_spec":
                result = wrapper._post(
                    "/specs",
                    json_body={
                        "name": arguments["name"],
                        "indicators": arguments["indicators"],
                        "entry_conditions": arguments["entry_conditions"],
                        "exit_conditions": arguments["exit_conditions"],
                        "parameters": arguments["parameters"],
                        "description": arguments["description"],
                    },
                )
                return wrapper._text(result)

            else:
                return wrapper._error_text(f"Unknown tool: {name}")

        except Exception as e:
            logger.error("Strategy MCP tool '%s' failed: %s", name, e)
            return wrapper._error_text(str(e))

    return server
