"""Webhook delivery with HMAC-SHA256 signing and retry logic."""

import hashlib
import hmac
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

VALID_EVENT_TYPES = frozenset(
    {
        "trade.executed",
        "alert.triggered",
        "strategy.signal",
        "backtest.completed",
    }
)

# Retry backoff: 10s, 60s, 300s
RETRY_DELAYS_SECONDS = [10, 60, 300]


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for *payload_bytes* using *secret*."""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def build_delivery_headers(signature: str, event_type: str, delivery_id: str) -> dict:
    """Return headers sent with every webhook delivery."""
    return {
        "Content-Type": "application/json",
        "X-TradeStream-Signature": f"sha256={signature}",
        "X-TradeStream-Event": event_type,
        "X-TradeStream-Delivery": delivery_id,
    }


async def deliver_webhook(
    url: str,
    secret: str,
    event_type: str,
    payload: Dict[str, Any],
    delivery_id: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Send a single webhook delivery attempt.

    Returns a dict with ``success``, ``status_code``, ``response_body``, and
    ``error`` keys.
    """
    delivery_id = delivery_id or str(uuid.uuid4())
    payload_bytes = json.dumps(payload, default=str).encode("utf-8")
    signature = sign_payload(payload_bytes, secret)
    headers = build_delivery_headers(signature, event_type, delivery_id)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, content=payload_bytes, headers=headers, timeout=timeout
            )
        success = 200 <= resp.status_code < 300
        return {
            "success": success,
            "status_code": resp.status_code,
            "response_body": resp.text[:2000],
            "error": None,
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "status_code": None,
            "response_body": None,
            "error": "Request timed out",
        }
    except Exception as exc:
        return {
            "success": False,
            "status_code": None,
            "response_body": None,
            "error": str(exc)[:500],
        }


async def deliver_with_retries(
    db_pool,
    webhook_id: str,
    url: str,
    secret: str,
    event_type: str,
    payload: Dict[str, Any],
) -> str:
    """Create a delivery record and attempt delivery with retries.

    Returns the delivery id.
    """
    import json as _json

    delivery_id = str(uuid.uuid4())
    payload_json = _json.dumps(payload, default=str)

    # Insert delivery record
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO webhook_deliveries
                (id, webhook_id, event_type, payload, status, attempts, max_attempts)
            VALUES ($1::uuid, $2::uuid, $3, $4::jsonb, 'pending', 0, 3)
            """,
            delivery_id,
            webhook_id,
            event_type,
            payload_json,
        )

    for attempt in range(3):
        result = await deliver_webhook(
            url=url,
            secret=secret,
            event_type=event_type,
            payload=payload,
            delivery_id=delivery_id,
        )

        attempt_num = attempt + 1
        if result["success"]:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE webhook_deliveries
                    SET status = 'success', attempts = $2,
                        response_code = $3, response_body = $4,
                        completed_at = now()
                    WHERE id = $1::uuid
                    """,
                    delivery_id,
                    attempt_num,
                    result["status_code"],
                    result["response_body"],
                )
            logger.info("Webhook %s delivered on attempt %d", delivery_id, attempt_num)
            return delivery_id

        # Failed attempt — update record
        error_msg = result["error"] or f"HTTP {result['status_code']}"
        if attempt_num < 3:
            next_delay = RETRY_DELAYS_SECONDS[attempt]
            next_retry = datetime.now(timezone.utc).replace(
                microsecond=0
            )  # placeholder
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE webhook_deliveries
                    SET attempts = $2, response_code = $3,
                        response_body = $4, error_message = $5,
                        next_retry_at = now() + ($6 || ' seconds')::interval
                    WHERE id = $1::uuid
                    """,
                    delivery_id,
                    attempt_num,
                    result["status_code"],
                    result["response_body"],
                    error_msg,
                    str(next_delay),
                )
            logger.warning(
                "Webhook %s attempt %d failed: %s — retrying in %ds",
                delivery_id,
                attempt_num,
                error_msg,
                next_delay,
            )
        else:
            # Final failure
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE webhook_deliveries
                    SET status = 'failed', attempts = $2,
                        response_code = $3, response_body = $4,
                        error_message = $5, completed_at = now()
                    WHERE id = $1::uuid
                    """,
                    delivery_id,
                    attempt_num,
                    result["status_code"],
                    result["response_body"],
                    error_msg,
                )
            logger.error(
                "Webhook %s permanently failed after %d attempts",
                delivery_id,
                attempt_num,
            )

    return delivery_id
