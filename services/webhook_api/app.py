"""
Webhook Management REST API.

Provides CRUD endpoints for webhooks, delivery history,
event dispatching with HMAC-SHA256 signing, and retry logic.
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import List, Optional

import asyncpg
from fastapi import Depends, FastAPI, Query
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

logger = logging.getLogger(__name__)

VALID_EVENT_TYPES = {
    "trade_executed",
    "signal_triggered",
    "position_changed",
    "risk_alert",
}

DEFAULT_RETRY_POLICY = {"max_retries": 3, "backoff_seconds": [1, 5, 30]}


# --- Request DTOs ---


class RetryPolicyDTO(BaseModel):
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")
    backoff_seconds: List[int] = Field(
        default=[1, 5, 30], description="Backoff delays in seconds per retry"
    )


class CreateWebhookDTO(BaseModel):
    url: str = Field(..., description="Webhook destination URL")
    secret: str = Field("", description="HMAC-SHA256 signing secret")
    event_types: List[str] = Field(
        ..., min_length=1, description="Event types to subscribe to"
    )
    is_active: bool = Field(True, description="Whether the webhook is active")
    retry_policy: Optional[RetryPolicyDTO] = Field(
        None, description="Retry policy configuration"
    )
    description: str = Field("", description="Human-readable description")


class UpdateWebhookDTO(BaseModel):
    url: Optional[str] = Field(None, description="Webhook destination URL")
    secret: Optional[str] = Field(None, description="HMAC-SHA256 signing secret")
    event_types: Optional[List[str]] = Field(
        None, description="Event types to subscribe to"
    )
    is_active: Optional[bool] = Field(None, description="Whether the webhook is active")
    retry_policy: Optional[RetryPolicyDTO] = Field(
        None, description="Retry policy configuration"
    )
    description: Optional[str] = Field(None, description="Human-readable description")


# --- Helpers ---


def _compute_signature(secret: str, timestamp: str, payload: str) -> str:
    """Compute HMAC-SHA256 signature over timestamp.payload."""
    message = f"{timestamp}.{payload}"
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _serialize_webhook(row) -> dict:
    """Convert a database row to a serializable dict."""
    item = dict(row)
    for ts_field in ("created_at", "updated_at"):
        if item.get(ts_field):
            item[ts_field] = item[ts_field].isoformat()
    if isinstance(item.get("retry_policy"), str):
        item["retry_policy"] = json.loads(item["retry_policy"])
    # Mask secret in responses
    if item.get("secret"):
        item["secret"] = "••••••••"
    return item


def _serialize_delivery(row) -> dict:
    """Convert a delivery row to a serializable dict."""
    item = dict(row)
    if item.get("created_at"):
        item["created_at"] = item["created_at"].isoformat()
    if item.get("payload") and isinstance(item["payload"], str):
        item["payload"] = json.loads(item["payload"])
    return item


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

    # --- CRUD ---

    @app.post("", status_code=201, tags=["Webhooks"])
    async def create_webhook(body: CreateWebhookDTO):
        """Register a new webhook subscription."""
        invalid = [e for e in body.event_types if e not in VALID_EVENT_TYPES]
        if invalid:
            return validation_error(
                f"Invalid event types: {invalid}. "
                f"Valid types: {sorted(VALID_EVENT_TYPES)}"
            )

        retry_policy = (
            body.retry_policy.model_dump() if body.retry_policy else DEFAULT_RETRY_POLICY
        )

        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO webhooks (url, secret, event_types, is_active,
                                          retry_policy, description)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6)
                    RETURNING *
                    """,
                    body.url,
                    body.secret,
                    body.event_types,
                    body.is_active,
                    json.dumps(retry_policy),
                    body.description,
                )
        except Exception as e:
            logger.error("Failed to create webhook: %s", e)
            return server_error("Failed to create webhook")

        return success_response(
            _serialize_webhook(row),
            "webhook",
            resource_id=str(row["id"]),
            status_code=201,
        )

    @app.get("", tags=["Webhooks"])
    async def list_webhooks(
        pagination: PaginationParams = Depends(),
        is_active: Optional[bool] = Query(None, description="Filter by active status"),
        event_type: Optional[str] = Query(None, description="Filter by event type"),
    ):
        """List all registered webhooks."""
        conditions = []
        params = []
        idx = 1

        if is_active is not None:
            conditions.append(f"is_active = ${idx}")
            params.append(is_active)
            idx += 1

        if event_type is not None:
            conditions.append(f"${idx} = ANY(event_types)")
            params.append(event_type)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_query = f"SELECT COUNT(*) FROM webhooks {where}"
        data_query = f"""
            SELECT * FROM webhooks {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params_with_pagination = params + [pagination.limit, pagination.offset]

        async with db_pool.acquire() as conn:
            total = await conn.fetchval(count_query, *params)
            rows = await conn.fetch(data_query, *params_with_pagination)

        items = [_serialize_webhook(row) for row in rows]
        return collection_response(
            items, "webhook", total=total, limit=pagination.limit, offset=pagination.offset
        )

    @app.get("/{webhook_id}", tags=["Webhooks"])
    async def get_webhook(webhook_id: str):
        """Get a single webhook by ID."""
        try:
            wid = uuid.UUID(webhook_id)
        except ValueError:
            return validation_error(f"Invalid webhook ID: {webhook_id}")

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM webhooks WHERE id = $1", wid)

        if not row:
            return not_found("Webhook", webhook_id)
        return success_response(
            _serialize_webhook(row), "webhook", resource_id=webhook_id
        )

    @app.patch("/{webhook_id}", tags=["Webhooks"])
    async def update_webhook(webhook_id: str, body: UpdateWebhookDTO):
        """Update a webhook's configuration."""
        try:
            wid = uuid.UUID(webhook_id)
        except ValueError:
            return validation_error(f"Invalid webhook ID: {webhook_id}")

        if body.event_types is not None:
            invalid = [e for e in body.event_types if e not in VALID_EVENT_TYPES]
            if invalid:
                return validation_error(
                    f"Invalid event types: {invalid}. "
                    f"Valid types: {sorted(VALID_EVENT_TYPES)}"
                )

        updates = []
        params = []
        idx = 1

        for field in ("url", "secret", "is_active", "description"):
            val = getattr(body, field)
            if val is not None:
                updates.append(f"{field} = ${idx}")
                params.append(val)
                idx += 1

        if body.event_types is not None:
            updates.append(f"event_types = ${idx}")
            params.append(body.event_types)
            idx += 1

        if body.retry_policy is not None:
            updates.append(f"retry_policy = ${idx}::jsonb")
            params.append(json.dumps(body.retry_policy.model_dump()))
            idx += 1

        if not updates:
            return validation_error("No fields to update")

        updates.append("updated_at = NOW()")

        query = f"""
            UPDATE webhooks SET {', '.join(updates)}
            WHERE id = ${idx}
            RETURNING *
        """
        params.append(wid)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return not_found("Webhook", webhook_id)
        return success_response(
            _serialize_webhook(row), "webhook", resource_id=webhook_id
        )

    @app.delete("/{webhook_id}", status_code=204, tags=["Webhooks"])
    async def delete_webhook(webhook_id: str):
        """Delete a webhook subscription."""
        try:
            wid = uuid.UUID(webhook_id)
        except ValueError:
            return validation_error(f"Invalid webhook ID: {webhook_id}")

        async with db_pool.acquire() as conn:
            result = await conn.execute("DELETE FROM webhooks WHERE id = $1", wid)

        if result == "DELETE 0":
            return not_found("Webhook", webhook_id)
        return None

    # --- Delivery history ---

    @app.get("/{webhook_id}/deliveries", tags=["Deliveries"])
    async def list_deliveries(
        webhook_id: str,
        pagination: PaginationParams = Depends(),
        success: Optional[bool] = Query(None, description="Filter by success status"),
    ):
        """List delivery history for a webhook."""
        try:
            wid = uuid.UUID(webhook_id)
        except ValueError:
            return validation_error(f"Invalid webhook ID: {webhook_id}")

        # Check webhook exists
        async with db_pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM webhooks WHERE id = $1", wid
            )
            if not exists:
                return not_found("Webhook", webhook_id)

            conditions = ["webhook_id = $1"]
            params = [wid]
            idx = 2

            if success is not None:
                conditions.append(f"success = ${idx}")
                params.append(success)
                idx += 1

            where = f"WHERE {' AND '.join(conditions)}"

            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM webhook_deliveries {where}", *params
            )
            rows = await conn.fetch(
                f"""
                SELECT * FROM webhook_deliveries {where}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}
                """,
                *params,
                pagination.limit,
                pagination.offset,
            )

        items = [_serialize_delivery(row) for row in rows]
        return collection_response(
            items,
            "webhook_delivery",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # --- Test endpoint ---

    @app.post("/{webhook_id}/test", tags=["Webhooks"])
    async def test_webhook(webhook_id: str):
        """Send a test payload to a webhook."""
        try:
            wid = uuid.UUID(webhook_id)
        except ValueError:
            return validation_error(f"Invalid webhook ID: {webhook_id}")

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM webhooks WHERE id = $1", wid)

        if not row:
            return not_found("Webhook", webhook_id)

        test_payload = {
            "event_type": "test",
            "webhook_id": str(row["id"]),
            "timestamp": int(time.time()),
            "data": {
                "message": "This is a test event from TradeStream.",
            },
        }

        payload_str = json.dumps(test_payload, default=str, sort_keys=True)
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-TradeStream-Timestamp": timestamp,
        }

        secret = row["secret"]
        if secret:
            sig = _compute_signature(secret, timestamp, payload_str)
            headers["X-TradeStream-Signature"] = sig

        import requests

        start = time.monotonic()
        delivery_record = {
            "webhook_id": wid,
            "event_type": "test",
            "payload": json.dumps(test_payload),
            "attempt": 1,
        }

        try:
            resp = requests.post(
                row["url"],
                data=payload_str,
                headers=headers,
                timeout=10,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            delivery_record.update(
                {
                    "status_code": resp.status_code,
                    "response_body": resp.text[:1000],
                    "response_time_ms": elapsed_ms,
                    "success": resp.status_code < 300,
                }
            )
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            delivery_record.update(
                {
                    "response_time_ms": elapsed_ms,
                    "success": False,
                    "error": str(e)[:1000],
                }
            )

        # Record delivery
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO webhook_deliveries
                    (webhook_id, event_type, payload, status_code,
                     response_body, response_time_ms, attempt, success, error)
                VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, $8, $9)
                """,
                delivery_record["webhook_id"],
                delivery_record["event_type"],
                delivery_record.get("payload"),
                delivery_record.get("status_code"),
                delivery_record.get("response_body"),
                delivery_record.get("response_time_ms"),
                delivery_record.get("attempt", 1),
                delivery_record.get("success", False),
                delivery_record.get("error"),
            )

        return success_response(
            {
                "delivered": delivery_record.get("success", False),
                "status_code": delivery_record.get("status_code"),
                "response_time_ms": delivery_record.get("response_time_ms"),
                "error": delivery_record.get("error"),
            },
            "webhook_test",
            resource_id=webhook_id,
        )

    return app
