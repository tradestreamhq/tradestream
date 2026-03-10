"""
Agent Gateway Service

FastAPI application that streams agent events (signals, reasoning, tool calls)
via Server-Sent Events (SSE). Reads from agent_decisions table and uses Redis
pub/sub for real-time event streaming. Also provides a chat endpoint for
natural language queries about signals and agent activity.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Optional

import asyncpg
import httpx
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_CHANNEL = "agent_events"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
CHAT_MODEL = os.environ.get("CHAT_MODEL", "google/gemini-2.0-flash-001")
CHAT_MAX_CONTEXT_EVENTS = 50

app = FastAPI(title="Agent Gateway", version="1.0.0")


class ChatRequest(BaseModel):
    """Request body for the /chat endpoint."""

    question: str = Field(..., min_length=1, max_length=2000)
    context_window: int = Field(
        default=50, ge=1, le=200, description="Number of recent events to include"
    )


# Connection pools (initialized on startup)
_db_pool: Optional[asyncpg.Pool] = None
_redis: Optional[aioredis.Redis] = None


def _get_db_dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DATABASE", "tradestream")
    username = os.environ.get("POSTGRES_USERNAME", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    return f"postgresql://{username}:{password}@{host}:{port}/{database}"


def _get_redis_url() -> str:
    host = os.environ.get("REDIS_HOST", "localhost")
    port = os.environ.get("REDIS_PORT", "6379")
    return f"redis://{host}:{port}/0"


@app.on_event("startup")
async def startup():
    global _db_pool, _redis
    _db_pool = await asyncpg.create_pool(dsn=_get_db_dsn(), min_size=2, max_size=10)
    _redis = aioredis.from_url(_get_redis_url(), decode_responses=True)
    logger.info("Agent Gateway started")


@app.on_event("shutdown")
async def shutdown():
    global _db_pool, _redis
    if _db_pool:
        await _db_pool.close()
    if _redis:
        await _redis.aclose()
    logger.info("Agent Gateway stopped")


def _serialize_row(row: asyncpg.Record) -> dict:
    """Convert a database row to a JSON-serializable dict."""
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
    return result


def _row_to_event(row: dict) -> dict:
    """Convert a database row dict to an SSE event payload."""
    event_type = "decision"
    if row.get("reasoning"):
        event_type = "reasoning"
    if row.get("tool_calls"):
        event_type = "tool_call"
    if row.get("signal_id"):
        event_type = "signal"

    return {
        "event_type": event_type,
        "id": row.get("id"),
        "signal_id": row.get("signal_id"),
        "agent_name": row.get("agent_name"),
        "decision_type": row.get("decision_type"),
        "score": row.get("score"),
        "tier": row.get("tier"),
        "reasoning": row.get("reasoning"),
        "tool_calls": row.get("tool_calls"),
        "model_used": row.get("model_used"),
        "latency_ms": row.get("latency_ms"),
        "tokens_used": row.get("tokens_used"),
        "success": row.get("success"),
        "error_message": row.get("error_message"),
        "created_at": row.get("created_at"),
    }


async def _event_generator(
    agent_name: Optional[str] = None,
    event_type: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """Generate SSE events from Redis pub/sub."""
    pubsub = _redis.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            # Apply filters
            if agent_name and data.get("agent_name") != agent_name:
                continue
            if event_type and data.get("event_type") != event_type:
                continue

            yield data
    finally:
        await pubsub.unsubscribe(REDIS_CHANNEL)
        await pubsub.aclose()


@app.get("/health")
async def health():
    """Health check endpoint."""
    checks = {"status": "healthy", "service": "agent-gateway"}

    # Check database connectivity
    try:
        async with _db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"

    # Check Redis connectivity
    try:
        await _redis.ping()
        checks["redis"] = "connected"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.get("/events/stream")
async def stream_events(
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    event_type: Optional[str] = Query(
        None,
        description="Filter by event type (signal, reasoning, tool_call, decision)",
    ),
):
    """Stream agent events via Server-Sent Events."""

    async def generate():
        async for event in _event_generator(
            agent_name=agent_name, event_type=event_type
        ):
            yield {
                "event": event.get("event_type", "message"),
                "data": json.dumps(event),
            }

    return EventSourceResponse(generate())


@app.get("/events/recent")
async def get_recent_events(
    limit: int = Query(50, ge=1, le=500, description="Number of events to return"),
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
):
    """Get recent agent events from the database."""
    query = "SELECT * FROM agent_decisions WHERE 1=1"
    params = []
    param_idx = 0

    if agent_name:
        param_idx += 1
        query += f" AND agent_name = ${param_idx}"
        params.append(agent_name)

    if event_type:
        if event_type == "signal":
            query += " AND signal_id IS NOT NULL"
        elif event_type == "reasoning":
            query += " AND reasoning IS NOT NULL"
        elif event_type == "tool_call":
            query += " AND tool_calls IS NOT NULL"

    param_idx += 1
    query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
    params.append(limit)

    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    events = [_row_to_event(_serialize_row(row)) for row in rows]
    return {"events": events, "count": len(events)}


async def publish_event(event: dict):
    """Publish an event to Redis pub/sub (used by agents to push events)."""
    if _redis:
        await _redis.publish(REDIS_CHANNEL, json.dumps(event))


async def _gather_chat_context(context_window: int) -> str:
    """Gather recent signals and agent activity for chat context."""
    query = """
        SELECT agent_name, decision_type, score, tier, reasoning,
               tool_calls, model_used, latency_ms, success, error_message,
               created_at
        FROM agent_decisions
        ORDER BY created_at DESC
        LIMIT $1
    """
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(query, min(context_window, CHAT_MAX_CONTEXT_EVENTS))

    if not rows:
        return "No recent agent activity found."

    lines = []
    for row in rows:
        row_dict = _serialize_row(row)
        parts = []
        if row_dict.get("created_at"):
            parts.append(f"[{row_dict['created_at']}]")
        if row_dict.get("agent_name"):
            parts.append(f"agent={row_dict['agent_name']}")
        if row_dict.get("tier"):
            parts.append(f"tier={row_dict['tier']}")
        if row_dict.get("score") is not None:
            parts.append(f"score={row_dict['score']}")
        if row_dict.get("decision_type"):
            parts.append(f"type={row_dict['decision_type']}")
        if row_dict.get("success") is not None:
            parts.append(f"success={row_dict['success']}")
        if row_dict.get("reasoning"):
            reasoning = row_dict["reasoning"][:200]
            parts.append(f"reasoning={reasoning}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)


CHAT_SYSTEM_PROMPT = """You are a trading assistant for TradeStream, an AI-powered \
crypto trading platform. You answer questions about recent signals, agent activity, \
strategies, and market conditions based on the context provided.

Rules:
- Only answer based on the context provided. If you don't have enough data, say so.
- You are READ-ONLY: never suggest executing trades or modifying system state.
- Be concise and use trading terminology appropriately.
- When discussing signals, reference their tier (HOT/WARM/COLD), score, and agent name.
- Format numbers clearly (percentages, scores, timestamps).
"""


@app.post("/chat")
async def chat(request: ChatRequest):
    """Answer natural language questions about signals and agent activity via SSE."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return JSONResponse(
            status_code=503,
            content={"error": "Chat service not configured (missing API key)"},
        )

    try:
        context = await _gather_chat_context(request.context_window)
    except Exception as e:
        logger.error("Failed to gather chat context: %s", e)
        context = "Unable to fetch recent activity."

    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Recent agent activity:\n{context}",
        },
        {"role": "user", "content": request.question},
    ]

    async def generate():
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": CHAT_MODEL,
                    "messages": messages,
                    "stream": True,
                    "max_tokens": 1024,
                },
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    yield {
                        "event": "chat_error",
                        "data": json.dumps(
                            {"error": f"LLM API error: {response.status_code}"}
                        ),
                    }
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        yield {
                            "event": "chat_done",
                            "data": json.dumps({"done": True}),
                        }
                        return
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield {
                                "event": "chat_response",
                                "data": json.dumps({"content": content}),
                            }
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    return EventSourceResponse(generate())


def main():
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
