"""
Webhook REST API — RMM Level 2.

Provides CRUD endpoints for webhook registration, testing, and
delivery log inspection.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware
from services.webhook_api.delivery import (
    VALID_EVENT_TYPES,
    deliver_webhook,
    deliver_with_retries,
)

logger = logging.getLogger(__name__)


# --- Request DTOs ---


class WebhookCreate(BaseModel):
    url: str = Field(..., description="Destination URL for webhook delivery")
    events: List[str] = Field(..., description="Event types to subscribe to")
    secret: str = Field(..., description="Shared secret for HMAC-SHA256 signing")
    description: Optional[str] = Field(None, description="Human-readable description")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Webhook API FastAPI application."""
    app = FastAPI(
        title="Webhook API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/webhooks",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("webhook-api", check_deps))

    router = APIRouter(tags=["Webhooks"])

    # ------------------------------------------------------------------
    # POST / — register a new webhook
    # ------------------------------------------------------------------
    @router.post("", status_code=201)
    async def create_webhook(body: WebhookCreate):
        # Validate event types
        invalid = set(body.events) - VALID_EVENT_TYPES
        if invalid:
            return validation_error(
                f"Invalid event types: {', '.join(sorted(invalid))}. "
                f"Valid types: {', '.join(sorted(VALID_EVENT_TYPES))}"
            )
        if not body.events:
            return validation_error("At least one event type is required")

        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO webhooks (url, events, secret, description)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, url, events, is_active, description, created_at
                    """,
                    body.url,
                    body.events,
                    body.secret,
                    body.description,
                )
        except Exception as e:
            logger.error("Failed to create webhook: %s", e)
            return server_error(str(e))

        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        item["events"] = list(item["events"])
        return success_response(
            item, "webhook", resource_id=item["id"], status_code=201
        )

    # ------------------------------------------------------------------
    # GET / — list all webhooks
    # ------------------------------------------------------------------
    @router.get("")
    async def list_webhooks(pagination: PaginationParams = Depends()):
        query = """
            SELECT id, url, events, is_active, description, created_at
            FROM webhooks
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM webhooks"

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, pagination.limit, pagination.offset)
            total = await conn.fetchval(count_query)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            item["events"] = list(item["events"])
            items.append(item)

        return collection_response(
            items,
            "webhook",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # ------------------------------------------------------------------
    # DELETE /{webhook_id} — remove a webhook
    # ------------------------------------------------------------------
    @router.delete("/{webhook_id}", status_code=204)
    async def delete_webhook(webhook_id: str):
        query = "DELETE FROM webhooks WHERE id = $1::uuid RETURNING id"
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, webhook_id)
        if not row:
            return not_found("Webhook", webhook_id)
        return None

    # ------------------------------------------------------------------
    # POST /{webhook_id}/test — send a test payload
    # ------------------------------------------------------------------
    @router.post("/{webhook_id}/test")
    async def test_webhook(webhook_id: str):
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, url, secret, events FROM webhooks WHERE id = $1::uuid",
                webhook_id,
            )
        if not row:
            return not_found("Webhook", webhook_id)

        test_payload = {
            "event": "test",
            "webhook_id": str(row["id"]),
            "message": "This is a test webhook delivery from TradeStream.",
            "subscribed_events": list(row["events"]),
        }

        result = await deliver_webhook(
            url=row["url"],
            secret=row["secret"],
            event_type="test",
            payload=test_payload,
        )

        return success_response(
            {
                "webhook_id": str(row["id"]),
                "delivered": result["success"],
                "status_code": result["status_code"],
                "error": result["error"],
            },
            "webhook_test",
        )

    # ------------------------------------------------------------------
    # GET /{webhook_id}/deliveries — delivery log
    # ------------------------------------------------------------------
    @router.get("/{webhook_id}/deliveries")
    async def list_deliveries(
        webhook_id: str,
        pagination: PaginationParams = Depends(),
    ):
        # Verify webhook exists
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM webhooks WHERE id = $1::uuid", webhook_id
            )
        if not exists:
            return not_found("Webhook", webhook_id)

        query = """
            SELECT id, webhook_id, event_type, status, attempts,
                   response_code, error_message, created_at, completed_at
            FROM webhook_deliveries
            WHERE webhook_id = $1::uuid
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*) FROM webhook_deliveries WHERE webhook_id = $1::uuid
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                query, webhook_id, pagination.limit, pagination.offset
            )
            total = await conn.fetchval(count_query, webhook_id)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["webhook_id"] = str(item["webhook_id"])
            for ts_field in ("created_at", "completed_at"):
                if item.get(ts_field):
                    item[ts_field] = item[ts_field].isoformat()
            items.append(item)

        return collection_response(
            items,
            "webhook_delivery",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    app.include_router(router)
    return app
