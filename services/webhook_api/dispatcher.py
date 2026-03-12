"""
Webhook event dispatcher with HMAC-SHA256 signing and exponential backoff retry.

Usage:
    dispatcher = WebhookDispatcher(db_pool)
    await dispatcher.dispatch_event("trade_executed", {"symbol": "BTC/USD", ...})
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, List

import asyncpg
import requests

logger = logging.getLogger(__name__)

DEFAULT_BACKOFF = [1, 5, 30]


def compute_signature(secret: str, timestamp: str, payload: str) -> str:
    """Compute HMAC-SHA256 signature over timestamp.payload."""
    message = f"{timestamp}.{payload}"
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_headers(secret: str, payload: str) -> dict:
    """Build webhook request headers with optional HMAC signature."""
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-TradeStream-Timestamp": timestamp,
    }
    if secret:
        headers["X-TradeStream-Signature"] = compute_signature(
            secret, timestamp, payload
        )
    return headers


class WebhookDispatcher:
    """Dispatches events to subscribed webhooks with retry logic."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def dispatch_event(
        self, event_type: str, data: Dict[str, Any]
    ) -> List[dict]:
        """Dispatch an event to all active webhooks subscribed to this event type.

        Returns a list of delivery result dicts.
        """
        async with self.db_pool.acquire() as conn:
            webhooks = await conn.fetch(
                """
                SELECT id, url, secret, retry_policy
                FROM webhooks
                WHERE is_active = TRUE AND $1 = ANY(event_types)
                """,
                event_type,
            )

        results = []
        for webhook in webhooks:
            result = await self._deliver_to_webhook(webhook, event_type, data)
            results.append(result)
        return results

    async def _deliver_to_webhook(
        self, webhook, event_type: str, data: Dict[str, Any]
    ) -> dict:
        """Deliver event to a single webhook with retry logic."""
        webhook_id = webhook["id"]
        retry_policy = webhook["retry_policy"]
        if isinstance(retry_policy, str):
            retry_policy = json.loads(retry_policy)

        max_retries = retry_policy.get("max_retries", 3)
        backoff = retry_policy.get("backoff_seconds", DEFAULT_BACKOFF)

        payload_dict = {
            "event_type": event_type,
            "webhook_id": str(webhook_id),
            "timestamp": int(time.time()),
            "data": data,
        }
        payload_str = json.dumps(payload_dict, default=str, sort_keys=True)

        last_result = None
        for attempt in range(1, max_retries + 1):
            result = self._attempt_delivery(
                webhook["url"], webhook["secret"], payload_str, attempt
            )
            last_result = result

            # Record delivery attempt
            await self._record_delivery(
                webhook_id, event_type, payload_dict, result, attempt
            )

            if result["success"]:
                return result

            # Wait before retry (except on last attempt)
            if attempt < max_retries:
                delay = backoff[min(attempt - 1, len(backoff) - 1)]
                time.sleep(delay)

        return last_result

    def _attempt_delivery(
        self, url: str, secret: str, payload_str: str, attempt: int
    ) -> dict:
        """Make a single delivery attempt."""
        headers = build_headers(secret, payload_str)
        start = time.monotonic()

        try:
            resp = requests.post(url, data=payload_str, headers=headers, timeout=10)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "success": resp.status_code < 300,
                "status_code": resp.status_code,
                "response_body": resp.text[:1000],
                "response_time_ms": elapsed_ms,
                "attempt": attempt,
                "error": None,
            }
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "success": False,
                "status_code": None,
                "response_body": None,
                "response_time_ms": elapsed_ms,
                "attempt": attempt,
                "error": str(e)[:1000],
            }

    async def _record_delivery(
        self,
        webhook_id,
        event_type: str,
        payload: dict,
        result: dict,
        attempt: int,
    ):
        """Record a delivery attempt in the database."""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO webhook_deliveries
                        (webhook_id, event_type, payload, status_code,
                         response_body, response_time_ms, attempt, success, error)
                    VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, $8, $9)
                    """,
                    webhook_id,
                    event_type,
                    json.dumps(payload),
                    result.get("status_code"),
                    result.get("response_body"),
                    result.get("response_time_ms"),
                    attempt,
                    result.get("success", False),
                    result.get("error"),
                )
        except Exception as e:
            logger.error("Failed to record delivery: %s", e)
