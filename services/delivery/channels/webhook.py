"""Webhook delivery channel with HMAC signing."""

import hashlib
import hmac
import json
import time

import requests
from absl import logging

from services.delivery.channels.base import DeliveryChannel, DeliveryResult


class WebhookDeliveryChannel(DeliveryChannel):
    """Delivers signals to HTTP webhook endpoints with HMAC-SHA256 signing."""

    def __init__(self, signing_secret: str = ""):
        self.signing_secret = signing_secret

    @property
    def name(self) -> str:
        return "webhook"

    def send(self, signal: dict, recipient: str) -> DeliveryResult:
        """Send signal to a webhook URL (recipient = URL)."""
        payload = json.dumps(signal, default=str, sort_keys=True)
        headers = self._build_headers(payload)
        try:
            resp = requests.post(recipient, data=payload, headers=headers, timeout=10)
            if resp.status_code < 300:
                return DeliveryResult.ok(self.name)
            if resp.status_code >= 500:
                return DeliveryResult.fail(
                    self.name,
                    f"Server error {resp.status_code}: {resp.text}",
                    retryable=True,
                )
            return DeliveryResult.fail(
                self.name,
                f"Webhook {resp.status_code}: {resp.text}",
                retryable=False,
            )
        except requests.RequestException as e:
            return DeliveryResult.fail(self.name, str(e), retryable=True)

    def _build_headers(self, payload: str) -> dict:
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-TradeStream-Timestamp": timestamp,
        }
        if self.signing_secret:
            message = f"{timestamp}.{payload}"
            signature = hmac.new(
                self.signing_secret.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            headers["X-TradeStream-Signature"] = signature
        return headers
