"""
Agent Gateway Service

FastAPI application that streams agent events (signals, reasoning, tool calls)
via Server-Sent Events (SSE). Reads from agent_decisions table and uses Redis
pub/sub for real-time event streaming. Provides dashboard summary endpoints
for monitoring active agents, recent decisions, and signal activity.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Optional

import asyncpg
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from services.shared.auth import fastapi_auth_middleware
from services.shared.credentials import PostgresConfig, RedisConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_CHANNEL = "agent_events"

_pg_config = PostgresConfig()
_redis_config = RedisConfig()

app = FastAPI(
    title="Agent Gateway",
    version="1.0.0",
    description=(
        "Streams agent events (signals, reasoning, tool calls, decisions) "
        "via Server-Sent Events and provides a REST API for recent event queries."
    ),
)
fastapi_auth_middleware(app)


# --- Response models for OpenAPI documentation ---


class HealthResponse(BaseModel):
    status: str = Field(
        ..., description="Service status: healthy or degraded", examples=["healthy"]
    )
    service: str = Field(..., description="Service name", examples=["agent-gateway"])
    database: str = Field(
        ..., description="Database connectivity status", examples=["connected"]
    )
    redis: str = Field(
        ..., description="Redis connectivity status", examples=["connected"]
    )


class AgentEvent(BaseModel):
    event_type: str = Field(..., description="Event type", examples=["signal"])
    id: Optional[str] = Field(None, description="Event ID")
    signal_id: Optional[str] = Field(None, description="Associated signal ID")
    agent_name: Optional[str] = Field(
        None, description="Name of the agent", examples=["signal-generator"]
    )
    decision_type: Optional[str] = Field(None, description="Decision type")
    score: Optional[float] = Field(None, description="Score (0-1)", examples=[0.85])
    tier: Optional[str] = Field(None, description="Signal tier", examples=["high"])
    reasoning: Optional[str] = Field(None, description="Agent reasoning text")
    tool_calls: Optional[str] = Field(None, description="Tool calls made by the agent")
    model_used: Optional[str] = Field(
        None, description="LLM model used", examples=["gpt-4"]
    )
    latency_ms: Optional[int] = Field(
        None, description="Processing latency in ms", examples=[150]
    )
    tokens_used: Optional[int] = Field(
        None, description="Token count used", examples=[500]
    )
    success: Optional[bool] = Field(None, description="Whether the event succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[str] = Field(
        None, description="ISO 8601 timestamp", examples=["2026-01-15T10:30:00+00:00"]
    )


class RecentEventsResponse(BaseModel):
    events: list[AgentEvent] = Field(..., description="List of agent events")
    count: int = Field(..., description="Number of events returned", examples=[10])


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connection pools (initialized on startup)
_db_pool: Optional[asyncpg.Pool] = None
_redis: Optional[aioredis.Redis] = None


@app.on_event("startup")
async def startup():
    global _db_pool, _redis
    _db_pool = await asyncpg.create_pool(dsn=_pg_config.dsn, min_size=2, max_size=10)
    _redis = aioredis.from_url(_redis_config.url, decode_responses=True)
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


@app.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
    tags=["Health"],
)
async def health():
    """Health check endpoint.

    Returns connectivity status for the database and Redis.
    Returns 503 if any dependency is unreachable.
    """
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


@app.get("/events/stream", tags=["Events"], response_class=EventSourceResponse)
async def stream_events(
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    event_type: Optional[str] = Query(
        None,
        description="Filter by event type (signal, reasoning, tool_call, decision)",
    ),
):
    """Stream agent events via Server-Sent Events.

    Opens a persistent SSE connection that pushes real-time agent events
    from the Redis pub/sub channel. Supports optional filtering by agent
    name and event type.
    """

    async def generate():
        async for event in _event_generator(
            agent_name=agent_name, event_type=event_type
        ):
            yield {
                "event": event.get("event_type", "message"),
                "data": json.dumps(event),
            }

    return EventSourceResponse(generate())


@app.get("/events/recent", response_model=RecentEventsResponse, tags=["Events"])
async def get_recent_events(
    limit: int = Query(50, ge=1, le=500, description="Number of events to return"),
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    event_type: Optional[str] = Query(
        None,
        description="Filter by event type (signal, reasoning, tool_call, decision)",
    ),
):
    """Get recent agent events from the database.

    Returns the most recent agent decision events, ordered by creation time
    descending. Supports filtering by agent name and event type.
    """
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


@app.get("/dashboard/summary")
async def get_dashboard_summary():
    """Get a high-level dashboard summary with active agents and decision stats."""
    async with _db_pool.acquire() as conn:
        active_agents = await conn.fetch(
            """
            SELECT agent_name,
                   COUNT(*) as decision_count,
                   MAX(created_at) as last_active,
                   AVG(latency_ms) as avg_latency_ms,
                   SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as success_count,
                   SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failure_count
            FROM agent_decisions
            WHERE created_at > NOW() - INTERVAL '5 minutes'
              AND agent_name IS NOT NULL
            GROUP BY agent_name
            ORDER BY last_active DESC
            """
        )

        stats_24h = await conn.fetchrow(
            """
            SELECT COUNT(*) as total_decisions,
                   COUNT(DISTINCT agent_name) as unique_agents,
                   AVG(latency_ms) as avg_latency_ms,
                   SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successes,
                   SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failures,
                   COUNT(DISTINCT signal_id) FILTER (WHERE signal_id IS NOT NULL) as signals_generated
            FROM agent_decisions
            WHERE created_at > NOW() - INTERVAL '24 hours'
            """
        )

        tier_dist = await conn.fetch(
            """
            SELECT tier, COUNT(*) as count
            FROM agent_decisions
            WHERE created_at > NOW() - INTERVAL '24 hours'
              AND tier IS NOT NULL
            GROUP BY tier
            ORDER BY count DESC
            """
        )

        recent_signals = await conn.fetch(
            """
            SELECT id, signal_id, agent_name, score, tier, reasoning,
                   model_used, latency_ms, tokens_used, success, created_at
            FROM agent_decisions
            WHERE signal_id IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 10
            """
        )

    agents_list = [_serialize_row(row) for row in active_agents]
    stats = _serialize_row(stats_24h) if stats_24h else {}
    tiers = {row["tier"]: row["count"] for row in tier_dist}
    signals = [_serialize_row(row) for row in recent_signals]

    return {
        "active_agents": agents_list,
        "stats_24h": stats,
        "tier_distribution": tiers,
        "recent_signals": signals,
    }


@app.get("/dashboard/agents")
async def get_agent_details(
    agent_name: Optional[str] = Query(None, description="Specific agent to query"),
):
    """Get detailed agent activity and performance metrics."""
    query = """
        SELECT agent_name,
               decision_type,
               COUNT(*) as total_decisions,
               AVG(latency_ms) as avg_latency_ms,
               MIN(latency_ms) as min_latency_ms,
               MAX(latency_ms) as max_latency_ms,
               AVG(tokens_used) as avg_tokens,
               SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successes,
               SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failures,
               MIN(created_at) as first_seen,
               MAX(created_at) as last_seen
        FROM agent_decisions
        WHERE agent_name IS NOT NULL
    """
    params = []
    param_idx = 0

    if agent_name:
        param_idx += 1
        query += f" AND agent_name = ${param_idx}"
        params.append(agent_name)

    query += (
        " GROUP BY agent_name, decision_type ORDER BY agent_name, total_decisions DESC"
    )

    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    agents = {}
    for row in rows:
        serialized = _serialize_row(row)
        name = serialized["agent_name"]
        if name not in agents:
            agents[name] = {
                "agent_name": name,
                "decision_types": [],
                "total_decisions": 0,
                "first_seen": serialized["first_seen"],
                "last_seen": serialized["last_seen"],
            }
        agents[name]["decision_types"].append(serialized)
        agents[name]["total_decisions"] += serialized["total_decisions"]
        if serialized["first_seen"] < agents[name]["first_seen"]:
            agents[name]["first_seen"] = serialized["first_seen"]
        if serialized["last_seen"] > agents[name]["last_seen"]:
            agents[name]["last_seen"] = serialized["last_seen"]

    return {"agents": list(agents.values())}


@app.get("/dashboard/signals")
async def get_signal_activity(
    hours: int = Query(24, ge=1, le=168, description="Lookback period in hours"),
    limit: int = Query(100, ge=1, le=500, description="Max signals to return"),
):
    """Get signal activity with scoring details for the dashboard."""
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, signal_id, agent_name, score, tier,
                   reasoning, tool_calls, model_used, latency_ms,
                   tokens_used, decision_type, success,
                   error_message, created_at
            FROM agent_decisions
            WHERE created_at > NOW() - make_interval(hours => $1)
            ORDER BY created_at DESC
            LIMIT $2
            """,
            hours,
            limit,
        )

    events = [_row_to_event(_serialize_row(row)) for row in rows]
    return {"signals": events, "count": len(events), "hours": hours}


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
