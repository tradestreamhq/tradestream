"""Telegram sender for trading signals."""

import requests
from absl import logging


class TelegramSender:
    """Sends trading signals to a Telegram chat via the Bot API."""

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.url = self.BASE_URL.format(token=bot_token)

    def send_signal(self, signal: dict) -> bool:
        """Format and send a trading signal to Telegram.

        Returns:
            True if the message was sent successfully.
        """
        text = self._format_signal(signal)
        try:
            resp = requests.post(
                self.url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                logging.info("Telegram message sent for %s", signal.get("symbol"))
                return True
            logging.warning("Telegram API returned %d: %s", resp.status_code, resp.text)
            return False
        except requests.RequestException as e:
            logging.error("Failed to send Telegram message: %s", e)
            return False

    def _format_signal(self, signal: dict) -> str:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        score = signal.get("opportunity_score", 0)
        summary = signal.get("summary", "")

        emoji = {
            "BUY": "\u2b06\ufe0f",
            "SELL": "\u2b07\ufe0f",
            "HOLD": "\u23f8\ufe0f",
        }.get(action, "\u2753")

        lines = [
            f"{emoji} <b>{action}</b> {symbol}",
            f"Confidence: <b>{confidence:.0%}</b>",
        ]
        if score:
            lines.append(f"Opportunity Score: <b>{score}</b>")
        if summary:
            lines.append(f"\n{summary}")
        return "\n".join(lines)
