"""
MCP server for web search integration.
Exposes tools for searching the web with financial context,
enabling the decision agent to access news, analysis, and market data.

Implements issue #1472 requirements:
- Web search via configurable provider (Brave/Google)
- Financial query builder
- Result caching (15 min TTL)
- Rate limiting (10 searches/min)
- Deduplication
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
    SEARCH_FAILED,
    RATE_LIMITED,
    INVALID_QUERY,
    DATABASE_ERROR,
)
from services.shared.mcp_metadata import wrap_response, wrap_error
from services.websearch_mcp.search_client import (
    SearchClient,
    FINANCIAL_DOMAINS,
    build_financial_query,
)

_CACHE_TTL = 900.0  # 15 minutes per spec


def create_server(search_client: SearchClient) -> Server:
    """Create and configure the web search MCP server."""
    server = Server("websearch-mcp")
    cache = TtlCache(default_ttl=_CACHE_TTL)

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="web_search",
                description="Search the web for information. Returns structured results with title, URL, snippet, and source.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 5,
                            "maximum": 20,
                            "description": "Maximum number of results to return",
                        },
                        "domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of domains to restrict results to (e.g. ['reuters.com', 'bloomberg.com'])",
                        },
                        "recency_hours": {
                            "type": "integer",
                            "description": "Only return results from the last N hours",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache and fetch fresh results",
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="financial_search",
                description="Search for financial news and analysis about a trading instrument. Automatically builds optimized queries and filters to financial news sources.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instrument": {
                            "type": "string",
                            "description": "Trading pair or asset (e.g. BTC/USD, ETH, Bitcoin)",
                        },
                        "topic": {
                            "type": "string",
                            "enum": [
                                "regulatory",
                                "technical",
                                "fundamental",
                                "sentiment",
                                "earnings",
                                "general",
                            ],
                            "default": "general",
                            "description": "Search focus area",
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 5,
                            "maximum": 20,
                            "description": "Maximum number of results to return",
                        },
                        "recency_hours": {
                            "type": "integer",
                            "default": 24,
                            "description": "Only return results from the last N hours",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache and fetch fresh results",
                        },
                    },
                    "required": ["instrument"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        start = time.monotonic()
        force_refresh = arguments.get("force_refresh", False)

        try:
            if name == "web_search":
                query = arguments["query"]
                if not query or not query.strip():
                    return wrap_error(
                        McpError(INVALID_QUERY, "Query cannot be empty").to_dict(),
                        start_time=start,
                    )

                max_results = min(arguments.get("max_results", 5), 20)
                domains = arguments.get("domains")
                recency_hours = arguments.get("recency_hours")

                cache_key = f"search:{query}:{max_results}:{domains}:{recency_hours}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(
                            cached[0],
                            start_time=start,
                            cached=True,
                            cache_ttl_remaining=cached[1],
                            source="web_search",
                        )

                results = search_client.search(
                    query=query,
                    max_results=max_results,
                    domains=domains,
                    recency_hours=recency_hours,
                )
                data = {"query": query, "results": results, "count": len(results)}
                cache.set(cache_key, data, ttl=_CACHE_TTL)
                return wrap_response(data, start_time=start, source="web_search")

            elif name == "financial_search":
                instrument = arguments["instrument"]
                topic = arguments.get("topic", "general")
                max_results = min(arguments.get("max_results", 5), 20)
                recency_hours = arguments.get("recency_hours", 24)

                query = build_financial_query(instrument, topic)
                cache_key = f"financial:{instrument}:{topic}:{max_results}:{recency_hours}"
                if not force_refresh:
                    cached = cache.get(cache_key)
                    if cached:
                        return wrap_response(
                            cached[0],
                            start_time=start,
                            cached=True,
                            cache_ttl_remaining=cached[1],
                            source="web_search",
                        )

                results = search_client.search(
                    query=query,
                    max_results=max_results,
                    domains=FINANCIAL_DOMAINS,
                    recency_hours=recency_hours,
                )
                data = {
                    "instrument": instrument,
                    "topic": topic,
                    "query": query,
                    "results": results,
                    "count": len(results),
                }
                cache.set(cache_key, data, ttl=_CACHE_TTL)
                return wrap_response(data, start_time=start, source="web_search")

            else:
                return wrap_error(
                    McpError("UNKNOWN_TOOL", f"Unknown tool: {name}").to_dict(),
                    start_time=start,
                )

        except RuntimeError as e:
            error_msg = str(e)
            if "Rate limit" in error_msg:
                return wrap_error(
                    McpError(RATE_LIMITED, error_msg).to_dict(),
                    start_time=start,
                )
            return wrap_error(
                McpError(SEARCH_FAILED, error_msg).to_dict(),
                start_time=start,
            )
        except Exception as e:
            logging.exception("Tool call %s failed", name)
            return wrap_error(
                McpError(SEARCH_FAILED, str(e)).to_dict(),
                start_time=start,
            )

    return server
