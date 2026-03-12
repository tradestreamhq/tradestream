"""Audit Trail REST API for trade execution compliance."""

import logging
from datetime import datetime
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query
from fastapi.responses import Response

from services.audit_trail.models import AuditSearchParams, EventType
from services.audit_trail.query import AuditQuery
from services.audit_trail.recorder import AuditRecorder
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Audit Trail API FastAPI application."""
    app = FastAPI(
        title="Audit Trail API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/audit",
    )
    fastapi_auth_middleware(app)

    recorder = AuditRecorder(db_pool)
    query = AuditQuery(db_pool)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("audit-trail-api", check_deps))

    # --- Record event ---

    @app.post("/events", tags=["Audit"])
    async def record_event(
        order_id: str = Query(...),
        event_type: EventType = Query(...),
        symbol: Optional[str] = Query(None),
        strategy: Optional[str] = Query(None),
    ):
        """Record an order lifecycle event."""
        event = await recorder.record(
            order_id=order_id,
            event_type=event_type,
            symbol=symbol,
            strategy=strategy,
        )
        return success_response(
            event.model_dump(mode="json"),
            "audit_event",
            resource_id=event.event_id,
        )

    # --- Order trail ---

    @app.get("/orders/{order_id}", tags=["Audit"])
    async def get_order_trail(order_id: str):
        """Get the full audit trail for a specific order."""
        events = await query.get_order_trail(order_id)
        if not events:
            return not_found("Order trail", order_id)
        return collection_response(events, "audit_event")

    # --- Search ---

    @app.get("/search", tags=["Audit"])
    async def search_events(
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        strategy: Optional[str] = Query(None),
        symbol: Optional[str] = Query(None),
        event_type: Optional[EventType] = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        """Search audit events by date, strategy, symbol, or event type."""
        params = AuditSearchParams(
            start_date=start_date,
            end_date=end_date,
            strategy=strategy,
            symbol=symbol,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
        events = await query.search(params)
        return collection_response(events, "audit_event", limit=limit, offset=offset)

    # --- CSV export ---

    @app.get("/export", tags=["Audit"])
    async def export_csv(
        start_date: Optional[datetime] = Query(None),
        end_date: Optional[datetime] = Query(None),
        strategy: Optional[str] = Query(None),
        symbol: Optional[str] = Query(None),
        event_type: Optional[EventType] = Query(None),
        limit: int = Query(1000, ge=1, le=10000),
        offset: int = Query(0, ge=0),
    ):
        """Export audit events as CSV for compliance reporting."""
        params = AuditSearchParams(
            start_date=start_date,
            end_date=end_date,
            strategy=strategy,
            symbol=symbol,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
        csv_content = await query.export_csv(params)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
        )

    return app
