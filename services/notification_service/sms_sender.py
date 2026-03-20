"""SMS sender for critical trading signals via Twilio API."""

import requests
from absl import logging


class SmsSender:
    """Sends trading signals via SMS using the Twilio REST API.

    Intended for high-priority / critical signals only (e.g. stop-loss
    triggers, large drawdown alerts).
    """

    TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"

    # Only deliver signals at or above this priority by default.
    CRITICAL_PRIORITIES = frozenset({"critical", "high"})

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        to_number: str,
    ):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.to_number = to_number
        self.url = self.TWILIO_API_URL.format(sid=account_sid)

    @property
    def name(self) -> str:
        return "sms"

    def send_signal(self, signal: dict) -> bool:
        """Send a compact SMS for a trading signal.

        Returns:
            True if the Twilio API accepted the message.
        """
        body = self._format_signal(signal)
        try:
            resp = requests.post(
                self.url,
                data={
                    "From": self.from_number,
                    "To": self.to_number,
                    "Body": body,
                },
                auth=(self.account_sid, self.auth_token),
                timeout=10,
            )
            if resp.status_code in (200, 201):
                logging.info(
                    "SMS sent for %s to %s", signal.get("symbol"), self.to_number
                )
                return True
            logging.warning("Twilio returned %d: %s", resp.status_code, resp.text[:200])
            return False
        except requests.RequestException as e:
            logging.error("Failed to send SMS: %s", e)
            return False

    def supports_priority(self, priority: str) -> bool:
        """SMS is reserved for critical / high-priority signals."""
        return priority in self.CRITICAL_PRIORITIES

    def _format_signal(self, signal: dict) -> str:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        summary = signal.get("summary", "")

        msg = f"[TradeStream] {action} {symbol} (conf: {confidence:.0%})"
        if summary:
            # SMS has 160 char limit for single segment
            remaining = 160 - len(msg) - 2  # newline + space
            if remaining > 10:
                msg += f"\n{summary[:remaining]}"
        return msg
