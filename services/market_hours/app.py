"""Market Hours REST API — GET /api/v1/market-hours/{exchange}."""

import logging

from fastapi import APIRouter, FastAPI

from services.market_hours.calendar import get_holidays
from services.market_hours.models import MarketPhase
from services.market_hours.schedule import SCHEDULES, get_current_phase
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import not_found, success_response
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create the Market Hours API FastAPI application."""
    app = FastAPI(
        title="Market Hours API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/market-hours",
    )
    fastapi_auth_middleware(app)
    app.include_router(create_health_router("market-hours"))

    router = APIRouter(tags=["Market Hours"])

    @router.get("/exchanges")
    async def list_exchanges():
        """List supported exchanges."""
        items = [
            {"exchange": code, "timezone": sched.timezone}
            for code, sched in SCHEDULES.items()
        ]
        return {"data": items}

    @router.get("/{exchange}")
    async def get_market_hours(exchange: str):
        """Get current market status for an exchange."""
        exchange = exchange.upper()
        if exchange not in SCHEDULES:
            return not_found("Exchange", exchange)

        status = get_current_phase(exchange)
        return success_response(
            {
                "exchange": status.exchange,
                "phase": status.phase.value,
                "is_open": status.is_open,
                "current_session_start": status.current_session_start,
                "current_session_end": status.current_session_end,
                "is_holiday": status.is_holiday,
                "holiday_name": status.holiday_name,
            },
            "market_status",
            resource_id=exchange,
        )

    @router.get("/{exchange}/holidays")
    async def get_exchange_holidays(exchange: str, year: int = 2026):
        """Get holiday calendar for an exchange."""
        exchange = exchange.upper()
        if exchange not in SCHEDULES:
            return not_found("Exchange", exchange)

        # Crypto has no holidays
        if exchange == "CRYPTO":
            return {"data": [], "meta": {"total": 0}}

        holidays = get_holidays(year)
        items = [
            {
                "date": h.date.isoformat(),
                "name": h.name,
                "half_day": h.half_day,
            }
            for h in holidays
        ]
        return {"data": items, "meta": {"total": len(items), "year": year}}

    app.include_router(router)
    return app
