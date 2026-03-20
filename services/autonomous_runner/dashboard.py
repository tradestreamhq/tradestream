"""Pipeline dashboard API: real-time view of pipeline status, signal flow, and decision log.

Provides REST endpoints and SSE stream for monitoring the autonomous signal
generation pipeline.
"""

import asyncio
import json
import logging
import time
from collections import deque
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SignalEventBus:
    """In-process event bus for broadcasting signals to SSE subscribers.

    Publishes signals to SSE stream even when no users are connected,
    buffering the last N events so new subscribers see recent history.
    """

    def __init__(self, buffer_size: int = 100):
        self._subscribers: list[asyncio.Queue] = []
        self._buffer: deque = deque(maxlen=buffer_size)

    def publish(self, event: dict):
        """Publish a signal event to all subscribers and the replay buffer."""
        self._buffer.append(event)
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to the event stream. Returns an asyncio.Queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        # Replay recent events
        for event in self._buffer:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                break
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)


# Module-level event bus for SSE streaming
_event_bus = SignalEventBus()


class DashboardState:
    """Shared state between the runner and the dashboard API."""

    def __init__(self):
        self.coordinator = None
        self.kill_switch = None
        self.runner_started_at = None
        self.last_cycle_at = None
        self.total_cycles = 0
        self.total_signals_emitted = 0
        self.last_cycle_duration_ms = 0
        self.last_cycle_signals = 0


_state = DashboardState()


def set_dashboard_state(coordinator=None, kill_switch=None, runner_started_at=None):
    """Set the shared state references (called from main runner)."""
    if coordinator:
        _state.coordinator = coordinator
    if kill_switch:
        _state.kill_switch = kill_switch
    if runner_started_at:
        _state.runner_started_at = runner_started_at


def record_cycle(duration_ms: int, signals_count: int):
    """Record a completed cycle for dashboard metrics."""
    _state.last_cycle_at = time.time()
    _state.total_cycles += 1
    _state.total_signals_emitted += signals_count
    _state.last_cycle_duration_ms = duration_ms
    _state.last_cycle_signals = signals_count


def publish_signal_event(decision_dict: dict):
    """Publish a signal decision to the SSE event bus."""
    event = {
        "type": "signal",
        "timestamp": time.time(),
        "data": decision_dict,
    }
    _event_bus.publish(event)


def get_event_bus() -> SignalEventBus:
    """Return the module-level event bus (for testing)."""
    return _event_bus


app = FastAPI(
    title="Autonomous Signal Pipeline Dashboard",
    version="1.0.0",
)


class KillSwitchRequest(BaseModel):
    reason: str = ""
    activated_by: str = "api"


@app.get("/health")
def health():
    return {"status": "ok", "service": "autonomous-signal-pipeline"}


@app.get("/health/live")
def health_live():
    """Liveness probe: service is running."""
    return {"status": "alive"}


@app.get("/health/ready")
def health_ready():
    """Readiness probe: service is ready to process signals."""
    ready = _state.coordinator is not None and _state.runner_started_at is not None
    if not ready:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "coordinator not initialized"},
        )
    return {"status": "ready"}


@app.get("/health/detailed")
def health_detailed():
    """Detailed health check with component status."""
    components = {
        "runner": {
            "status": "up" if _state.runner_started_at else "down",
            "started_at": _state.runner_started_at,
            "total_cycles": _state.total_cycles,
        },
        "coordinator": {
            "status": "up" if _state.coordinator else "down",
        },
        "kill_switch": {
            "status": "up" if _state.kill_switch else "unavailable",
        },
    }

    if _state.coordinator:
        status = _state.coordinator.get_pipeline_status()
        components["circuit_breaker"] = status.get("circuit_breaker", {})
        components["adaptive"] = status.get("adaptive", {})
        components["db_persistence"] = status.get("db_persistence", False)
        components["risk"] = _state.coordinator.risk_manager.get_status()

    all_up = all(
        c.get("status") in ("up", "unavailable", True)
        for c in components.values()
        if isinstance(c, dict) and "status" in c
    )
    return {
        "status": "healthy" if all_up else "degraded",
        "components": components,
    }


@app.get("/api/pipeline/status")
def pipeline_status():
    """Overall pipeline status."""
    status = {
        "running": _state.runner_started_at is not None,
        "started_at": _state.runner_started_at,
        "last_cycle_at": _state.last_cycle_at,
        "total_cycles": _state.total_cycles,
        "total_signals_emitted": _state.total_signals_emitted,
        "last_cycle_duration_ms": _state.last_cycle_duration_ms,
        "last_cycle_signals": _state.last_cycle_signals,
    }

    if _state.coordinator:
        status["pipeline"] = _state.coordinator.get_pipeline_status()

    if _state.kill_switch:
        status["kill_switch"] = _state.kill_switch.get_status()

    return status


@app.get("/api/pipeline/decisions")
def recent_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    symbol: Optional[str] = Query(default=None),
):
    """Recent autonomous decisions with full reasoning chains."""
    if not _state.coordinator:
        return {"decisions": [], "total": 0}

    decisions = _state.coordinator.get_recent_decisions(limit=limit)

    if symbol:
        decisions = [d for d in decisions if d.get("symbol") == symbol]

    return {"decisions": decisions, "total": len(decisions)}


@app.get("/api/pipeline/risk")
def risk_status():
    """Current risk management status."""
    if not _state.coordinator:
        return {"error": "Coordinator not initialized"}
    return _state.coordinator.risk_manager.get_status()


@app.post("/api/pipeline/kill-switch/activate")
def activate_kill_switch(req: KillSwitchRequest):
    """Activate the kill switch to pause autonomous generation."""
    if not _state.kill_switch:
        return {"error": "Kill switch not initialized"}
    success = _state.kill_switch.activate(
        reason=req.reason, activated_by=req.activated_by
    )
    return {"success": success, "status": _state.kill_switch.get_status()}


@app.post("/api/pipeline/kill-switch/deactivate")
def deactivate_kill_switch():
    """Deactivate the kill switch to resume autonomous generation."""
    if not _state.kill_switch:
        return {"error": "Kill switch not initialized"}
    success = _state.kill_switch.deactivate(deactivated_by="api")
    return {"success": success, "status": _state.kill_switch.get_status()}


@app.get("/api/pipeline/kill-switch")
def kill_switch_status():
    """Get current kill switch status."""
    if not _state.kill_switch:
        return {"active": False, "error": "Kill switch not initialized"}
    return _state.kill_switch.get_status()


@app.get("/api/pipeline/metrics")
def pipeline_metrics_endpoint():
    """Pipeline metrics summary."""
    from services.autonomous_runner.metrics import pipeline_metrics

    return pipeline_metrics.get_summary()


@app.get("/api/pipeline/signals/stream")
async def signal_stream():
    """SSE endpoint: streams trading signals in real-time.

    Publishes signals even with no users connected (buffered).
    New subscribers receive recent history via replay buffer.
    """
    from starlette.responses import StreamingResponse

    queue = _event_bus.subscribe()

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = json.dumps(event, default=str)
                    yield f"event: signal\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive to prevent connection timeout
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _event_bus.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/pipeline/signals/stream/status")
def stream_status():
    """SSE stream status: subscriber count and buffer depth."""
    return {
        "subscribers": _event_bus.subscriber_count,
        "buffer_size": _event_bus.buffer_size,
    }


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    try:
        from prometheus_client import generate_latest
        from starlette.responses import Response

        return Response(
            content=generate_latest(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    except ImportError:
        from services.autonomous_runner.metrics import pipeline_metrics

        return pipeline_metrics.get_summary()
