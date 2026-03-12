"""Webhook delivery engine with HMAC signing and exponential backoff retry."""

import hashlib
import hmac
import json
import time

import requests
from absl import logging

from services.webhook.models import (
    DeliveryRecord,
    DeliveryStatus,
    WebhookEvent,
    WebhookRegistration,
)


MAX_ATTEMPTS = 3
BACKOFF_BASE = 2
BACKOFF_MAX = 30
REQUEST_TIMEOUT = 10


def compute_signature(secret: str, timestamp: str, payload: str) -> str:
    """Compute HMAC-SHA256 signature over timestamp + payload."""
    message = f"{timestamp}.{payload}"
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    secret: str, timestamp: str, payload: str, signature: str
) -> bool:
    """Verify an incoming webhook signature."""
    expected = compute_signature(secret, timestamp, payload)
    return hmac.compare_digest(expected, signature)


def build_headers(secret: str, payload: str) -> dict:
    """Build HTTP headers for a webhook request, including HMAC signature."""
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


def deliver(
    registration: WebhookRegistration,
    event: WebhookEvent,
    max_attempts: int = MAX_ATTEMPTS,
) -> DeliveryRecord:
    """Deliver a webhook event to a registered endpoint with retry.

    Uses exponential backoff: 2^attempt seconds (capped at BACKOFF_MAX).
    Returns a DeliveryRecord with the final status.
    """
    record = DeliveryRecord.create(
        webhook_id=registration.webhook_id,
        event_id=event.event_id,
        event_type=event.event_type,
        max_attempts=max_attempts,
    )

    envelope = {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "data": event.payload,
    }
    payload = json.dumps(envelope, default=str, sort_keys=True)

    last_error = ""
    for attempt in range(1, max_attempts + 1):
        record.attempt = attempt
        try:
            headers = build_headers(registration.secret, payload)
            resp = requests.post(
                registration.url,
                data=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code < 300:
                logging.info(
                    "Webhook %s delivered to %s (attempt %d)",
                    event.event_id,
                    registration.url,
                    attempt,
                )
                record.mark_delivered(resp.status_code)
                return record

            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code < 500:
                logging.warning(
                    "Webhook %s rejected by %s: %s",
                    event.event_id,
                    registration.url,
                    last_error,
                )
                record.mark_failed(last_error, resp.status_code)
                return record

            logging.warning(
                "Webhook %s attempt %d/%d failed: %s",
                event.event_id,
                attempt,
                max_attempts,
                last_error,
            )
        except requests.RequestException as exc:
            last_error = str(exc)
            logging.warning(
                "Webhook %s attempt %d/%d error: %s",
                event.event_id,
                attempt,
                max_attempts,
                last_error,
            )

        if attempt < max_attempts:
            backoff = min(BACKOFF_BASE**attempt, BACKOFF_MAX)
            time.sleep(backoff)

    record.mark_failed(last_error)
    logging.error(
        "Webhook %s delivery to %s failed after %d attempts: %s",
        event.event_id,
        registration.url,
        max_attempts,
        last_error,
    )
    return record
