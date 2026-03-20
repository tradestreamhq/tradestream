"""
MCP server for CoinMarketCap cryptocurrency data.

Exposes tools for querying prices, market caps, volumes, trending coins,
and exchange rates. Includes TTL-based caching to reduce API calls.
"""

import logging
import time
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from services.shared.mcp_cache import TtlCache
from services.shared.mcp_errors import (
    McpError,
    NOT_FOUND,
    DATABASE_ERROR,
    INVALID_PARAMETER,
)
from services.shared.mcp_metadata import wrap_response, wrap_error
from services.coinmarketcap_mcp.cmc_client import CoinMarketCapClient

logger = logging.getLogger(__name__)

server = Server("coinmarketcap-mcp")
_cache = TtlCache(default_ttl=60.0)

_CACHE_TTLS = {
    "get_price": 30.0,
    "get_market_cap": 60.0,
    "get_volume": 60.0,
    "get_trending": 120.0,
    "get_exchange_rates": 30.0,
}


def _set_cmc_client(client: CoinMarketCapClient) -> None:
    """Set the CMC client on the server instance."""
    server._cmc_client = client


def _get_cmc_client() -> CoinMarketCapClient:
    """Get the CMC client from the server instance."""
    return server._cmc_client


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="get_price",
            description="Get current price for one or more cryptocurrencies",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Cryptocurrency symbols (e.g. ['BTC', 'ETH'])",
                    },
                    "convert": {
                        "type": "string",
                        "default": "USD",
                        "description": "Target currency for price conversion",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass cache and fetch fresh data",
                    },
                },
                "required": ["symbols"],
            },
        ),
        Tool(
            name="get_market_cap",
            description="Get market capitalization data for cryptocurrencies",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Cryptocurrency symbols",
                    },
                    "convert": {
                        "type": "string",
                        "default": "USD",
                        "description": "Target currency",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass cache",
                    },
                },
                "required": ["symbols"],
            },
        ),
        Tool(
            name="get_volume",
            description="Get 24h trading volume for cryptocurrencies",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Cryptocurrency symbols",
                    },
                    "convert": {
                        "type": "string",
                        "default": "USD",
                        "description": "Target currency",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass cache",
                    },
                },
                "required": ["symbols"],
            },
        ),
        Tool(
            name="get_trending",
            description="Get top trending cryptocurrencies by market cap",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "maximum": 100,
                        "description": "Number of results to return",
                    },
                    "convert": {
                        "type": "string",
                        "default": "USD",
                        "description": "Target currency",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass cache",
                    },
                },
            },
        ),
        Tool(
            name="get_exchange_rates",
            description="Get exchange rate for a cryptocurrency against a target currency",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Source cryptocurrency symbol (e.g. BTC)",
                    },
                    "convert": {
                        "type": "string",
                        "default": "USD",
                        "description": "Target currency",
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Bypass cache",
                    },
                },
                "required": ["symbol"],
            },
        ),
    ]


def _extract_quote_fields(
    quote_data: dict[str, Any], convert: str, fields: list[str]
) -> dict[str, Any]:
    """Extract specific fields from a CMC quote entry."""
    quote = quote_data.get("quote", {}).get(convert, {})
    result: dict[str, Any] = {
        "name": quote_data.get("name"),
        "symbol": quote_data.get("symbol"),
    }
    for field in fields:
        result[field] = quote.get(field)
    return result


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls with caching and structured errors."""
    start = time.monotonic()
    cmc = _get_cmc_client()
    force_refresh = arguments.get("force_refresh", False)

    try:
        if name == "get_price":
            symbols = [s.upper() for s in arguments["symbols"]]
            convert = arguments.get("convert", "USD").upper()
            cache_key = f"price:{','.join(sorted(symbols))}:{convert}"

            if not force_refresh:
                cached = _cache.get(cache_key)
                if cached:
                    return wrap_response(
                        cached[0],
                        start_time=start,
                        cached=True,
                        cache_ttl_remaining=cached[1],
                        source="coinmarketcap",
                    )

            quotes = await cmc.get_quotes(symbols, convert=convert)
            result = []
            for sym in symbols:
                entries = quotes.get(sym, [])
                if entries:
                    entry = entries[0] if isinstance(entries, list) else entries
                    result.append(
                        _extract_quote_fields(
                            entry,
                            convert,
                            ["price", "percent_change_1h", "percent_change_24h"],
                        )
                    )
            _cache.set(cache_key, result, ttl=_CACHE_TTLS["get_price"])
            return wrap_response(result, start_time=start, source="coinmarketcap")

        elif name == "get_market_cap":
            symbols = [s.upper() for s in arguments["symbols"]]
            convert = arguments.get("convert", "USD").upper()
            cache_key = f"mcap:{','.join(sorted(symbols))}:{convert}"

            if not force_refresh:
                cached = _cache.get(cache_key)
                if cached:
                    return wrap_response(
                        cached[0],
                        start_time=start,
                        cached=True,
                        cache_ttl_remaining=cached[1],
                        source="coinmarketcap",
                    )

            quotes = await cmc.get_quotes(symbols, convert=convert)
            result = []
            for sym in symbols:
                entries = quotes.get(sym, [])
                if entries:
                    entry = entries[0] if isinstance(entries, list) else entries
                    result.append(
                        _extract_quote_fields(
                            entry,
                            convert,
                            [
                                "market_cap",
                                "market_cap_dominance",
                                "fully_diluted_market_cap",
                            ],
                        )
                    )
            _cache.set(cache_key, result, ttl=_CACHE_TTLS["get_market_cap"])
            return wrap_response(result, start_time=start, source="coinmarketcap")

        elif name == "get_volume":
            symbols = [s.upper() for s in arguments["symbols"]]
            convert = arguments.get("convert", "USD").upper()
            cache_key = f"vol:{','.join(sorted(symbols))}:{convert}"

            if not force_refresh:
                cached = _cache.get(cache_key)
                if cached:
                    return wrap_response(
                        cached[0],
                        start_time=start,
                        cached=True,
                        cache_ttl_remaining=cached[1],
                        source="coinmarketcap",
                    )

            quotes = await cmc.get_quotes(symbols, convert=convert)
            result = []
            for sym in symbols:
                entries = quotes.get(sym, [])
                if entries:
                    entry = entries[0] if isinstance(entries, list) else entries
                    result.append(
                        _extract_quote_fields(
                            entry,
                            convert,
                            ["volume_24h", "volume_change_24h"],
                        )
                    )
            _cache.set(cache_key, result, ttl=_CACHE_TTLS["get_volume"])
            return wrap_response(result, start_time=start, source="coinmarketcap")

        elif name == "get_trending":
            limit = arguments.get("limit", 20)
            convert = arguments.get("convert", "USD").upper()
            cache_key = f"trending:{limit}:{convert}"

            if not force_refresh:
                cached = _cache.get(cache_key)
                if cached:
                    return wrap_response(
                        cached[0],
                        start_time=start,
                        cached=True,
                        cache_ttl_remaining=cached[1],
                        source="coinmarketcap",
                    )

            listings = await cmc.get_listings(limit=limit, convert=convert)
            result = []
            for item in listings:
                quote = item.get("quote", {}).get(convert, {})
                result.append(
                    {
                        "rank": item.get("cmc_rank"),
                        "name": item.get("name"),
                        "symbol": item.get("symbol"),
                        "price": quote.get("price"),
                        "percent_change_24h": quote.get("percent_change_24h"),
                        "market_cap": quote.get("market_cap"),
                        "volume_24h": quote.get("volume_24h"),
                    }
                )
            _cache.set(cache_key, result, ttl=_CACHE_TTLS["get_trending"])
            return wrap_response(result, start_time=start, source="coinmarketcap")

        elif name == "get_exchange_rates":
            symbol = arguments["symbol"].upper()
            convert = arguments.get("convert", "USD").upper()
            cache_key = f"rate:{symbol}:{convert}"

            if not force_refresh:
                cached = _cache.get(cache_key)
                if cached:
                    return wrap_response(
                        cached[0],
                        start_time=start,
                        cached=True,
                        cache_ttl_remaining=cached[1],
                        source="coinmarketcap",
                    )

            entry = await cmc.get_exchange_rates(symbol=symbol, convert=convert)
            if not entry:
                return wrap_error(
                    McpError(
                        NOT_FOUND,
                        f"No data found for symbol '{symbol}'",
                        details={"symbol": symbol},
                    ).to_dict(),
                    start_time=start,
                )
            quote = entry.get("quote", {}).get(convert, {})
            result = {
                "symbol": symbol,
                "convert": convert,
                "price": quote.get("price"),
                "last_updated": quote.get("last_updated"),
            }
            _cache.set(cache_key, result, ttl=_CACHE_TTLS["get_exchange_rates"])
            return wrap_response(result, start_time=start, source="coinmarketcap")

        else:
            return wrap_error(
                McpError("UNKNOWN_TOOL", f"Unknown tool: {name}").to_dict(),
                start_time=start,
            )

    except Exception as e:
        logger.exception("Tool call %s failed", name)
        return wrap_error(
            McpError(DATABASE_ERROR, str(e)).to_dict(), start_time=start
        )
