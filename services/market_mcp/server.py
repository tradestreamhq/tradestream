"""
MCP server for the market data service.
Exposes tools for querying candle data, prices, volatility, and market summaries.
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
    INVALID_SYMBOL,
    INVALID_TIMEFRAME,
    NO_DATA,
    DATABASE_ERROR,
)
from services.shared.mcp_metadata import wrap_response, wrap_error
from services.market_mcp.influxdb_client import InfluxDBMarketClient
from services.market_mcp.redis_client import RedisMarketClient

_CACHE_TTLS = {
    "get_candles": 60.0,
    "get_latest_price": 5.0,
    "get_volatility": 30.0,
    "get_market_summary": 30.0,
}


def create_server(
    influxdb_client: InfluxDBMarketClient,
    redis_client: RedisMarketClient,
) -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("market-mcp")
    cache = TtlCache(default_ttl=30.0)

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="get_candles",
                description="Query OHLCV candle data for a cryptocurrency symbol.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Currency pair (e.g., BTC/USD)",
                        },
                        "timeframe": {
                            "type": "string",
                            "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                            "default": "1m",
                            "description": "Candle timeframe",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time in RFC3339 or relative (e.g., -1h).",
                        },
                        "end": {
                            "type": "string",
                            "description": "End time in RFC3339 or relative.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 100,
                            "maximum": 1000,
                            "description": "Maximum number of candles to return.",
                        },
                        "offset": {
                            "type": "integer",
                            "default": 0,
                            "description": "Offset for pagination.",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache and fetch fresh data",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            Tool(
                name="get_latest_price",
                description="Get the most recent price for a cryptocurrency symbol.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Currency pair (e.g., BTC/USD)",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache and fetch fresh data",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            Tool(
                name="get_volatility",
                description="Compute volatility metrics (stddev of returns, ATR) for a symbol.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Currency pair (e.g., BTC/USD)",
                        },
                        "period_minutes": {
                            "type": "integer",
                            "default": 60,
                            "description": "Lookback period in minutes.",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache and fetch fresh data",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            Tool(
                name="get_symbols",
                description="Get the list of available cryptocurrency symbols.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_market_summary",
                description="Get aggregated market summary including price, changes, volume, volatility, and VWAP.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Currency pair (e.g., BTC/USD)",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache and fetch fresh data",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        start = time.monotonic()
        force_refresh = arguments.get("force_refresh", False)

        try:
            if name == "get_candles":
                cache_key = f"candles:{arguments['symbol']}:{arguments.get('timeframe', '1m')}:{arguments.get('limit', 100)}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(
                            cached[0],
                            start_time=start,
                            cached=True,
                            cache_ttl_remaining=cached[1],
                            source="influxdb",
                        )
                result = influxdb_client.get_candles(
                    symbol=arguments["symbol"],
                    timeframe=arguments.get("timeframe", "1m"),
                    start=arguments.get("start"),
                    end=arguments.get("end"),
                    limit=arguments.get("limit", 100),
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["get_candles"])
                return wrap_response(result, start_time=start, source="influxdb")

            elif name == "get_latest_price":
                cache_key = f"price:{arguments['symbol']}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(
                            cached[0],
                            start_time=start,
                            cached=True,
                            cache_ttl_remaining=cached[1],
                            source="influxdb",
                        )
                result = influxdb_client.get_latest_price(
                    symbol=arguments["symbol"],
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["get_latest_price"])
                return wrap_response(result, start_time=start, source="influxdb")

            elif name == "get_volatility":
                cache_key = f"vol:{arguments['symbol']}:{arguments.get('period_minutes', 60)}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(
                            cached[0],
                            start_time=start,
                            cached=True,
                            cache_ttl_remaining=cached[1],
                            source="influxdb",
                        )
                result = influxdb_client.get_volatility(
                    symbol=arguments["symbol"],
                    period_minutes=arguments.get("period_minutes", 60),
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["get_volatility"])
                return wrap_response(result, start_time=start, source="influxdb")

            elif name == "get_symbols":
                result = redis_client.get_symbols()
                return wrap_response(result, start_time=start, source="redis")

            elif name == "get_market_summary":
                cache_key = f"summary:{arguments['symbol']}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(
                            cached[0],
                            start_time=start,
                            cached=True,
                            cache_ttl_remaining=cached[1],
                            source="influxdb",
                        )
                result = influxdb_client.get_market_summary(
                    symbol=arguments["symbol"],
                )
                cache.set(cache_key, result, ttl=_CACHE_TTLS["get_market_summary"])
                return wrap_response(result, start_time=start, source="influxdb")

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
