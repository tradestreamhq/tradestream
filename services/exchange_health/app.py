"""Exchange Health REST API — RMM Level 2.

Provides endpoints for monitoring exchange connectivity, latency, and rate limits.
"""

import logging
from typing import Optional

from fastapi import APIRouter, FastAPI

from services.exchange_health.monitor import ExchangeHealthMonitor
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(monitor: ExchangeHealthMonitor) -> FastAPI:
    """Create the Exchange Health API FastAPI application.

    Args:
        monitor: ExchangeHealthMonitor instance tracking exchange health.
    """
    app = FastAPI(
        title="Exchange Health API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/exchanges",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        summary = monitor.get_summary()
        return {"monitor": "ok" if summary["connected"] > 0 else "no exchanges connected"}

    app.include_router(create_health_router("exchange-health", check_deps))

    exchanges_router = APIRouter(prefix="/health", tags=["Exchange Health"])

    @exchanges_router.get("")
    async def get_health_summary():
        """Get aggregate health status for all exchanges."""
        summary = monitor.get_summary()
        return success_response(summary, "exchange-health-summary")

    @exchanges_router.get("/alerts")
    async def get_alerts():
        """Get recent health alerts."""
        alerts = [a.to_dict() for a in monitor.alerts]
        return collection_response(alerts, "alert")

    @exchanges_router.get("/{exchange_id}")
    async def get_exchange_health(exchange_id: str):
        """Get health details for a specific exchange."""
        health = monitor.get_exchange_health(exchange_id)
        if not health:
            return not_found("Exchange", exchange_id)
        return success_response(health.to_dict(), "exchange-health", resource_id=exchange_id)

    @exchanges_router.post("/{exchange_id}/check")
    async def trigger_check(exchange_id: str):
        """Trigger an immediate health check for an exchange."""
        health = monitor.get_exchange_health(exchange_id)
        if not health:
            return not_found("Exchange", exchange_id)
        await monitor.check_exchange(exchange_id)
        updated = monitor.get_exchange_health(exchange_id)
        return success_response(updated.to_dict(), "exchange-health", resource_id=exchange_id)

    app.include_router(exchanges_router)
    return app
