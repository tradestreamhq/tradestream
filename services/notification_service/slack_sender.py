"""Slack sender for trading signals via incoming webhooks."""

import requests
from absl import logging


class SlackSender:
    """Sends trading signals to a Slack channel via incoming webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_signal(self, signal: dict) -> bool:
        """Format and send a trading signal as a Slack Block Kit message.

        Returns:
            True if the message was sent successfully.
        """
        blocks = self._build_blocks(signal)
        try:
            resp = requests.post(
                self.webhook_url,
                json={"blocks": blocks},
                timeout=10,
            )
            if resp.status_code == 200 and resp.text == "ok":
                logging.info("Slack message sent for %s", signal.get("symbol"))
                return True
            logging.warning(
                "Slack webhook returned %d: %s", resp.status_code, resp.text
            )
            return False
        except requests.RequestException as e:
            logging.error("Failed to send Slack message: %s", e)
            return False

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
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{symbol} Signal",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Action:* {emoji} {action}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence:* {confidence:.0%}",
                    },
                ],
            },
        ]

        if score:
            blocks[1]["fields"].append(
                {"type": "mrkdwn", "text": f"*Opportunity Score:* {score}"}
            )

        if summary:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": summary},
                }
            )

        return blocks
