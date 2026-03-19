"""SMS delivery channel via Twilio API."""

import requests
from absl import logging

from services.delivery.channels.base import DeliveryChannel, DeliveryResult


class SMSDeliveryChannel(DeliveryChannel):
    """Delivers critical signals via SMS using the Twilio API.

    Only sends for high-priority signals (HOT tier or opportunity_score >= 80).
    """

    TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    MIN_SCORE_FOR_SMS = 80

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.url = self.TWILIO_API_URL.format(sid=account_sid)

    @property
    def name(self) -> str:
        return "sms"

    def send(self, signal: dict, recipient: str) -> DeliveryResult:
        """Send SMS to recipient (phone number in E.164 format)."""
        if not self._is_critical(signal):
            return DeliveryResult.fail(
                self.name,
                "Signal below SMS threshold (score < 80 or tier != HOT)",
                retryable=False,
            )

        body = self._format(signal)
        try:
            resp = requests.post(
                self.url,
                data={"To": recipient, "From": self.from_number, "Body": body},
                auth=(self.account_sid, self.auth_token),
                timeout=10,
            )
            if resp.status_code == 201:
                data = resp.json()
                return DeliveryResult.ok(self.name, external_id=data.get("sid", ""))
            if resp.status_code == 400:
                return DeliveryResult.fail(
                    self.name, f"Invalid request: {resp.text}", retryable=False
                )
            return DeliveryResult.fail(
                self.name,
                f"Twilio {resp.status_code}: {resp.text}",
                retryable=resp.status_code >= 500,
            )
        except requests.RequestException as e:
            return DeliveryResult.fail(self.name, str(e), retryable=True)

    def validate_recipient(self, recipient: str) -> bool:
        """Validate E.164 phone number format."""
        return (
            recipient.startswith("+")
            and len(recipient) >= 8
            and recipient[1:].isdigit()
        )

    def _is_critical(self, signal: dict) -> bool:
        """Check if signal meets SMS criticality threshold."""
        tier = signal.get("opportunity_tier", signal.get("tier", ""))
        score = signal.get("opportunity_score", 0)
        return tier == "HOT" or score >= self.MIN_SCORE_FOR_SMS

    def _format(self, signal: dict) -> str:
        action = signal.get("action", "UNKNOWN")
        symbol = signal.get("symbol", "N/A")
        confidence = signal.get("confidence", 0)
        score = signal.get("opportunity_score", 0)

        return (
            f"TradeStream: {action} {symbol}\n"
            f"Score: {score} | Confidence: {confidence:.0%}\n"
            f"View: https://app.tradestream.io"
        )
