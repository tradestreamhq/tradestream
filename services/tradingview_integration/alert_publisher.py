"""TradingView-compatible alert publisher.

Formats TradeStream internal signals as TradingView-style webhook payloads
and delivers them to configured TradingView-compatible endpoints.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class TradingViewAlertPublisher:
    """Publishes TradeStream signals as TradingView-compatible webhook payloads."""

    def __init__(self, webhook_url: str, timeout: int = 10):
        self.webhook_url = webhook_url
        self.timeout = timeout

    def publish_signal(self, signal: Dict[str, Any]) -> bool:
        """Convert an internal signal to TradingView format and POST it."""
        payload = self.format_payload(signal)
        try:
            return self._deliver(payload)
        except Exception:
            logger.exception("TradingView alert delivery failed after retries")
            return False

    @staticmethod
    def format_payload(signal: Dict[str, Any]) -> Dict[str, Any]:
        """Format an internal signal as a TradingView-compatible alert payload."""
        signal_type = signal.get("signal_type", "").upper()

        # Map internal signal types to TradingView actions
        action_map = {
            "BUY": "buy",
            "SELL": "sell",
            "STOP_LOSS": "close",
            "HOLD": "hold",
        }
        action = action_map.get(signal_type, signal_type.lower())

        payload: Dict[str, Any] = {
            "ticker": _instrument_to_ticker(signal.get("instrument", "")),
            "action": action,
            "price": signal.get("price"),
            "strategy": signal.get("strategy_name", "tradestream"),
            "time": signal.get("created_at") or str(int(time.time())),
        }

        if signal.get("stop_loss") is not None:
            payload["stoploss"] = signal["stop_loss"]
        if signal.get("take_profit") is not None:
            payload["takeprofit"] = signal["take_profit"]
        if signal.get("position_size") is not None:
            payload["quantity"] = signal["position_size"]

        return payload

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _deliver(self, payload: Dict[str, Any]) -> bool:
        """POST the alert payload with retry logic."""
        resp = requests.post(
            self.webhook_url,
            json=payload,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code < 300:
            logger.info("TradingView alert delivered to %s", self.webhook_url)
            return True
        if resp.status_code >= 500:
            raise requests.RequestException(
                f"Server error {resp.status_code}: {resp.text}"
            )
        logger.warning(
            "TradingView alert endpoint returned %d: %s",
            resp.status_code,
            resp.text,
        )
        return False


def _instrument_to_ticker(instrument: str) -> str:
    """Convert TradeStream instrument format to TradingView ticker.

    TradeStream: BTC/USD  -> TradingView: BTCUSD
    """
    return instrument.replace("/", "")
