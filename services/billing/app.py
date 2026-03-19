"""
Billing REST API — Stripe subscription management.

Provides endpoints for checkout session creation, webhook handling,
subscription management, and customer portal access.
"""

import json as json_module
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import stripe
from fastapi import FastAPI, Header, Query, Request
from pydantic import BaseModel, Field

from services.billing.plans import PLANS, get_plan, plan_to_dict
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
from services.shared.pipeline_metrics import PipelineMetrics

logger = logging.getLogger(__name__)


class CheckoutRequest(BaseModel):
    tier: str = Field(
        ...,
        description="Subscription tier: 'pro' or 'enterprise'",
        pattern="^(pro|enterprise)$",
    )
    email: str = Field(..., description="Customer email address")
    success_url: str = Field(
        ..., description="URL to redirect after successful checkout"
    )
    cancel_url: str = Field(..., description="URL to redirect if checkout is cancelled")
    telegram_chat_id: Optional[str] = Field(
        None, description="Telegram chat ID to link subscription"
    )


class PortalRequest(BaseModel):
    customer_id: str = Field(..., description="Billing customer UUID")
    return_url: str = Field(..., description="URL to redirect after portal session")


def create_app(
    db_pool: asyncpg.Pool, metrics: Optional[PipelineMetrics] = None
) -> FastAPI:
    """Create the Billing API FastAPI application."""
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    app = FastAPI(
        title="Billing API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/billing",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("billing-api", check_deps))

    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------

    @app.get("/plans", tags=["Plans"])
    async def list_plans():
        """List available subscription plans."""
        items = [plan_to_dict(p) for p in PLANS.values()]
        return collection_response(items, "plan")

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    @app.post("/checkout", tags=["Checkout"])
    async def create_checkout(body: CheckoutRequest):
        """Create a Stripe Checkout session for a subscription."""
        plan = get_plan(body.tier)
        price_id = os.environ.get(plan.stripe_price_id_env, "")
        if not price_id:
            return validation_error(
                f"Stripe price not configured for tier '{body.tier}'"
            )

        if not stripe.api_key:
            return server_error("Stripe is not configured")

        try:
            metadata = {"tier": body.tier}
            if body.telegram_chat_id:
                metadata["telegram_chat_id"] = body.telegram_chat_id

            session = stripe.checkout.Session.create(
                mode="subscription",
                customer_email=body.email,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=body.success_url,
                cancel_url=body.cancel_url,
                metadata=metadata,
                subscription_data={"metadata": metadata},
            )
            return success_response(
                {
                    "checkout_url": session.url,
                    "session_id": session.id,
                },
                "checkout_session",
                resource_id=session.id,
                status_code=201,
            )
        except stripe.StripeError as e:
            logger.error("Stripe checkout error: %s", e)
            return server_error(f"Stripe error: {e.user_message or str(e)}")

    # ------------------------------------------------------------------
    # Stripe Webhook
    # ------------------------------------------------------------------

    @app.post("/webhook", tags=["Webhook"])
    async def stripe_webhook(request: Request):
        """Handle Stripe webhook events."""
        start = time.monotonic()
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature", "")

        if metrics:
            metrics.stripe_webhooks_received.inc()

        if webhook_secret:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, webhook_secret
                )
            except stripe.SignatureVerificationError:
                logger.warning("Stripe webhook: invalid signature")
                if metrics:
                    metrics.stripe_webhooks_failed.inc()
                return error_response(
                    "INVALID_SIGNATURE", "Invalid webhook signature", 400
                )
            except ValueError:
                if metrics:
                    metrics.stripe_webhooks_failed.inc()
                return error_response("INVALID_PAYLOAD", "Invalid payload", 400)
        else:
            event = stripe.Event.construct_from(
                json_module.loads(payload), stripe.api_key
            )

        event_type = event["type"]
        event_id = event["id"]

        logger.info(
            "Stripe webhook received: event_type=%s event_id=%s",
            event_type,
            event_id,
        )

        # Deduplicate events
        async with db_pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM billing_events WHERE stripe_event_id = $1", event_id
            )
            if existing:
                logger.info("Stripe webhook deduplicated: %s", event_id)
                return success_response(
                    {"status": "already_processed"}, "webhook_result"
                )

        handlers = {
            "customer.subscription.created": _handle_subscription_created,
            "customer.subscription.updated": _handle_subscription_updated,
            "customer.subscription.deleted": _handle_subscription_cancelled,
            "invoice.payment_failed": _handle_payment_failed,
            "checkout.session.completed": _handle_checkout_completed,
        }

        handler = handlers.get(event_type)
        if handler:
            try:
                await handler(db_pool, event)
            except Exception as e:
                logger.error("Error handling %s: %s", event_type, e)
                if metrics:
                    metrics.stripe_webhooks_failed.inc()
                return server_error(f"Error processing event: {event_type}")

        # Record the event
        async with db_pool.acquire() as conn:
            sub_id = await _find_subscription_id(conn, event)
            await conn.execute(
                """INSERT INTO billing_events (stripe_event_id, event_type, subscription_id, payload)
                   VALUES ($1, $2, $3, $4)""",
                event_id,
                event_type,
                sub_id,
                str(payload.decode("utf-8")),
            )

        elapsed_ms = (time.monotonic() - start) * 1000
        if metrics:
            metrics.stripe_webhooks_processed.inc()
            metrics.stripe_webhook_latency_ms.observe(elapsed_ms)

        logger.info(
            "Stripe webhook processed: event_type=%s event_id=%s latency_ms=%.1f",
            event_type,
            event_id,
            elapsed_ms,
        )

        return success_response(
            {"status": "processed", "event_type": event_type}, "webhook_result"
        )

    # ------------------------------------------------------------------
    # Subscription Management
    # ------------------------------------------------------------------

    @app.get("/subscription", tags=["Subscription"])
    async def get_subscription(
        customer_id: Optional[str] = Query(None),
        email: Optional[str] = Query(None),
    ):
        """Get subscription details for a customer."""
        if not customer_id and not email:
            return validation_error("Provide either customer_id or email")

        async with db_pool.acquire() as conn:
            if customer_id:
                row = await conn.fetchrow(
                    """SELECT c.id, c.email, c.telegram_chat_id,
                              s.tier, s.status, s.current_period_end, s.cancel_at_period_end
                       FROM billing_customers c
                       LEFT JOIN billing_subscriptions s ON s.customer_id = c.id AND s.status = 'active'
                       WHERE c.id = $1::uuid""",
                    customer_id,
                )
            else:
                row = await conn.fetchrow(
                    """SELECT c.id, c.email, c.telegram_chat_id,
                              s.tier, s.status, s.current_period_end, s.cancel_at_period_end
                       FROM billing_customers c
                       LEFT JOIN billing_subscriptions s ON s.customer_id = c.id AND s.status = 'active'
                       WHERE c.email = $1""",
                    email,
                )

        if not row:
            identifier = customer_id or email
            return not_found("Customer", identifier)

        data = dict(row)
        data["id"] = str(data["id"])
        tier = data.get("tier") or "free"
        plan = get_plan(tier)
        data["plan"] = plan_to_dict(plan)
        if data.get("current_period_end"):
            data["current_period_end"] = data["current_period_end"].isoformat()
        return success_response(data, "subscription", resource_id=data["id"])

    @app.post("/portal", tags=["Subscription"])
    async def create_portal(body: PortalRequest):
        """Create a Stripe Customer Portal session for subscription management."""
        if not stripe.api_key:
            return server_error("Stripe is not configured")

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT stripe_customer_id FROM billing_customers WHERE id = $1::uuid",
                body.customer_id,
            )

        if not row:
            return not_found("Customer", body.customer_id)

        try:
            session = stripe.billing_portal.Session.create(
                customer=row["stripe_customer_id"],
                return_url=body.return_url,
            )
            return success_response(
                {"portal_url": session.url},
                "portal_session",
                status_code=201,
            )
        except stripe.StripeError as e:
            logger.error("Stripe portal error: %s", e)
            return server_error(f"Stripe error: {e.user_message or str(e)}")

    return app


# ------------------------------------------------------------------
# Webhook Event Handlers
# ------------------------------------------------------------------


async def _handle_checkout_completed(db_pool: asyncpg.Pool, event):
    """Handle checkout.session.completed — create customer record."""
    session = event["data"]["object"]
    customer_id = session.get("customer")
    email = session.get("customer_email") or session.get("customer_details", {}).get(
        "email", ""
    )
    metadata = session.get("metadata", {})
    telegram_chat_id = metadata.get("telegram_chat_id")

    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM billing_customers WHERE stripe_customer_id = $1",
            customer_id,
        )
        if not existing:
            await conn.execute(
                """INSERT INTO billing_customers (stripe_customer_id, email, telegram_chat_id)
                   VALUES ($1, $2, $3)""",
                customer_id,
                email,
                telegram_chat_id,
            )


async def _handle_subscription_created(db_pool: asyncpg.Pool, event):
    """Handle customer.subscription.created — record subscription."""
    sub = event["data"]["object"]
    stripe_sub_id = sub["id"]
    stripe_customer_id = sub["customer"]
    metadata = sub.get("metadata", {})
    tier = metadata.get("tier", "pro")
    status = sub.get("status", "active")

    period_start = datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc)
    period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)

    async with db_pool.acquire() as conn:
        # Ensure customer exists
        customer = await conn.fetchrow(
            "SELECT id FROM billing_customers WHERE stripe_customer_id = $1",
            stripe_customer_id,
        )
        if not customer:
            await conn.execute(
                "INSERT INTO billing_customers (stripe_customer_id, email) VALUES ($1, $2)",
                stripe_customer_id,
                "",
            )
            customer = await conn.fetchrow(
                "SELECT id FROM billing_customers WHERE stripe_customer_id = $1",
                stripe_customer_id,
            )

        await conn.execute(
            """INSERT INTO billing_subscriptions
               (customer_id, stripe_subscription_id, tier, status,
                current_period_start, current_period_end)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (stripe_subscription_id) DO UPDATE
               SET tier = $3, status = $4,
                   current_period_start = $5, current_period_end = $6,
                   updated_at = NOW()""",
            customer["id"],
            stripe_sub_id,
            tier,
            status,
            period_start,
            period_end,
        )


async def _handle_subscription_updated(db_pool: asyncpg.Pool, event):
    """Handle customer.subscription.updated — sync status and period."""
    sub = event["data"]["object"]
    stripe_sub_id = sub["id"]
    metadata = sub.get("metadata", {})
    tier = metadata.get("tier", "pro")
    status = sub.get("status", "active")
    cancel_at_end = sub.get("cancel_at_period_end", False)

    period_start = datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc)
    period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)

    async with db_pool.acquire() as conn:
        await conn.execute(
            """UPDATE billing_subscriptions
               SET tier = $1, status = $2, current_period_start = $3,
                   current_period_end = $4, cancel_at_period_end = $5, updated_at = NOW()
               WHERE stripe_subscription_id = $6""",
            tier,
            status,
            period_start,
            period_end,
            cancel_at_end,
            stripe_sub_id,
        )


async def _handle_subscription_cancelled(db_pool: asyncpg.Pool, event):
    """Handle customer.subscription.deleted — mark cancelled."""
    sub = event["data"]["object"]
    stripe_sub_id = sub["id"]

    async with db_pool.acquire() as conn:
        await conn.execute(
            """UPDATE billing_subscriptions
               SET status = 'cancelled', updated_at = NOW()
               WHERE stripe_subscription_id = $1""",
            stripe_sub_id,
        )


async def _handle_payment_failed(db_pool: asyncpg.Pool, event):
    """Handle invoice.payment_failed — mark subscription as past_due."""
    invoice = event["data"]["object"]
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    async with db_pool.acquire() as conn:
        await conn.execute(
            """UPDATE billing_subscriptions
               SET status = 'past_due', updated_at = NOW()
               WHERE stripe_subscription_id = $1""",
            stripe_sub_id,
        )


async def _find_subscription_id(conn, event):
    """Try to find the internal subscription UUID for an event."""
    obj = event["data"]["object"]
    stripe_sub_id = obj.get("id") or obj.get("subscription")
    if not stripe_sub_id:
        return None
    row = await conn.fetchrow(
        "SELECT id FROM billing_subscriptions WHERE stripe_subscription_id = $1",
        stripe_sub_id,
    )
    return row["id"] if row else None
