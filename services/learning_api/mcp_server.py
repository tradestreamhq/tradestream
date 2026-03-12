"""
MCP wrapper for the Learning Engine REST API.
"""

import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.rest_api_shared.mcp_wrapper import MCPAPIWrapper

logger = logging.getLogger(__name__)


def create_server(api_base_url: str) -> Server:
    """Create an MCP server wrapping the Learning Engine REST API."""
    wrapper = MCPAPIWrapper(api_base_url)
    server = Server("learning-api-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="list_decisions",
                description="List past trading decisions with optional filters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instrument": {
                            "type": "string",
                            "description": "Filter by instrument",
                        },
                        "from": {
                            "type": "string",
                            "description": "Start datetime (ISO 8601)",
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
                name="record_decision",
                description="Record a new agent decision",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "signal_id": {"type": "string"},
                        "agent_name": {"type": "string"},
                        "decision_type": {"type": "string"},
                        "score": {"type": "number"},
                        "tier": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "model_used": {"type": "string"},
                        "latency_ms": {"type": "integer"},
                        "tokens_used": {"type": "integer"},
                    },
                    "required": [
                        "signal_id",
                        "agent_name",
                        "decision_type",
                        "score",
                        "tier",
                        "reasoning",
                    ],
                },
            ),
            Tool(
                name="get_decision",
                description="Get a specific decision by ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "decision_id": {
                            "type": "string",
                            "description": "Decision UUID",
                        },
                    },
                    "required": ["decision_id"],
                },
            ),
            Tool(
                name="get_patterns",
                description="Get detected performance patterns from recent decisions",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_performance",
                description="Get aggregate performance metrics",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instrument": {"type": "string"},
                        "period": {
                            "type": "string",
                            "enum": ["7d", "30d", "90d", "all"],
                            "default": "30d",
                        },
                    },
                },
            ),
            Tool(
                name="find_similar",
                description="Find similar historical market situations",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instrument": {"type": "string"},
                        "price": {"type": "number"},
                        "volatility": {"type": "number"},
                        "volume": {"type": "number"},
                    },
                    "required": ["instrument", "price"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        try:
            if name == "list_decisions":
                params = {"limit": arguments.get("limit", 50)}
                if arguments.get("instrument"):
                    params["instrument"] = arguments["instrument"]
                if arguments.get("from"):
                    params["from"] = arguments["from"]
                result = wrapper._get("/decisions", params=params)
                return wrapper._text(result)

            elif name == "record_decision":
                result = wrapper._post("/decisions", json_body=arguments)
                return wrapper._text(result)

            elif name == "get_decision":
                result = wrapper._get(f"/decisions/{arguments['decision_id']}")
                return wrapper._text(result)

            elif name == "get_patterns":
                result = wrapper._get("/patterns")
                return wrapper._text(result)

            elif name == "get_performance":
                params = {"period": arguments.get("period", "30d")}
                if arguments.get("instrument"):
                    params["instrument"] = arguments["instrument"]
                result = wrapper._get("/performance", params=params)
                return wrapper._text(result)

            elif name == "find_similar":
                result = wrapper._post("/similar", json_body=arguments)
                return wrapper._text(result)

            else:
                return wrapper._error_text(f"Unknown tool: {name}")

        except Exception as e:
            logger.error("Learning MCP tool '%s' failed: %s", name, e)
            return wrapper._error_text(str(e))

    return server
