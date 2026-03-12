"""Webhook sender with HMAC signature verification and retry logic."""

import hashlib
import hmac
import json
import time

import requests
from absl import logging
from tenacity import retry, stop_after_attempt, wait_exponential


class WebhookSender:
    """Sends trading signals to configured webhook endpoints with HMAC signing."""

    def __init__(self, webhook_url: str, signing_secret: str = ""):
        self.webhook_url = webhook_url
        self.signing_secret = signing_secret

    def send_signal(self, signal: dict) -> bool:
        """Send a trading signal as a signed JSON webhook POST.

        Returns:
            True if the webhook was delivered successfully.
        """
        payload = self._build_payload(signal)
        headers = self._build_headers(payload)

        try:
            return self._deliver(payload, headers)
        except Exception as e:
            logging.error("Webhook delivery failed after retries: %s", e)
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _deliver(self, payload: str, headers: dict) -> bool:
        """Deliver the webhook with retry logic."""
        resp = requests.post(
            self.webhook_url,
            data=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code < 300:
            logging.info("Webhook delivered to %s", self.webhook_url)
            return True
        if resp.status_code >= 500:
            raise requests.RequestException(
                f"Server error {resp.status_code}: {resp.text}"
            )
        logging.warning("Webhook returned %d: %s", resp.status_code, resp.text)
        return False

    def _build_payload(self, signal: dict) -> str:
        return json.dumps(signal, default=str, sort_keys=True)

    def _build_headers(self, payload: str) -> dict:
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-TradeStream-Timestamp": timestamp,
        }
        if self.signing_secret:
            signature = self._compute_signature(timestamp, payload)
            headers["X-TradeStream-Signature"] = signature
        return headers

    def _compute_signature(self, timestamp: str, payload: str) -> str:
        """Compute HMAC-SHA256 signature over timestamp + payload."""
        message = f"{timestamp}.{payload}"
        return hmac.new(
            self.signing_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
