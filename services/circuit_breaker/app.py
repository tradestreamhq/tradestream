"""
Circuit Breaker REST API — RMM Level 2.

Provides endpoints for monitoring circuit breaker status and
performing manual resets after trading halts.
"""

import logging
from typing import Optional

import asyncpg
from fastapi import FastAPI
from pydantic import BaseModel, Field

from services.circuit_breaker.breaker import CircuitBreaker
from services.circuit_breaker.models import ThresholdConfig
from services.circuit_breaker.monitor import DrawdownMonitor
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import error_response, success_response
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


class ResetRequest(BaseModel):
    acknowledged_by: str = Field(
        ..., min_length=1, description="Identifier of who is acknowledging the reset"
    )


def create_app(
    db_pool: asyncpg.Pool,
    thresholds: Optional[ThresholdConfig] = None,
    poll_interval: float = 10.0,
) -> FastAPI:
    """Create the Circuit Breaker API FastAPI application."""
    breaker = CircuitBreaker(thresholds=thresholds)
    monitor = DrawdownMonitor(
        breaker=breaker, db_pool=db_pool, poll_interval_seconds=poll_interval
    )

    app = FastAPI(
        title="Circuit Breaker API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/circuit-breaker",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("circuit-breaker", check_deps))

    @app.on_event("startup")
    async def startup():
        await monitor.start()

    @app.on_event("shutdown")
    async def shutdown():
        await monitor.stop()

    @app.get("/status", tags=["Circuit Breaker"])
    async def get_status():
        """Get current circuit breaker status."""
        state = breaker.state
        return success_response(
            {
                "level": state.level.value,
                "drawdown_pct": round(state.drawdown_pct, 6),
                "peak_equity": state.peak_equity,
                "current_equity": state.current_equity,
                "is_halted": state.is_halted,
                "halted_strategies": state.halted_strategies,
                "trading_allowed": not state.is_halted,
                "last_triggered_at": state.last_triggered_at,
                "reset_acknowledged": state.reset_acknowledged,
                "thresholds": {
                    "warning": breaker.thresholds.warning,
                    "halt": breaker.thresholds.halt,
                    "emergency": breaker.thresholds.emergency,
                },
                "recent_events": [
                    {
                        "level": e.level.value,
                        "drawdown_pct": round(e.drawdown_pct, 6),
                        "timestamp": e.timestamp,
                        "message": e.message,
                    }
                    for e in state.events[-10:]
                ],
            },
            "circuit_breaker_status",
        )

    @app.post("/reset", tags=["Circuit Breaker"])
    async def reset_breaker(body: ResetRequest):
        """Reset the circuit breaker after manual acknowledgment."""
        success = breaker.reset(body.acknowledged_by)
        if not success:
            return error_response(
                code="NOT_HALTED",
                message="Circuit breaker is not in a halted state",
                status_code=409,
            )
        state = breaker.state
        return success_response(
            {
                "level": state.level.value,
                "is_halted": state.is_halted,
                "trading_allowed": True,
                "reset_by": body.acknowledged_by,
            },
            "circuit_breaker_reset",
        )

    # Expose breaker and monitor for testing
    app.state.breaker = breaker
    app.state.monitor = monitor

    return app
