"""
MCP server for the signal service.
Exposes tools for signal emission, decision logging, and analytics.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from services.shared.mcp_cache import TtlCache
from services.shared.mcp_errors import McpError, DATABASE_ERROR
from services.shared.mcp_metadata import wrap_response, wrap_error
from services.signal_mcp.postgres_client import PostgresClient
from services.signal_mcp.redis_client import RedisClient


def create_server(
    postgres_client: PostgresClient,
    redis_client: RedisClient,
) -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("signal-mcp")
    cache = TtlCache(default_ttl=30.0)

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="emit_signal",
                description="Emit a trading signal. Stores in PostgreSQL and publishes to Redis.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Trading symbol (e.g., BTC/USD)",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["BUY", "SELL", "HOLD"],
                            "description": "Signal action",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Signal confidence 0.0-1.0",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Reasoning for the signal",
                        },
                        "strategy_breakdown": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "strategy_type": {"type": "string"},
                                    "signal": {"type": "string"},
                                    "confidence": {"type": "number"},
                                },
                            },
                            "description": "Breakdown by strategy",
                        },
                    },
                    "required": [
                        "symbol",
                        "action",
                        "confidence",
                        "reasoning",
                        "strategy_breakdown",
                    ],
                },
            ),
            Tool(
                name="log_decision",
                description="Log an agent decision for a signal.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "signal_id": {
                            "type": "string",
                            "description": "UUID of the signal",
                        },
                        "score": {
                            "type": "number",
                            "description": "Decision score",
                        },
                        "tier": {
                            "type": "string",
                            "description": "Decision tier",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Decision reasoning",
                        },
                        "tool_calls": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Tool calls made during decision",
                        },
                        "model_used": {
                            "type": "string",
                            "description": "Model used for decision",
                        },
                        "latency_ms": {
                            "type": "integer",
                            "description": "Latency in milliseconds",
                        },
                        "tokens": {
                            "type": "integer",
                            "description": "Tokens used",
                        },
                    },
                    "required": [
                        "signal_id",
                        "score",
                        "tier",
                        "reasoning",
                        "tool_calls",
                        "model_used",
                        "latency_ms",
                        "tokens",
                    ],
                },
            ),
            Tool(
                name="get_recent_signals",
                description="Get recent trading signals with optional filters.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Filter by symbol (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "description": "Max results to return",
                        },
                        "min_score": {
                            "type": "number",
                            "description": "Minimum decision score filter (optional)",
                        },
                        "force_refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": "Bypass cache and fetch fresh data",
                        },
                    },
                },
            ),
            Tool(
                name="get_paper_pnl",
                description="Get aggregated simulated P&L from signals.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Filter by symbol (optional)",
                        },
                    },
                },
            ),
            Tool(
                name="get_signal_accuracy",
                description="Get signal accuracy metrics for a lookback window.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lookback_hours": {
                            "type": "integer",
                            "default": 24,
                            "description": "Lookback window in hours",
                        },
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        start = time.monotonic()
        force_refresh = arguments.get("force_refresh", False)

        try:
            if name == "emit_signal":
                signal_id = await postgres_client.insert_signal(
                    symbol=arguments["symbol"],
                    action=arguments["action"],
                    confidence=arguments["confidence"],
                    reasoning=arguments["reasoning"],
                    strategy_breakdown=arguments["strategy_breakdown"],
                )
                signal_data = {
                    "signal_id": signal_id,
                    "symbol": arguments["symbol"],
                    "action": arguments["action"],
                    "confidence": arguments["confidence"],
                    "reasoning": arguments["reasoning"],
                    "strategy_breakdown": arguments["strategy_breakdown"],
                }
                redis_client.publish_signal(arguments["symbol"], signal_data)
                return wrap_response(
                    {"signal_id": signal_id},
                    start_time=start,
                    source="postgresql",
                )

            elif name == "log_decision":
                decision_id = await postgres_client.insert_decision(
                    signal_id=arguments["signal_id"],
                    score=arguments["score"],
                    tier=arguments["tier"],
                    reasoning=arguments["reasoning"],
                    tool_calls=arguments["tool_calls"],
                    model_used=arguments["model_used"],
                    latency_ms=arguments["latency_ms"],
                    tokens_used=arguments["tokens"],
                )
                return wrap_response(
                    {"decision_id": decision_id},
                    start_time=start,
                    source="postgresql",
                )

            elif name == "get_recent_signals":
                cache_key = f"signals:{arguments.get('symbol', '')}:{arguments.get('limit', 20)}:{arguments.get('min_score', '')}"
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
                signals = await postgres_client.get_recent_signals(
                    symbol=arguments.get("symbol"),
                    limit=arguments.get("limit", 20),
                    min_score=arguments.get("min_score"),
                )
                cache.set(cache_key, signals, ttl=30.0)
                return wrap_response(signals, start_time=start, source="postgresql")

            elif name == "get_paper_pnl":
                pnl = await postgres_client.get_paper_pnl(
                    symbol=arguments.get("symbol"),
                )
                return wrap_response(pnl, start_time=start, source="postgresql")

            elif name == "get_signal_accuracy":
                accuracy = await postgres_client.get_signal_accuracy(
                    lookback_hours=arguments.get("lookback_hours", 24),
                )
                return wrap_response(accuracy, start_time=start, source="postgresql")

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
