"""TradingView Webhook Integration API.

Provides endpoints for:
- Receiving TradingView alert webhooks and converting them to TradeStream signals
- Managing TradingView integration connections
- Generating Pine Script templates for TradeStream strategies
- Publishing TradeStream signals as TradingView-compatible alerts
"""

import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Path, Query, Request
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.tradingview_integration.alert_publisher import TradingViewAlertPublisher
from services.tradingview_integration.models import (
    PineScriptConfig,
    TradingViewAction,
    TradingViewConnection,
    TradingViewWebhookPayload,
    tradingview_payload_to_signal,
)
from services.tradingview_integration.pine_script import (
    generate_strategy_template,
    generate_webhook_indicator,
)

logger = logging.getLogger(__name__)


# --- Request DTOs ---


class CreateConnectionRequest(BaseModel):
    name: str = Field(..., description="Connection name")
    strategy_name: Optional[str] = Field(
        None, description="Map to this TradeStream strategy"
    )
    instrument: Optional[str] = Field(
        None, description="Override instrument (e.g., BTC/USD)"
    )
    alert_mapping: Optional[Dict[str, str]] = Field(
        None, description="Custom action-to-signal mappings"
    )


class UpdateConnectionRequest(BaseModel):
    name: Optional[str] = None
    strategy_name: Optional[str] = None
    instrument: Optional[str] = None
    active: Optional[bool] = None
    alert_mapping: Optional[Dict[str, str]] = None


class PineScriptRequest(BaseModel):
    strategy_name: str = Field(..., description="Strategy name")
    ticker: Optional[str] = Field(None, description="Override symbol")
    include_stop_loss: bool = Field(True)
    include_take_profit: bool = Field(True)
    include_quantity: bool = Field(True)
    template_type: str = Field(
        "indicator",
        description="'indicator' or 'strategy'",
        pattern="^(indicator|strategy)$",
    )


class PublishAlertRequest(BaseModel):
    webhook_url: str = Field(..., description="Target webhook URL")
    signal: Dict[str, Any] = Field(..., description="Internal signal to publish")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the TradingView Integration FastAPI application."""
    app = FastAPI(
        title="TradingView Integration API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/integrations/tradingview",
    )
    # Custom auth middleware that skips API key check for webhook endpoints
    # (TradingView authenticates via secret token in the URL path instead)
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class _TradingViewAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            path = request.url.path
            # Webhook endpoints use token-based auth, not API key
            if path.startswith("/webhook/") or path in ("/health", "/api/health"):
                return await call_next(request)
            # All other endpoints require API key
            import os

            api_key = os.environ.get("TRADESTREAM_API_KEY")
            if not api_key:
                return await call_next(request)
            provided = request.headers.get("X-API-Key")
            if provided != api_key:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or missing API key"},
                )
            return await call_next(request)

    app.add_middleware(_TradingViewAuthMiddleware)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("tradingview-integration", check_deps))

    # ------------------------------------------------------------------
    # Webhook Receiver — token-authenticated, no API key required
    # ------------------------------------------------------------------

    @app.post("/webhook/{webhook_token}", tags=["Webhook"])
    async def receive_webhook(webhook_token: str, request: Request):
        """Receive a TradingView alert webhook.

        Authentication is via the secret token in the URL path.
        This endpoint is excluded from API key auth so TradingView can call it.
        """
        # Look up connection by token
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, name, strategy_name, instrument, alert_mapping, active "
                "FROM tradingview_connections "
                "WHERE webhook_token = $1",
                webhook_token,
            )

        if not row:
            return error_response(
                "UNAUTHORIZED", "Invalid webhook token", status_code=401
            )

        if not row["active"]:
            return error_response(
                "CONNECTION_DISABLED",
                "This TradingView connection is disabled",
                status_code=403,
            )

        # Parse request body
        try:
            body = await request.json()
        except Exception:
            return validation_error("Invalid JSON payload")

        try:
            payload = TradingViewWebhookPayload(**body)
        except Exception as e:
            return validation_error(f"Invalid webhook payload: {e}")

        # Convert to internal signal
        connection_config = dict(row)
        if connection_config.get("alert_mapping"):
            # alert_mapping is stored as JSONB, asyncpg returns it as a string or dict
            if isinstance(connection_config["alert_mapping"], str):
                connection_config["alert_mapping"] = json.loads(
                    connection_config["alert_mapping"]
                )

        signal = tradingview_payload_to_signal(payload, connection_config)

        # Store the signal
        signal_id = str(uuid.uuid4())
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO signals
                   (id, strategy_name, instrument, signal_type, price,
                    stop_loss, take_profit, position_size, strength,
                    metadata, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())""",
                signal_id,
                signal["strategy_name"],
                signal["instrument"],
                signal["signal_type"],
                signal.get("price"),
                signal.get("stop_loss"),
                signal.get("take_profit"),
                signal.get("position_size"),
                signal.get("strength"),
                json.dumps(signal.get("metadata", {})),
            )

        # Record webhook receipt
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO tradingview_webhook_log
                   (id, connection_id, signal_id, raw_payload, created_at)
                   VALUES ($1, $2, $3, $4, NOW())""",
                str(uuid.uuid4()),
                str(row["id"]),
                signal_id,
                json.dumps(body),
            )

        logger.info(
            "TradingView webhook received: connection=%s signal=%s type=%s",
            row["name"],
            signal_id,
            signal["signal_type"],
        )

        return success_response(
            {
                "signal_id": signal_id,
                "signal_type": signal["signal_type"],
                "instrument": signal["instrument"],
                "strategy_name": signal["strategy_name"],
                "price": signal.get("price"),
            },
            "tradingview_signal",
            resource_id=signal_id,
            status_code=201,
        )

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------

    @app.post("/connections", tags=["Connections"])
    async def create_connection(body: CreateConnectionRequest):
        """Create a new TradingView integration connection."""
        conn_id = str(uuid.uuid4())
        webhook_token = secrets.token_urlsafe(32)

        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO tradingview_connections
                   (id, name, webhook_token, strategy_name, instrument,
                    alert_mapping, active, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, true, NOW())""",
                conn_id,
                body.name,
                webhook_token,
                body.strategy_name,
                body.instrument,
                json.dumps(body.alert_mapping) if body.alert_mapping else None,
            )

        return success_response(
            {
                "id": conn_id,
                "name": body.name,
                "webhook_token": webhook_token,
                "webhook_url": f"/api/v1/integrations/tradingview/webhook/{webhook_token}",
                "strategy_name": body.strategy_name,
                "instrument": body.instrument,
                "active": True,
            },
            "tradingview_connection",
            resource_id=conn_id,
            status_code=201,
        )

    @app.get("/connections", tags=["Connections"])
    async def list_connections():
        """List all TradingView connections."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, webhook_token, strategy_name, instrument, "
                "active, created_at FROM tradingview_connections ORDER BY created_at DESC"
            )

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["webhook_url"] = (
                f"/api/v1/integrations/tradingview/webhook/{item['webhook_token']}"
            )
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)

        return collection_response(items, "tradingview_connection")

    @app.get("/connections/{connection_id}", tags=["Connections"])
    async def get_connection(connection_id: str):
        """Get a specific TradingView connection."""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, name, webhook_token, strategy_name, instrument, "
                "alert_mapping, active, created_at "
                "FROM tradingview_connections WHERE id = $1",
                connection_id,
            )

        if not row:
            return not_found("TradingView connection", connection_id)

        item = dict(row)
        item["id"] = str(item["id"])
        item["webhook_url"] = (
            f"/api/v1/integrations/tradingview/webhook/{item['webhook_token']}"
        )
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()

        return success_response(item, "tradingview_connection", resource_id=item["id"])

    @app.patch("/connections/{connection_id}", tags=["Connections"])
    async def update_connection(connection_id: str, body: UpdateConnectionRequest):
        """Update a TradingView connection configuration."""
        updates = []
        params = []
        idx = 1

        if body.name is not None:
            updates.append(f"name = ${idx}")
            params.append(body.name)
            idx += 1
        if body.strategy_name is not None:
            updates.append(f"strategy_name = ${idx}")
            params.append(body.strategy_name)
            idx += 1
        if body.instrument is not None:
            updates.append(f"instrument = ${idx}")
            params.append(body.instrument)
            idx += 1
        if body.active is not None:
            updates.append(f"active = ${idx}")
            params.append(body.active)
            idx += 1
        if body.alert_mapping is not None:
            updates.append(f"alert_mapping = ${idx}")
            params.append(json.dumps(body.alert_mapping))
            idx += 1

        if not updates:
            return validation_error("No fields to update")

        updates.append(f"updated_at = NOW()")
        params.append(connection_id)

        query = (
            f"UPDATE tradingview_connections SET {', '.join(updates)} "
            f"WHERE id = ${idx} RETURNING id, name, active"
        )

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return not_found("TradingView connection", connection_id)

        return success_response(
            {"id": str(row["id"]), "name": row["name"], "active": row["active"]},
            "tradingview_connection",
            resource_id=str(row["id"]),
        )

    @app.delete("/connections/{connection_id}", tags=["Connections"])
    async def delete_connection(connection_id: str):
        """Delete (deactivate) a TradingView connection."""
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE tradingview_connections SET active = false, updated_at = NOW() "
                "WHERE id = $1 AND active = true",
                connection_id,
            )

        if result == "UPDATE 0":
            return not_found("TradingView connection", connection_id)

        return success_response(
            {"id": connection_id, "status": "disconnected"},
            "tradingview_connection",
            resource_id=connection_id,
        )

    # ------------------------------------------------------------------
    # Pine Script Generator
    # ------------------------------------------------------------------

    @app.post("/pine-script", tags=["Pine Script"])
    async def generate_pine_script(body: PineScriptRequest, request: Request):
        """Generate a Pine Script template for TradingView alerts.

        The generated script includes webhook alert payloads configured
        to send data to the TradeStream TradingView webhook endpoint.
        """
        # Find connection for this strategy to get webhook URL
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT webhook_token FROM tradingview_connections "
                "WHERE strategy_name = $1 AND active = true LIMIT 1",
                body.strategy_name,
            )

        if row:
            base_url = str(request.base_url).rstrip("/")
            webhook_url = f"{base_url}/api/v1/integrations/tradingview/webhook/{row['webhook_token']}"
        else:
            webhook_url = "<YOUR_WEBHOOK_URL>"

        config = PineScriptConfig(
            strategy_name=body.strategy_name,
            webhook_url=webhook_url,
            ticker=body.ticker,
            include_stop_loss=body.include_stop_loss,
            include_take_profit=body.include_take_profit,
            include_quantity=body.include_quantity,
        )

        if body.template_type == "strategy":
            script = generate_strategy_template(config)
        else:
            script = generate_webhook_indicator(config)

        return success_response(
            {
                "strategy_name": body.strategy_name,
                "template_type": body.template_type,
                "pine_script": script,
                "webhook_url": webhook_url,
            },
            "pine_script",
        )

    # ------------------------------------------------------------------
    # Alert Publisher
    # ------------------------------------------------------------------

    @app.post("/publish", tags=["Publisher"])
    async def publish_alert(body: PublishAlertRequest):
        """Publish a TradeStream signal as a TradingView-compatible webhook alert."""
        publisher = TradingViewAlertPublisher(body.webhook_url)
        payload = publisher.format_payload(body.signal)
        delivered = publisher.publish_signal(body.signal)

        return success_response(
            {
                "delivered": delivered,
                "payload": payload,
                "webhook_url": body.webhook_url,
            },
            "tradingview_alert",
        )

    # ------------------------------------------------------------------
    # Webhook Log
    # ------------------------------------------------------------------

    @app.get("/webhook-log", tags=["Webhook"])
    async def get_webhook_log(
        connection_id: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=200),
    ):
        """Get recent webhook receipts for debugging."""
        if connection_id:
            rows_query = (
                "SELECT wl.id, wl.connection_id, wl.signal_id, wl.raw_payload, "
                "wl.created_at, tc.name as connection_name "
                "FROM tradingview_webhook_log wl "
                "JOIN tradingview_connections tc ON tc.id::text = wl.connection_id "
                "WHERE wl.connection_id = $1 "
                "ORDER BY wl.created_at DESC LIMIT $2"
            )
            params = [connection_id, limit]
        else:
            rows_query = (
                "SELECT wl.id, wl.connection_id, wl.signal_id, wl.raw_payload, "
                "wl.created_at, tc.name as connection_name "
                "FROM tradingview_webhook_log wl "
                "JOIN tradingview_connections tc ON tc.id::text = wl.connection_id "
                "ORDER BY wl.created_at DESC LIMIT $1"
            )
            params = [limit]

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(rows_query, *params)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            if item.get("raw_payload") and isinstance(item["raw_payload"], str):
                item["raw_payload"] = json.loads(item["raw_payload"])
            items.append(item)

        return collection_response(items, "webhook_log_entry")

    return app
