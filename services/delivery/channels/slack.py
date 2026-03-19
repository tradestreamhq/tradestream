"""Slack delivery channel via incoming webhooks."""

import requests
from absl import logging

from services.delivery.channels.base import DeliveryChannel, DeliveryResult


class SlackDeliveryChannel(DeliveryChannel):
    """Delivers signals to Slack via incoming webhook URLs."""

    @property
    def name(self) -> str:
        return "slack"

    def send(self, signal: dict, recipient: str) -> DeliveryResult:
        """Send signal to a Slack webhook URL (recipient = webhook URL)."""
        blocks = self._build_blocks(signal)
        fallback = f"{signal.get('action', '')} {signal.get('symbol', '')} - Score: {signal.get('opportunity_score', 0)}"
        try:
            resp = requests.post(
                recipient,
                json={"blocks": blocks, "text": fallback},
                timeout=10,
            )
            if resp.status_code == 200 and resp.text == "ok":
                return DeliveryResult.ok(self.name)
            if resp.status_code == 404:
                return DeliveryResult.fail(self.name, "Webhook not found", retryable=False)
            return DeliveryResult.fail(
                self.name,
                f"Slack {resp.status_code}: {resp.text}",
                retryable=resp.status_code >= 500 or resp.status_code == 429,
            )
        except requests.RequestException as e:
            return DeliveryResult.fail(self.name, str(e), retryable=True)

    def _build_blocks(self, signal: dict) -> list:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        score = signal.get("opportunity_score", 0)
        summary = signal.get("summary", "")

        emoji = {
            "BUY": ":chart_with_upwards_trend:",
            "SELL": ":chart_with_downwards_trend:",
            "HOLD": ":pause_button:",
        }.get(action, ":grey_question:")

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"{symbol} Signal"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Action:* {emoji} {action}"},
                    {"type": "mrkdwn", "text": f"*Confidence:* {confidence:.0%}"},
                ],
            },
        ]

        if score:
            blocks[1]["fields"].append(
                {"type": "mrkdwn", "text": f"*Opportunity Score:* {score}"}
            )

        if summary:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": summary}})

        return blocks
