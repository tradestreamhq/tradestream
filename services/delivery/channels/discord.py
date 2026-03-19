"""Discord delivery channel via webhooks."""

import requests
from absl import logging

from services.delivery.channels.base import DeliveryChannel, DeliveryResult


class DiscordDeliveryChannel(DeliveryChannel):
    """Delivers signals to Discord channels via webhook URLs."""

    @property
    def name(self) -> str:
        return "discord"

    def send(self, signal: dict, recipient: str) -> DeliveryResult:
        """Send signal to a Discord webhook URL (recipient = webhook URL)."""
        embed = self._build_embed(signal)
        try:
            resp = requests.post(
                recipient,
                json={"embeds": [embed]},
                timeout=10,
            )
            if resp.status_code in (200, 204):
                return DeliveryResult.ok(self.name)
            if resp.status_code == 404:
                return DeliveryResult.fail(
                    self.name, "Webhook not found", retryable=False
                )
            return DeliveryResult.fail(
                self.name,
                f"Discord {resp.status_code}: {resp.text}",
                retryable=resp.status_code >= 500 or resp.status_code == 429,
            )
        except requests.RequestException as e:
            return DeliveryResult.fail(self.name, str(e), retryable=True)

    def _build_embed(self, signal: dict) -> dict:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        score = signal.get("opportunity_score", 0)
        summary = signal.get("summary", "")

        color = {"BUY": 0x00CC00, "SELL": 0xCC0000, "HOLD": 0xFFAA00}.get(
            action, 0x808080
        )

        fields = [
            {"name": "Action", "value": action, "inline": True},
            {"name": "Confidence", "value": f"{confidence:.0%}", "inline": True},
        ]
        if score:
            fields.append(
                {"name": "Opportunity Score", "value": str(score), "inline": True}
            )

        embed = {"title": f"{symbol} Signal", "color": color, "fields": fields}
        if summary:
            embed["description"] = summary
        embed["footer"] = {"text": "Powered by TradeStream"}
        return embed
