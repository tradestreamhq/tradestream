"""
Agent Gateway Service

FastAPI application that streams agent events (signals, reasoning, tool calls)
via Server-Sent Events (SSE). Reads from agent_decisions table and uses Redis
pub/sub for real-time event streaming. Provides dashboard summary endpoints
for monitoring active agents, recent decisions, and signal activity.

Implements the full agent-gateway spec:
- Session management with unique session IDs
- Command endpoint for submitting user queries
- Rate limiting per IP
- Backpressure handling and slow consumer detection
- Heartbeat events every 30 seconds
- Event ordering with sequence numbers
- Last-Event-ID reconnection support
- Connection limits per IP (max 5)
"""

import asyncio
import collections
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Optional

import asyncpg
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REDIS_CHANNEL = "agent_events"
REDIS_CHANNELS = ["channel:signals", "channel:reasoning", "channel:tool-events"]

# Configuration
MAX_QUEUE_SIZE = 1000
BACKPRESSURE_THRESHOLD_PCT = 80
SLOW_CONSUMER_TIMEOUT_SECONDS = 30
SESSION_TIMEOUT_SECONDS = 300
SESSION_CLEANUP_INTERVAL_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 30
MAX_CONNECTIONS_PER_IP = 5
STREAM_CONNECTIONS_PER_MINUTE = 10
COMMANDS_PER_MINUTE = 60
HEALTH_REQUESTS_PER_MINUTE = 120

from services.shared.auth import fastapi_auth_middleware

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
    connections: int = Field(0, description="Active SSE connections", examples=[42])
    uptime_seconds: int = Field(
        0, description="Service uptime in seconds", examples=[3600]
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
        None,
        description="ISO 8601 timestamp",
        examples=["2026-01-15T10:30:00+00:00"],
    )


class RecentEventsResponse(BaseModel):
    events: list[AgentEvent] = Field(..., description="List of agent events")
    count: int = Field(..., description="Number of events returned", examples=[10])


class CommandRequest(BaseModel):
    session_id: str = Field(..., description="Session ID from SSE stream")
    query: str = Field(..., description="User query text")
    symbol: Optional[str] = Field(
        None, description="Trading symbol", examples=["ETH/USD"]
    )


class CommandResponse(BaseModel):
    request_id: str = Field(..., description="Unique request identifier")
    session_id: str = Field(..., description="Session ID")
    status: str = Field(..., description="Processing status", examples=["processing"])
    message: str = Field(..., description="Status message")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://dashboard.tradestream.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connection pools (initialized on startup)
_db_pool: Optional[asyncpg.Pool] = None
_redis: Optional[aioredis.Redis] = None
_start_time: float = 0.0

# --- Session Management ---


class SessionManager:
    """Manages SSE sessions with per-session event queues."""

    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    def create_session(self) -> str:
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        self.sessions[session_id] = {
            "created_at": time.monotonic(),
            "last_activity": time.monotonic(),
            "sequence": 0,
            "queue": asyncio.Queue(maxsize=MAX_QUEUE_SIZE),
            "backpressure_since": None,
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        session = self.sessions.get(session_id)
        if session:
            session["last_activity"] = time.monotonic()
        return session

    def remove_session(self, session_id: str):
        self.sessions.pop(session_id, None)

    def next_sequence(self, session_id: str) -> int:
        session = self.sessions.get(session_id)
        if session:
            session["sequence"] += 1
            return session["sequence"]
        return 0

    def active_count(self) -> int:
        return len(self.sessions)

    async def start_cleanup(self):
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL_SECONDS)
            now = time.monotonic()
            to_remove = []
            for sid, session in self.sessions.items():
                if now - session["last_activity"] > SESSION_TIMEOUT_SECONDS:
                    to_remove.append(sid)
            for sid in to_remove[:100]:  # Max 100 per cycle
                self.remove_session(sid)
                logger.info("Cleaned up inactive session %s", sid)


session_manager = SessionManager()


# --- Rate Limiting ---


class RateLimiter:
    """Simple in-memory rate limiter per IP."""

    def __init__(self):
        # {endpoint: {ip: [(timestamp, ...)]}}
        self._windows: dict[str, dict[str, list[float]]] = {}

    def check(self, endpoint: str, ip: str, limit: int, window: int = 60) -> dict:
        """Check rate limit. Returns dict with allowed, remaining, reset."""
        now = time.time()
        key = f"{endpoint}"
        if key not in self._windows:
            self._windows[key] = {}
        if ip not in self._windows[key]:
            self._windows[key][ip] = []

        # Prune old entries
        cutoff = now - window
        self._windows[key][ip] = [t for t in self._windows[key][ip] if t > cutoff]

        count = len(self._windows[key][ip])
        remaining = max(0, limit - count)
        reset = int(now + window)

        if count >= limit:
            return {
                "allowed": False,
                "limit": limit,
                "remaining": 0,
                "reset": reset,
            }

        self._windows[key][ip].append(now)
        return {
            "allowed": True,
            "limit": limit,
            "remaining": remaining - 1,
            "reset": reset,
        }


rate_limiter = RateLimiter()


# --- Connection Tracking ---


class ConnectionTracker:
    """Track active SSE connections per IP."""

    def __init__(self, max_per_ip: int = MAX_CONNECTIONS_PER_IP):
        self.max_per_ip = max_per_ip
        self._connections: dict[str, int] = {}

    def can_connect(self, ip: str) -> bool:
        return self._connections.get(ip, 0) < self.max_per_ip

    def add(self, ip: str):
        self._connections[ip] = self._connections.get(ip, 0) + 1

    def remove(self, ip: str):
        count = self._connections.get(ip, 0)
        if count <= 1:
            self._connections.pop(ip, None)
        else:
            self._connections[ip] = count - 1

    def count(self, ip: str) -> int:
        return self._connections.get(ip, 0)

    def total(self) -> int:
        return sum(self._connections.values())


connection_tracker = ConnectionTracker()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit_response(result: dict) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "message": "Too many requests"},
        headers={
            "X-RateLimit-Limit": str(result["limit"]),
            "X-RateLimit-Remaining": str(result["remaining"]),
            "X-RateLimit-Reset": str(result["reset"]),
        },
    )


def _get_db_dsn() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DATABASE", "")
    username = os.environ.get("POSTGRES_USERNAME", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    return f"postgresql://{username}:{password}@{host}:{port}/{database}"


def _get_redis_url() -> str:
    host = os.environ.get("REDIS_HOST", "localhost")
    port = os.environ.get("REDIS_PORT", "6379")
    return f"redis://{host}:{port}/0"


@app.on_event("startup")
async def startup():
    global _db_pool, _redis, _start_time
    _start_time = time.time()
    _db_pool = await asyncpg.create_pool(dsn=_get_db_dsn(), min_size=2, max_size=10)
    _redis = aioredis.from_url(_get_redis_url(), decode_responses=True)
    await session_manager.start_cleanup()
    logger.info("Agent Gateway started")


@app.on_event("shutdown")
async def shutdown():
    global _db_pool, _redis
    await session_manager.stop_cleanup()
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


async def _session_event_generator(
    session_id: str,
    agent_name: Optional[str] = None,
    event_type: Optional[str] = None,
    last_event_id: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """Generate SSE events with session management, heartbeats, and backpressure."""
    session = session_manager.get_session(session_id)
    if not session:
        return

    # Send session_start event
    seq = session_manager.next_sequence(session_id)
    yield {
        "event": "session_start",
        "id": f"{session_id}:{seq}",
        "data": json.dumps(
            {
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
    }

    # Determine resume point from Last-Event-ID
    resume_after = 0
    if last_event_id and ":" in last_event_id:
        try:
            resume_after = int(last_event_id.split(":")[-1])
        except (ValueError, IndexError):
            pass

    pubsub = _redis.pubsub()
    channels = [REDIS_CHANNEL] + REDIS_CHANNELS
    await pubsub.subscribe(*channels)
    last_heartbeat = time.monotonic()

    try:
        while True:
            session = session_manager.get_session(session_id)
            if not session:
                break

            # Heartbeat check
            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                last_heartbeat = now
                seq = session_manager.next_sequence(session_id)
                yield {
                    "event": "heartbeat",
                    "id": f"{session_id}:{seq}",
                    "data": json.dumps(
                        {"timestamp": datetime.now(timezone.utc).isoformat()}
                    ),
                }

            # Check backpressure
            queue = session["queue"]
            queue_pct = (queue.qsize() / MAX_QUEUE_SIZE * 100) if MAX_QUEUE_SIZE else 0
            if queue_pct >= BACKPRESSURE_THRESHOLD_PCT:
                if session["backpressure_since"] is None:
                    session["backpressure_since"] = time.monotonic()
                    seq = session_manager.next_sequence(session_id)
                    yield {
                        "event": "backpressure_warning",
                        "id": f"{session_id}:{seq}",
                        "data": json.dumps(
                            {
                                "queue_size": queue.qsize(),
                                "queue_max": MAX_QUEUE_SIZE,
                                "message": "Event queue nearing capacity",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        ),
                    }
                elif (
                    time.monotonic() - session["backpressure_since"]
                    > SLOW_CONSUMER_TIMEOUT_SECONDS
                ):
                    # Slow consumer - disconnect
                    seq = session_manager.next_sequence(session_id)
                    yield {
                        "event": "error",
                        "id": f"{session_id}:{seq}",
                        "data": json.dumps(
                            {
                                "error_code": "slow_consumer",
                                "message": "Disconnected due to sustained backpressure",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        ),
                    }
                    break
            else:
                session["backpressure_since"] = None

            # Poll for Redis messages with timeout
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                message = None

            if message and message.get("type") == "message":
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue

                # Apply filters
                if agent_name and data.get("agent_name") != agent_name:
                    continue
                if event_type and data.get("event_type") != event_type:
                    continue

                seq = session_manager.next_sequence(session_id)
                if seq <= resume_after:
                    continue

                evt_type = data.get("event_type", "message")
                yield {
                    "event": evt_type,
                    "id": f"{session_id}:{seq}",
                    "data": json.dumps(data),
                }
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()


async def _event_generator(
    agent_name: Optional[str] = None,
    event_type: Optional[str] = None,
) -> AsyncGenerator[dict, None]:
    """Generate SSE events from Redis pub/sub (legacy non-session mode)."""
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


# --- Spec Endpoints ---


@app.get(
    "/api/agent/stream",
    tags=["Agent"],
    response_class=EventSourceResponse,
)
async def agent_stream(
    request: Request,
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """SSE stream endpoint per spec.

    Creates a new session and streams events with session IDs, sequence
    numbers, heartbeats, and backpressure handling. Supports reconnection
    via Last-Event-ID header.
    """
    client_ip = _get_client_ip(request)

    # Check connection limit
    if not connection_tracker.can_connect(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "connection_limit_exceeded",
                "message": f"Maximum {MAX_CONNECTIONS_PER_IP} connections per IP",
            },
        )

    # Check rate limit
    rl = rate_limiter.check("stream", client_ip, STREAM_CONNECTIONS_PER_MINUTE)
    if not rl["allowed"]:
        return _rate_limit_response(rl)

    session_id = session_manager.create_session()
    connection_tracker.add(client_ip)

    async def generate():
        try:
            async for event in _session_event_generator(
                session_id,
                agent_name=agent_name,
                event_type=event_type,
                last_event_id=last_event_id,
            ):
                yield event
        finally:
            connection_tracker.remove(client_ip)
            session_manager.remove_session(session_id)

    return EventSourceResponse(generate())


@app.post(
    "/api/agent/command",
    response_model=CommandResponse,
    tags=["Agent"],
)
async def agent_command(request: Request, body: CommandRequest):
    """Submit a user query to the agent.

    The session_id must come from a prior SSE connection. Events from
    processing this command will stream on the SSE connection associated
    with the session.
    """
    client_ip = _get_client_ip(request)

    # Rate limit
    rl = rate_limiter.check("command", client_ip, COMMANDS_PER_MINUTE)
    if not rl["allowed"]:
        return _rate_limit_response(rl)

    # Validate session
    session = session_manager.get_session(body.session_id)
    if not session:
        return JSONResponse(
            status_code=400,
            content={
                "error": "missing_session_id",
                "message": "Invalid or expired session_id. Connect to /api/agent/stream first.",
            },
        )

    request_id = f"req-{uuid.uuid4().hex[:12]}"

    # Publish command to Redis for agent processing
    if _redis:
        await _redis.publish(
            "agent_commands",
            json.dumps(
                {
                    "request_id": request_id,
                    "session_id": body.session_id,
                    "query": body.query,
                    "symbol": body.symbol,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )

    return CommandResponse(
        request_id=request_id,
        session_id=body.session_id,
        status="processing",
        message="Query submitted. Events will stream on /api/agent/stream",
    )


@app.get(
    "/api/agent/health",
    response_model=HealthResponse,
    tags=["Agent"],
)
async def agent_health(request: Request):
    """Health check endpoint per spec.

    Returns service status with connection count and Redis connectivity.
    """
    client_ip = _get_client_ip(request)
    rl = rate_limiter.check("health", client_ip, HEALTH_REQUESTS_PER_MINUTE)
    if not rl["allowed"]:
        return _rate_limit_response(rl)

    checks = {
        "status": "healthy",
        "service": "agent-gateway",
        "connections": connection_tracker.total(),
        "uptime_seconds": int(time.time() - _start_time),
    }

    try:
        async with _db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"

    try:
        await _redis.ping()
        checks["redis"] = "connected"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "healthy" else 503
    return JSONResponse(content=checks, status_code=status_code)


# --- Legacy Endpoints (backwards compatible) ---


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
    checks = {
        "status": "healthy",
        "service": "agent-gateway",
        "connections": connection_tracker.total(),
        "uptime_seconds": int(time.time() - _start_time),
    }

    try:
        async with _db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {e}"
        checks["status"] = "degraded"

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
    port = int(os.environ.get("API_PORT", "8081"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
