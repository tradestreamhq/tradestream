"""Discord sender for trading signals via webhooks."""

import requests
from absl import logging


class DiscordSender:
    """Sends trading signals to a Discord channel via webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_signal(self, signal: dict) -> bool:
        """Format and send a trading signal as a Discord embed.

        Returns:
            True if the message was sent successfully.
        """
        embed = self._build_embed(signal)
        try:
            resp = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=10,
            )
            if resp.status_code in (200, 204):
                logging.info("Discord message sent for %s", signal.get("symbol"))
                return True
            logging.warning(
                "Discord webhook returned %d: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logging.error("Failed to send Discord message: %s", e)
            return False

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

        embed = {
            "title": f"{symbol} Signal",
            "color": color,
            "fields": fields,
        }
        if summary:
            embed["description"] = summary
        return embed
