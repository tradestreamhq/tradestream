"""Telegram delivery channel."""

import requests
from absl import logging

from services.delivery.channels.base import DeliveryChannel, DeliveryResult


class TelegramDeliveryChannel(DeliveryChannel):
    """Delivers signals via the Telegram Bot API."""

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.url = self.BASE_URL.format(token=bot_token)

    @property
    def name(self) -> str:
        return "telegram"

    def send(self, signal: dict, recipient: str) -> DeliveryResult:
        text = self._format(signal)
        try:
            resp = requests.post(
                self.url,
                json={"chat_id": recipient, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                msg_id = str(data.get("result", {}).get("message_id", ""))
                return DeliveryResult.ok(self.name, external_id=msg_id)
            if resp.status_code == 403:
                return DeliveryResult.fail(
                    self.name, f"Bot blocked by user: {resp.text}", retryable=False
                )
            return DeliveryResult.fail(
                self.name,
                f"Telegram API {resp.status_code}: {resp.text}",
                retryable=resp.status_code >= 500,
            )
        except requests.RequestException as e:
            return DeliveryResult.fail(self.name, str(e), retryable=True)

    def _format(self, signal: dict) -> str:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        score = signal.get("opportunity_score", 0)
        summary = signal.get("summary", "")

        emoji = {"BUY": "\u2b06\ufe0f", "SELL": "\u2b07\ufe0f", "HOLD": "\u23f8\ufe0f"}.get(
            action, "\u2753"
        )

        lines = [f"{emoji} <b>{action}</b> {symbol}", f"Confidence: <b>{confidence:.0%}</b>"]
        if score:
            lines.append(f"Opportunity Score: <b>{score}</b>")
        if summary:
            lines.append(f"\n{summary}")
        return "\n".join(lines)
