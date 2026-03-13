"""Webhook dispatcher with HMAC signing, retry logic, and delivery logging."""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
import requests
from absl import logging
from tenacity import retry, stop_after_attempt, wait_exponential


class WebhookDispatcher:
    """Dispatches webhook payloads to registered URLs with signing and retries."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def dispatch_event(
        self, event_type: str, payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Dispatch an event to all matching active webhooks.

        Returns a list of delivery results.
        """
        webhooks = await self._get_matching_webhooks(event_type)
        results = []
        for webhook in webhooks:
            result = await self._deliver_to_webhook(webhook, event_type, payload)
            results.append(result)
        return results

    async def send_test(self, webhook_id: uuid.UUID) -> Dict[str, Any]:
        """Send a test payload to a specific webhook."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, url, signing_secret FROM webhooks WHERE id = $1",
                webhook_id,
            )
        if not row:
            return {"success": False, "error": "Webhook not found"}

        test_payload = {
            "event": "test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"message": "This is a test webhook delivery"},
        }
        return self._deliver_payload(
            url=row["url"],
            signing_secret=row["signing_secret"],
            payload=test_payload,
            webhook_id=row["id"],
            event_type="test",
        )

    async def _get_matching_webhooks(self, event_type: str) -> list:
        """Fetch active webhooks subscribed to the given event type."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, url, signing_secret
                   FROM webhooks
                   WHERE is_active = true AND $1 = ANY(events)""",
                event_type,
            )
        return [dict(row) for row in rows]

    async def _deliver_to_webhook(
        self,
        webhook: Dict[str, Any],
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deliver a payload to a single webhook and log the result."""
        event_payload = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }
        result = self._deliver_payload(
            url=webhook["url"],
            signing_secret=webhook["signing_secret"],
            payload=event_payload,
            webhook_id=webhook["id"],
            event_type=event_type,
        )
        await self._log_delivery(
            webhook_id=webhook["id"],
            event_type=event_type,
            payload=event_payload,
            result=result,
        )
        return result

    def _deliver_payload(
        self,
        url: str,
        signing_secret: str,
        payload: Dict[str, Any],
        webhook_id: uuid.UUID,
        event_type: str,
    ) -> Dict[str, Any]:
        """Send the HTTP POST with HMAC signing and retry on server errors."""
        json_payload = json.dumps(payload, default=str, sort_keys=True)
        timestamp = str(int(time.time()))
        signature = compute_signature(signing_secret, timestamp, json_payload)

        headers = {
            "Content-Type": "application/json",
            "X-TradeStream-Timestamp": timestamp,
            "X-TradeStream-Signature": signature,
            "X-TradeStream-Event": event_type,
        }

        try:
            response_code = _send_with_retries(url, json_payload, headers)
            return {
                "webhook_id": str(webhook_id),
                "success": True,
                "status_code": response_code,
            }
        except Exception as e:
            logging.error("Webhook delivery to %s failed after retries: %s", url, e)
            return {
                "webhook_id": str(webhook_id),
                "success": False,
                "error": str(e),
            }

    async def _log_delivery(
        self,
        webhook_id: uuid.UUID,
        event_type: str,
        payload: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Record delivery attempt in the webhook_deliveries table."""
        status = "success" if result.get("success") else "failed"
        response_code = result.get("status_code")
        error_message = result.get("error")

        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO webhook_deliveries
                       (id, webhook_id, event_type, payload, status,
                        response_code, error_message, created_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    uuid.uuid4(),
                    webhook_id,
                    event_type,
                    json.dumps(payload, default=str),
                    status,
                    response_code,
                    error_message,
                    datetime.now(timezone.utc),
                )
        except Exception as e:
            logging.error("Failed to log webhook delivery: %s", e)


def compute_signature(secret: str, timestamp: str, payload: str) -> str:
    """Compute HMAC-SHA256 signature over timestamp + payload."""
    message = f"{timestamp}.{payload}"
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def _send_with_retries(url: str, payload: str, headers: dict) -> int:
    """Send HTTP POST with retries on server errors."""
    resp = requests.post(url, data=payload, headers=headers, timeout=10)
    if resp.status_code >= 500:
        raise requests.RequestException(f"Server error {resp.status_code}: {resp.text}")
    if resp.status_code >= 300:
        raise requests.RequestException(f"Client error {resp.status_code}: {resp.text}")
    return resp.status_code
