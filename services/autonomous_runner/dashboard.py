"""Pipeline dashboard API: real-time view of pipeline status, signal flow, and decision log.

Provides REST and SSE endpoints for monitoring the autonomous signal generation pipeline.
"""

import asyncio
import json
import logging
import time
import uuid
from collections import Counter
from typing import Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.autonomous_runner.signal_event_bus import get_event_bus

logger = logging.getLogger(__name__)


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


app = FastAPI(
    title="Autonomous Signal Pipeline Dashboard",
    version="1.1.0",
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
        components["event_bus"] = get_event_bus().get_stats()

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


@app.get("/api/pipeline/stream")
async def signal_stream(
    request: Request,
    last_event_id: int = Query(default=0, ge=0),
):
    """Server-Sent Events stream for real-time signal updates.

    Publishes signals continuously even with no users connected (the event bus
    buffers events). New connections can replay missed events via last_event_id.
    """
    event_bus = get_event_bus()

    async def event_generator():
        queue = asyncio.Queue(maxsize=100)
        subscriber_id = f"sse-{uuid.uuid4().hex[:8]}"

        def on_event(event):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop oldest if consumer is slow

        # Replay missed events
        replay = event_bus.get_replay_buffer(since_id=last_event_id)
        for event in replay:
            yield _format_sse(event)

        # Subscribe for live events
        event_bus.subscribe(subscriber_id, on_event)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield _format_sse(event)
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(event: dict) -> str:
    """Format an event as SSE data."""
    event_id = event.get("id", "")
    event_type = event.get("type", "signal")
    data = json.dumps(event.get("data", {}))
    return f"id: {event_id}\nevent: {event_type}\ndata: {data}\n\n"


@app.get("/api/pipeline/analytics/decisions")
def decision_analytics():
    """Aggregated decision analytics: action distribution, confidence stats, tier distribution."""
    if not _state.coordinator:
        return {"error": "Coordinator not initialized"}

    decisions = _state.coordinator.get_recent_decisions(limit=200)
    if not decisions:
        return {
            "total": 0,
            "action_distribution": {},
            "confidence_stats": {},
            "opportunity_tiers": {},
        }

    actions = Counter(d.get("action", "HOLD") for d in decisions)
    confidences = [d.get("confidence", 0) for d in decisions]

    # Opportunity tier distribution
    tiers = Counter()
    for d in decisions:
        score = d.get("opportunity_score", 0) or 0
        if score >= 80:
            tiers["HOT"] += 1
        elif score >= 60:
            tiers["GOOD"] += 1
        elif score >= 40:
            tiers["NEUTRAL"] += 1
        else:
            tiers["LOW"] += 1

    # Risk rejection analysis
    rejected = [d for d in decisions if not d.get("risk_approved", True)]
    rejection_reasons = Counter()
    for d in rejected:
        for reason in d.get("risk_rejection_reasons", []):
            rejection_reasons[reason] += 1

    return {
        "total": len(decisions),
        "action_distribution": dict(actions),
        "confidence_stats": {
            "mean": sum(confidences) / len(confidences) if confidences else 0,
            "min": min(confidences) if confidences else 0,
            "max": max(confidences) if confidences else 0,
        },
        "opportunity_tiers": dict(tiers),
        "risk_rejections": {
            "total_rejected": len(rejected),
            "rejection_reasons": dict(rejection_reasons),
        },
    }


@app.get("/api/pipeline/analytics/signals")
def signal_analytics(symbol: Optional[str] = Query(default=None)):
    """Per-symbol signal history and agreement analysis."""
    if not _state.coordinator:
        return {"error": "Coordinator not initialized"}

    decisions = _state.coordinator.get_recent_decisions(limit=200)

    if symbol:
        decisions = [d for d in decisions if d.get("symbol") == symbol]

    # Group by symbol
    by_symbol = {}
    for d in decisions:
        sym = d.get("symbol", "unknown")
        if sym not in by_symbol:
            by_symbol[sym] = {
                "count": 0,
                "actions": Counter(),
                "avg_confidence": 0,
                "avg_agreement": 0,
                "approved": 0,
                "rejected": 0,
            }
        entry = by_symbol[sym]
        entry["count"] += 1
        entry["actions"][d.get("action", "HOLD")] += 1
        entry["avg_confidence"] += d.get("confidence", 0)
        entry["avg_agreement"] += d.get("fusion_agreement_ratio", 0) or 0
        if d.get("risk_approved", False):
            entry["approved"] += 1
        else:
            entry["rejected"] += 1

    # Compute averages
    for sym, entry in by_symbol.items():
        count = entry["count"]
        if count > 0:
            entry["avg_confidence"] = round(entry["avg_confidence"] / count, 4)
            entry["avg_agreement"] = round(entry["avg_agreement"] / count, 4)
        entry["actions"] = dict(entry["actions"])

    return {"symbols": by_symbol, "total_symbols": len(by_symbol)}


@app.get("/api/pipeline/event-bus")
def event_bus_status():
    """Event bus statistics."""
    return get_event_bus().get_stats()


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
