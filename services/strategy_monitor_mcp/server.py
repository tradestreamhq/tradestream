"""MCP server for strategy monitoring.

Wraps the strategy_monitor_api functionality as MCP tools,
enabling AI agents to discover and query strategy monitoring data.
"""

import json
from typing import Any

from services.shared.mcp_server_base import McpServerBase, ToolDef
from services.strategy_monitor_mcp.postgres_client import PostgresClient


class StrategyMonitorMcpServer(McpServerBase):
    """MCP server exposing strategy monitoring tools."""

    def __init__(self, postgres_client: PostgresClient) -> None:
        self._pg = postgres_client
        super().__init__("strategy-monitor")

    def tool_definitions(self) -> list[ToolDef]:
        return [
            ToolDef(
                name="get_strategies",
                description=(
                    "Get strategies with optional filtering by symbol, "
                    "strategy type, and minimum score. Supports pagination."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Filter by trading symbol (e.g. BTC/USD)",
                        },
                        "strategy_type": {
                            "type": "string",
                            "description": "Filter by strategy type",
                        },
                        "min_score": {
                            "type": "number",
                            "description": "Minimum performance score",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results per page",
                            "default": 50,
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Pagination offset",
                            "default": 0,
                        },
                    },
                },
            ),
            ToolDef(
                name="get_strategy_by_id",
                description="Get detailed information about a specific strategy by its ID",
                input_schema={
                    "type": "object",
                    "properties": {
                        "strategy_id": {
                            "type": "string",
                            "description": "Strategy identifier",
                        },
                    },
                    "required": ["strategy_id"],
                },
            ),
            ToolDef(
                name="get_metrics",
                description=(
                    "Get aggregated strategy metrics including total count, "
                    "average score, and breakdown by strategy type"
                ),
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            ToolDef(
                name="get_symbols",
                description="Get list of distinct trading symbols with active strategies",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            ToolDef(
                name="get_strategy_types",
                description="Get list of distinct strategy types in use",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    async def handle_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "get_strategies":
            return await self._pg.get_strategies(
                symbol=arguments.get("symbol"),
                strategy_type=arguments.get("strategy_type"),
                min_score=arguments.get("min_score"),
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
            )

        if name == "get_strategy_by_id":
            result = await self._pg.get_strategy_by_id(arguments["strategy_id"])
            if result is None:
                raise KeyError(f"Strategy not found: {arguments['strategy_id']}")
            return result

        if name == "get_metrics":
            return await self._pg.get_metrics()

        if name == "get_symbols":
            return await self._pg.get_symbols()

        if name == "get_strategy_types":
            return await self._pg.get_strategy_types()

        raise ValueError(f"Unknown tool: {name}")
