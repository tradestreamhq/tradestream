"""
MCP server for the market data service.
Exposes tools for querying candle data, prices, volatility, and market summaries.
"""

import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.market_mcp.influxdb_client import MarketInfluxDBClient
from services.market_mcp.redis_client import RedisClient


def create_server(
    influxdb_client: MarketInfluxDBClient,
    redis_client: RedisClient,
) -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("market-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_candles",
                description="Query historical candle (OHLCV) data from InfluxDB for a given symbol and timeframe.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading symbol (e.g., BTC/USD)",
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "Candle timeframe (e.g., 1m, 5m, 1h)",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time in RFC3339 format (optional)",
                        },
                        "end": {
                            "type": "string",
                            "description": "End time in RFC3339 format (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 100,
                            "description": "Maximum number of candles to return",
                        },
                    },
                    "required": ["symbol", "timeframe"],
                },
            ),
            Tool(
                name="get_latest_price",
                description="Get the most recent price for a symbol including 24h volume and change.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading symbol (e.g., BTC/USD)",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            Tool(
                name="get_volatility",
                description="Compute volatility metrics (stddev of returns and ATR) from recent candle data.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading symbol (e.g., BTC/USD)",
                        },
                        "period_minutes": {
                            "type": "integer",
                            "default": 60,
                            "description": "Lookback period in minutes",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            Tool(
                name="get_symbols",
                description="Get the list of tracked cryptocurrency symbols from Redis.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_market_summary",
                description="Get an aggregated market summary for a symbol including price, changes, volume, volatility, and VWAP.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading symbol (e.g., BTC/USD)",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        if name == "get_candles":
            candles = influxdb_client.get_candles(
                symbol=arguments["symbol"],
                timeframe=arguments["timeframe"],
                start=arguments.get("start"),
                end=arguments.get("end"),
                limit=arguments.get("limit", 100),
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(candles, default=str),
                )
            ]

        elif name == "get_latest_price":
            result = influxdb_client.get_latest_price(
                symbol=arguments["symbol"],
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, default=str),
                )
            ]

        elif name == "get_volatility":
            result = influxdb_client.get_volatility(
                symbol=arguments["symbol"],
                period_minutes=arguments.get("period_minutes", 60),
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, default=str),
                )
            ]

        elif name == "get_symbols":
            symbols = redis_client.get_symbols()
            return [
                TextContent(
                    type="text",
                    text=json.dumps(symbols, default=str),
                )
            ]

        elif name == "get_market_summary":
            result = influxdb_client.get_market_summary(
                symbol=arguments["symbol"],
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, default=str),
                )
            ]

        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": f"Unknown tool: {name}"}),
                )
            ]

    return server
