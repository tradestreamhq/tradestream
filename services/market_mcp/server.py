"""
MCP server for the market data service.
Exposes tools for querying candles, prices, volatility, symbols, and market summaries.
"""

import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.market_mcp.influxdb_client import InfluxDBMarketClient
from services.market_mcp.redis_client import RedisMarketClient


def create_server(
    influxdb_client: InfluxDBMarketClient,
    redis_client: RedisMarketClient,
) -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("market-mcp")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_candles",
                description="Get OHLCV candle data for a symbol from InfluxDB.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading symbol / currency pair (e.g., BTC/USD)",
                        },
                        "timeframe": {
                            "type": "string",
                            "default": "1m",
                            "description": "Candle timeframe (e.g., 1m, 5m, 1h)",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time (RFC3339 or relative like -1h). Optional.",
                        },
                        "end": {
                            "type": "string",
                            "description": "End time (RFC3339 or relative). Optional.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 100,
                            "description": "Maximum number of candles to return",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            Tool(
                name="get_latest_price",
                description="Get the most recent price for a symbol.",
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
                description="Get volatility metrics (stddev of returns, ATR) for a symbol.",
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
                description="Get list of available trading symbols from Redis.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_market_summary",
                description="Get aggregated market summary for a symbol including price, changes, volume, volatility, and VWAP.",
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
                timeframe=arguments.get("timeframe", "1m"),
                start=arguments.get("start"),
                end=arguments.get("end"),
                limit=arguments.get("limit", 100),
            )
            return [TextContent(type="text", text=json.dumps(candles, default=str))]

        elif name == "get_latest_price":
            price_data = influxdb_client.get_latest_price(
                symbol=arguments["symbol"],
            )
            return [TextContent(type="text", text=json.dumps(price_data, default=str))]

        elif name == "get_volatility":
            volatility_data = influxdb_client.get_volatility(
                symbol=arguments["symbol"],
                period_minutes=arguments.get("period_minutes", 60),
            )
            return [TextContent(type="text", text=json.dumps(volatility_data, default=str))]

        elif name == "get_symbols":
            symbols = redis_client.get_symbols()
            return [TextContent(type="text", text=json.dumps(symbols, default=str))]

        elif name == "get_market_summary":
            summary = influxdb_client.get_market_summary(
                symbol=arguments["symbol"],
            )
            return [TextContent(type="text", text=json.dumps(summary, default=str))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    return server
