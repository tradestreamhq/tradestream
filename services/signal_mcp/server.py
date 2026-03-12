"""
MCP server for the signal service.
Exposes tools for signal emission, decision logging, analytics,
signal audit trail, and signal replay.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from services.signal_mcp.audit_recorder import AuditRecorder
from services.signal_mcp.postgres_client import PostgresClient
from services.signal_mcp.redis_client import RedisClient
from services.signal_mcp.signal_replayer import SignalReplayer


def create_server(
    postgres_client: PostgresClient,
    redis_client: RedisClient,
    audit_recorder: Optional[AuditRecorder] = None,
    signal_replayer: Optional[SignalReplayer] = None,
) -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("signal-mcp")

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
            Tool(
                name="get_audit_log",
                description="Get signal audit trail events for debugging. Returns timestamped, sequenced signal events.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Filter by symbol (optional)",
                        },
                        "start_time": {
                            "type": "string",
                            "description": "ISO 8601 start time (optional)",
                        },
                        "end_time": {
                            "type": "string",
                            "description": "ISO 8601 end time (optional)",
                        },
                        "event_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by event types: SIGNAL_EMITTED, SIGNAL_SKIPPED, DECISION_LOGGED (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 100,
                            "description": "Max results to return",
                        },
                    },
                },
            ),
            Tool(
                name="replay_signals",
                description="Replay signal sequences from a time range for debugging. Compares replay results with original outcomes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "start_time": {
                            "type": "string",
                            "description": "ISO 8601 start time",
                        },
                        "end_time": {
                            "type": "string",
                            "description": "ISO 8601 end time",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Filter by symbol (optional)",
                        },
                    },
                    "required": ["start_time", "end_time"],
                },
            ),
            Tool(
                name="get_replay_result",
                description="Get the result of a previous signal replay session.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "replay_group_id": {
                            "type": "string",
                            "description": "UUID of the replay session",
                        },
                    },
                    "required": ["replay_group_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        import json

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

            if audit_recorder:
                await audit_recorder.record_signal_emitted(
                    signal_id=signal_id,
                    symbol=arguments["symbol"],
                    action=arguments["action"],
                    confidence=arguments["confidence"],
                    reasoning=arguments["reasoning"],
                    strategy_breakdown=arguments["strategy_breakdown"],
                )

            return [
                TextContent(
                    type="text",
                    text=json.dumps({"signal_id": signal_id}),
                )
            ]

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

            if audit_recorder:
                await audit_recorder.record_decision_logged(
                    signal_id=arguments["signal_id"],
                    symbol="unknown",
                    model_used=arguments["model_used"],
                    tool_calls=arguments["tool_calls"],
                )

            return [
                TextContent(
                    type="text",
                    text=json.dumps({"decision_id": decision_id}),
                )
            ]

        elif name == "get_recent_signals":
            signals = await postgres_client.get_recent_signals(
                symbol=arguments.get("symbol"),
                limit=arguments.get("limit", 20),
                min_score=arguments.get("min_score"),
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(signals, default=str),
                )
            ]

        elif name == "get_paper_pnl":
            pnl = await postgres_client.get_paper_pnl(
                symbol=arguments.get("symbol"),
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(pnl),
                )
            ]

        elif name == "get_signal_accuracy":
            accuracy = await postgres_client.get_signal_accuracy(
                lookback_hours=arguments.get("lookback_hours", 24),
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(accuracy),
                )
            ]

        elif name == "get_audit_log":
            if not audit_recorder:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Audit recorder not configured"}),
                    )
                ]

            start_time = None
            end_time = None
            if arguments.get("start_time"):
                start_time = datetime.fromisoformat(arguments["start_time"])
            if arguments.get("end_time"):
                end_time = datetime.fromisoformat(arguments["end_time"])

            events = await audit_recorder.get_events(
                symbol=arguments.get("symbol"),
                start_time=start_time,
                end_time=end_time,
                event_types=arguments.get("event_types"),
                limit=arguments.get("limit", 100),
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(events, default=str),
                )
            ]

        elif name == "replay_signals":
            if not signal_replayer:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Signal replayer not configured"}),
                    )
                ]

            start_time = datetime.fromisoformat(arguments["start_time"])
            end_time = datetime.fromisoformat(arguments["end_time"])

            summary = await signal_replayer.replay(
                start_time=start_time,
                end_time=end_time,
                symbol=arguments.get("symbol"),
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(summary.to_dict(), default=str),
                )
            ]

        elif name == "get_replay_result":
            if not signal_replayer:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Signal replayer not configured"}),
                    )
                ]

            result = await signal_replayer.get_replay_summary(
                arguments["replay_group_id"],
            )

            if result is None:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Replay session not found"}),
                    )
                ]

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
