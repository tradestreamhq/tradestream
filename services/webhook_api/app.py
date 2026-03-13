"""
Webhook REST API — RMM Level 2.

Provides endpoints for webhook registration, management,
testing, and delivery history.
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query
from pydantic import BaseModel

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware
from services.webhook_api.dispatcher import WebhookDispatcher
from services.webhook_api.models import WebhookCreate, WebhookEvent, WebhookUpdate

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Webhook API FastAPI application."""
    app = FastAPI(
        title="Webhook API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/webhooks",
    )
    fastapi_auth_middleware(app)

    dispatcher = WebhookDispatcher(db_pool)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("webhook-api", check_deps))

    # --- Webhook CRUD ---

    @app.post("", tags=["Webhooks"], status_code=201)
    async def create_webhook(body: WebhookCreate):
        """Register a new webhook endpoint."""
        webhook_id = uuid.uuid4()
        signing_secret = secrets.token_hex(32)
        now = datetime.now(timezone.utc)
        events = [e.value for e in body.events]

        try:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO webhooks
                       (id, url, events, description, is_active,
                        signing_secret, created_at, updated_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    webhook_id,
                    str(body.url),
                    events,
                    body.description,
                    body.is_active,
                    signing_secret,
                    now,
                    now,
                )
        except Exception as e:
            logger.exception("Failed to create webhook")
            return server_error("Failed to create webhook")

        return success_response(
            {
                "url": str(body.url),
                "events": events,
                "description": body.description,
                "is_active": body.is_active,
                "signing_secret": signing_secret,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
            "webhook",
            resource_id=str(webhook_id),
            status_code=201,
        )

    @app.get("", tags=["Webhooks"])
    async def list_webhooks(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        """List all registered webhooks."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, url, events, description, is_active,
                          signing_secret, created_at, updated_at
                   FROM webhooks
                   ORDER BY created_at DESC
                   LIMIT $1 OFFSET $2""",
                limit,
                offset,
            )
            total = await conn.fetchval("SELECT COUNT(*) FROM webhooks")

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["created_at"] = item["created_at"].isoformat()
            item["updated_at"] = item["updated_at"].isoformat()
            item["events"] = list(item["events"])
            items.append(item)

        return collection_response(items, "webhook", total=total, limit=limit, offset=offset)

    @app.get("/{webhook_id}", tags=["Webhooks"])
    async def get_webhook(webhook_id: uuid.UUID):
        """Get a specific webhook by ID."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, url, events, description, is_active,
                          signing_secret, created_at, updated_at
                   FROM webhooks WHERE id = $1""",
                webhook_id,
            )
        if not row:
            return not_found("Webhook", str(webhook_id))

        item = dict(row)
        item["id"] = str(item["id"])
        item["created_at"] = item["created_at"].isoformat()
        item["updated_at"] = item["updated_at"].isoformat()
        item["events"] = list(item["events"])

        return success_response(item, "webhook", resource_id=str(webhook_id))

    @app.put("/{webhook_id}", tags=["Webhooks"])
    async def update_webhook(webhook_id: uuid.UUID, body: WebhookUpdate):
        """Update an existing webhook configuration."""
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM webhooks WHERE id = $1", webhook_id
            )
            if not existing:
                return not_found("Webhook", str(webhook_id))

            updates = []
            params = []
            param_idx = 1

            if body.url is not None:
                param_idx += 1
                updates.append(f"url = ${param_idx}")
                params.append(str(body.url))
            if body.events is not None:
                param_idx += 1
                updates.append(f"events = ${param_idx}")
                params.append([e.value for e in body.events])
            if body.description is not None:
                param_idx += 1
                updates.append(f"description = ${param_idx}")
                params.append(body.description)
            if body.is_active is not None:
                param_idx += 1
                updates.append(f"is_active = ${param_idx}")
                params.append(body.is_active)

            if not updates:
                return validation_error("No fields to update")

            param_idx += 1
            updates.append(f"updated_at = ${param_idx}")
            params.append(datetime.now(timezone.utc))

            query = f"""UPDATE webhooks SET {', '.join(updates)}
                       WHERE id = $1
                       RETURNING id, url, events, description, is_active,
                                 signing_secret, created_at, updated_at"""
            row = await conn.fetchrow(query, webhook_id, *params)

        item = dict(row)
        item["id"] = str(item["id"])
        item["created_at"] = item["created_at"].isoformat()
        item["updated_at"] = item["updated_at"].isoformat()
        item["events"] = list(item["events"])

        return success_response(item, "webhook", resource_id=str(webhook_id))

    @app.delete("/{webhook_id}", tags=["Webhooks"], status_code=204)
    async def delete_webhook(webhook_id: uuid.UUID):
        """Delete a webhook."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM webhooks WHERE id = $1", webhook_id
            )
            if not row:
                return not_found("Webhook", str(webhook_id))
            await conn.execute("DELETE FROM webhooks WHERE id = $1", webhook_id)

    @app.post("/{webhook_id}/test", tags=["Webhooks"])
    async def test_webhook(webhook_id: uuid.UUID):
        """Send a test payload to a webhook."""
        result = await dispatcher.send_test(webhook_id)
        if not result.get("success"):
            error_msg = result.get("error", "Unknown error")
            if error_msg == "Webhook not found":
                return not_found("Webhook", str(webhook_id))
            return error_response("DELIVERY_FAILED", error_msg, status_code=502)

        return success_response(result, "webhook_test")

    # --- Delivery History ---

    @app.get("/{webhook_id}/deliveries", tags=["Deliveries"])
    async def list_deliveries(
        webhook_id: uuid.UUID,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        """List delivery history for a webhook."""
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM webhooks WHERE id = $1", webhook_id
            )
            if not existing:
                return not_found("Webhook", str(webhook_id))

            rows = await conn.fetch(
                """SELECT id, webhook_id, event_type, status,
                          response_code, error_message, created_at
                   FROM webhook_deliveries
                   WHERE webhook_id = $1
                   ORDER BY created_at DESC
                   LIMIT $2 OFFSET $3""",
                webhook_id,
                limit,
                offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM webhook_deliveries WHERE webhook_id = $1",
                webhook_id,
            )

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["webhook_id"] = str(item["webhook_id"])
            item["created_at"] = item["created_at"].isoformat()
            items.append(item)

        return collection_response(
            items, "webhook_delivery", total=total, limit=limit, offset=offset
        )

    return app
