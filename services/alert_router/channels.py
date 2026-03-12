"""Channel implementations for alert delivery."""

import hashlib
import hmac
import json
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional, Protocol

import requests
from absl import logging
from tenacity import retry, stop_after_attempt, wait_exponential

from services.alert_router.models import Alert, ChannelConfig


class Channel(Protocol):
    """Protocol for alert delivery channels."""

    def send(self, alert: Alert, template: Optional[str] = None) -> bool:
        """Send an alert. Returns True on success."""
        ...


class EmailChannel:
    """Delivers alerts via SMTP email."""

    def __init__(self, config: ChannelConfig):
        self.smtp_host = config.settings.get("smtp_host", "")
        self.smtp_port = int(config.settings.get("smtp_port", 587))
        self.username = config.settings.get("username", "")
        self.password = config.settings.get("password", "")
        self.from_addr = config.settings.get("from_address", "")
        self.to_addrs = config.settings.get("to_addresses", [])
        self.use_tls = config.settings.get("use_tls", True)

    def send(self, alert: Alert, template: Optional[str] = None) -> bool:
        if not self.smtp_host or not self.to_addrs:
            logging.warning("Email channel not configured")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[TradeStream Alert] {alert.title}"
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            body = self._format_body(alert, template)
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(self._format_html(alert, template), "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

            logging.info("Email alert sent to %s", self.to_addrs)
            return True
        except Exception as e:
            logging.error("Email delivery failed: %s", e)
            return False

    def _format_body(self, alert: Alert, template: Optional[str]) -> str:
        if template:
            return template.format(**alert.to_dict())
        return (
            f"Alert: {alert.title}\n"
            f"Type: {alert.alert_type}\n"
            f"Message: {alert.message}\n"
        )

    def _format_html(self, alert: Alert, template: Optional[str]) -> str:
        if template:
            return template.format(**alert.to_dict())
        return (
            f"<h2>{alert.title}</h2>"
            f"<p><strong>Type:</strong> {alert.alert_type}</p>"
            f"<p>{alert.message}</p>"
        )


class SlackWebhookChannel:
    """Delivers alerts via Slack incoming webhook."""

    def __init__(self, config: ChannelConfig):
        self.webhook_url = config.settings.get("webhook_url", "")

    def send(self, alert: Alert, template: Optional[str] = None) -> bool:
        if not self.webhook_url:
            logging.warning("Slack webhook URL not configured")
            return False

        payload = self._build_payload(alert, template)
        try:
            return self._deliver(payload)
        except Exception as e:
            logging.error("Slack delivery failed after retries: %s", e)
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _deliver(self, payload: Dict[str, Any]) -> bool:
        resp = requests.post(self.webhook_url, json=payload, timeout=10)
        if resp.status_code < 300:
            logging.info("Slack alert delivered")
            return True
        if resp.status_code >= 500:
            raise requests.RequestException(
                f"Slack server error {resp.status_code}: {resp.text}"
            )
        logging.warning("Slack returned %d: %s", resp.status_code, resp.text)
        return False

    def _build_payload(
        self, alert: Alert, template: Optional[str]
    ) -> Dict[str, Any]:
        if template:
            return {"text": template.format(**alert.to_dict())}
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": alert.title},
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Type:* {alert.alert_type}",
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Message:* {alert.message}",
                        },
                    ],
                },
            ]
        }


class CustomWebhookChannel:
    """Delivers alerts via custom HTTP webhook with HMAC signing."""

    def __init__(self, config: ChannelConfig):
        self.webhook_url = config.settings.get("webhook_url", "")
        self.signing_secret = config.settings.get("signing_secret", "")
        self.headers = config.settings.get("headers", {})

    def send(self, alert: Alert, template: Optional[str] = None) -> bool:
        if not self.webhook_url:
            logging.warning("Custom webhook URL not configured")
            return False

        payload = json.dumps(alert.to_dict(), default=str, sort_keys=True)
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
    def _deliver(self, payload: str, headers: Dict[str, str]) -> bool:
        resp = requests.post(
            self.webhook_url, data=payload, headers=headers, timeout=10
        )
        if resp.status_code < 300:
            logging.info("Webhook alert delivered to %s", self.webhook_url)
            return True
        if resp.status_code >= 500:
            raise requests.RequestException(
                f"Server error {resp.status_code}: {resp.text}"
            )
        logging.warning("Webhook returned %d: %s", resp.status_code, resp.text)
        return False

    def _build_headers(self, payload: str) -> Dict[str, str]:
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-TradeStream-Timestamp": timestamp,
            **self.headers,
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


class InAppChannel:
    """Stores alerts for in-app retrieval. Uses a provided store callback."""

    def __init__(self, config: ChannelConfig):
        self.store_fn = config.settings.get("store_fn")

    def send(self, alert: Alert, template: Optional[str] = None) -> bool:
        if self.store_fn and callable(self.store_fn):
            try:
                self.store_fn(alert.to_dict())
                logging.info("In-app alert stored for user %s", alert.user_id)
                return True
            except Exception as e:
                logging.error("In-app storage failed: %s", e)
                return False
        logging.info(
            "In-app alert logged (no store_fn): %s - %s",
            alert.alert_id,
            alert.title,
        )
        return True


CHANNEL_REGISTRY = {
    "email": EmailChannel,
    "slack_webhook": SlackWebhookChannel,
    "custom_webhook": CustomWebhookChannel,
    "in_app": InAppChannel,
}


def create_channel(config: ChannelConfig) -> Channel:
    """Factory to create a channel from config."""
    cls = CHANNEL_REGISTRY.get(config.channel_type.value)
    if cls is None:
        raise ValueError(f"Unknown channel type: {config.channel_type}")
    return cls(config)
