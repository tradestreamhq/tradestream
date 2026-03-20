"""
MCP server for backtest execution and historical performance.
Exposes tools for running backtests and querying historical strategy performance.
"""

import json
import logging
import time
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.shared.mcp_cache import TtlCache
from services.shared.mcp_errors import (
    McpError,
    STRATEGY_NOT_FOUND,
    DATABASE_ERROR,
)
from services.shared.mcp_metadata import wrap_response, wrap_error
from services.backtest_mcp.postgres_client import PostgresClient

_CACHE_TTLS = {
    "get_historical_performance": 300.0,  # 5 minutes
}


def create_server(postgres_client: PostgresClient) -> Server:
    """Create and configure the backtest MCP server with all tools."""
    server = Server("backtest-mcp")
    cache = TtlCache(default_ttl=300.0)

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
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache and fetch fresh data",
                        },
                    },
                    "required": ["strategy_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        start = time.monotonic()
        force_refresh = arguments.get("force_refresh", False)

        try:
            if name == "run_backtest":
                result = await postgres_client.run_backtest(
                    strategy_id=arguments["strategy_id"],
                    symbol=arguments["symbol"],
                    start_date=arguments.get("start_date"),
                    end_date=arguments.get("end_date"),
                )
                if "error" in result:
                    return wrap_error(
                        McpError(
                            STRATEGY_NOT_FOUND,
                            result["error"],
                            details={
                                "strategy_id": arguments["strategy_id"],
                                "symbol": arguments["symbol"],
                            },
                        ).to_dict(),
                        start_time=start,
                    )
                return wrap_response(result, start_time=start, source="postgresql")

            elif name == "get_historical_performance":
                cache_key = f"hist:{arguments['strategy_id']}:{arguments.get('symbol', '')}:{arguments.get('period', '3m')}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(
                            cached[0],
                            start_time=start,
                            cached=True,
                            cache_ttl_remaining=cached[1],
                            source="postgresql",
                        )
                result = await postgres_client.get_historical_performance(
                    strategy_id=arguments["strategy_id"],
                    symbol=arguments.get("symbol"),
                    period=arguments.get("period", "3m"),
                )
                if "error" in result:
                    return wrap_error(
                        McpError(
                            STRATEGY_NOT_FOUND,
                            result["error"],
                            details={"strategy_id": arguments["strategy_id"]},
                        ).to_dict(),
                        start_time=start,
                    )
                cache.set(
                    cache_key,
                    result,
                    ttl=_CACHE_TTLS["get_historical_performance"],
                )
                return wrap_response(result, start_time=start, source="postgresql")

            else:
                return wrap_error(
                    McpError("UNKNOWN_TOOL", f"Unknown tool: {name}").to_dict(),
                    start_time=start,
                )
        except Exception as e:
            logging.exception("Tool call %s failed", name)
            return wrap_error(
                McpError(DATABASE_ERROR, str(e)).to_dict(), start_time=start
            )

    return server
