"""Pipeline dashboard API: real-time view of pipeline status, signal flow, and decision log.

Provides REST endpoints for monitoring the autonomous signal generation pipeline.
"""

import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

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
    version="1.0.0",
)


class KillSwitchRequest(BaseModel):
    reason: str = ""
    activated_by: str = "api"


@app.get("/health")
def health():
    return {"status": "ok", "service": "autonomous-signal-pipeline"}


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
