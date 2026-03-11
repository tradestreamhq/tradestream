"""
Agent Gateway Service

FastAPI application that streams agent events (signals, reasoning, tool calls)
via Server-Sent Events (SSE). Reads from agent_decisions table and uses Redis
pub/sub for real-time event streaming.
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
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from services.shared.config import get_postgres_dsn, get_redis_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_CHANNEL = "agent_events"

from services.shared.auth import fastapi_auth_middleware

app = FastAPI(title="Agent Gateway", version="1.0.0")
fastapi_auth_middleware(app)

# Connection pools (initialized on startup)
_db_pool: Optional[asyncpg.Pool] = None
_redis: Optional[aioredis.Redis] = None


@app.on_event("startup")
async def startup():
    global _db_pool, _redis
    _db_pool = await asyncpg.create_pool(
        dsn=get_postgres_dsn(), min_size=2, max_size=10
    )
    _redis = aioredis.from_url(get_redis_url(), decode_responses=True)
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


def main():
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
