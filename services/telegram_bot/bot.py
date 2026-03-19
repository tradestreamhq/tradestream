"""
Telegram bot for TradeStream signal delivery.

Handles /start, /subscribe, /unsubscribe, /status commands.
Provides a send_signal method for pushing signals to subscribed users.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.telegram.org/bot{token}"


class TelegramSignalBot:
    """Telegram bot that manages signal subscriptions and delivers signals."""

    def __init__(self, bot_token: str, db_pool=None):
        self.bot_token = bot_token
        self.db_pool = db_pool
        self.api_url = BASE_URL.format(token=bot_token)

    # ------------------------------------------------------------------
    # Telegram API helpers
    # ------------------------------------------------------------------

    def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to a Telegram chat."""
        try:
            resp = requests.post(
                f"{self.api_url}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
                timeout=10,
            )
            if resp.status_code == 200:
                return True
            logger.warning("Telegram API returned %d: %s", resp.status_code, resp.text)
            return False
        except requests.RequestException as e:
            logger.error("Failed to send Telegram message: %s", e)
            return False

    def get_updates(self, offset: Optional[int] = None, timeout: int = 30) -> List[Dict]:
        """Long-poll for new messages."""
        params: Dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            resp = requests.get(
                f"{self.api_url}/getUpdates",
                params=params,
                timeout=timeout + 5,
            )
            if resp.status_code == 200:
                return resp.json().get("result", [])
            return []
        except requests.RequestException as e:
            logger.error("Failed to get updates: %s", e)
            return []

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def handle_command(self, chat_id: str, text: str) -> str:
        """Route a command and return the response text."""
        parts = text.strip().split()
        command = parts[0].lower().split("@")[0]  # strip @botname suffix

        handlers = {
            "/start": self._handle_start,
            "/subscribe": self._handle_subscribe,
            "/unsubscribe": self._handle_unsubscribe,
            "/status": self._handle_status,
            "/help": self._handle_start,
        }

        handler = handlers.get(command)
        if handler:
            return await handler(chat_id, parts[1:])
        return (
            "Unknown command. Use /start to see available commands."
        )

    async def _handle_start(self, chat_id: str, _args: List[str]) -> str:
        return (
            "<b>TradeStream Signal Bot</b>\n\n"
            "Receive real-time trading signals from your strategies.\n\n"
            "<b>Commands:</b>\n"
            "/subscribe — Start receiving signals\n"
            "/unsubscribe — Stop receiving signals\n"
            "/status — Check your subscription status\n"
            "/help — Show this message"
        )

    async def _handle_subscribe(self, chat_id: str, args: List[str]) -> str:
        if not self.db_pool:
            return "Bot is not connected to the database."

        async with self.db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM signal_subscriptions "
                "WHERE channel = 'telegram' AND endpoint = $1 AND active = true",
                chat_id,
            )
            if existing:
                return "You are already subscribed to signals."

            import uuid
            sub_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO signal_subscriptions
                   (id, channel, endpoint, strategies, pairs, active, created_at)
                   VALUES ($1, 'telegram', $2, NULL, NULL, true, NOW())""",
                sub_id,
                chat_id,
            )

        return (
            "Subscribed to trading signals!\n"
            f"Subscription ID: <code>{sub_id}</code>\n\n"
            "You will receive signals as they are generated."
        )

    async def _handle_unsubscribe(self, chat_id: str, _args: List[str]) -> str:
        if not self.db_pool:
            return "Bot is not connected to the database."

        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE signal_subscriptions SET active = false "
                "WHERE channel = 'telegram' AND endpoint = $1 AND active = true",
                chat_id,
            )
        if result == "UPDATE 0":
            return "You don't have an active subscription."
        return "Unsubscribed from trading signals."

    async def _handle_status(self, chat_id: str, _args: List[str]) -> str:
        if not self.db_pool:
            return "Bot is not connected to the database."

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, strategies, pairs, created_at "
                "FROM signal_subscriptions "
                "WHERE channel = 'telegram' AND endpoint = $1 AND active = true",
                chat_id,
            )
        if not row:
            return "No active subscription. Use /subscribe to start."

        strategies = row["strategies"] or ["all"]
        pairs = row["pairs"] or ["all"]
        created = row["created_at"].isoformat() if row["created_at"] else "unknown"

        return (
            "<b>Subscription Status</b>\n\n"
            f"ID: <code>{row['id']}</code>\n"
            f"Strategies: {', '.join(strategies)}\n"
            f"Pairs: {', '.join(pairs)}\n"
            f"Since: {created}"
        )

    # ------------------------------------------------------------------
    # Signal delivery
    # ------------------------------------------------------------------

    def format_signal(self, signal: Dict[str, Any]) -> str:
        """Format a trading signal for Telegram delivery."""
        direction = signal.get("direction") or signal.get("signal_type", "UNKNOWN")
        instrument = signal.get("instrument", "N/A")
        strategy = signal.get("strategy_name", "N/A")
        entry = signal.get("entry_price") or signal.get("price")
        sl = signal.get("stop_loss")
        tp = signal.get("take_profit")
        confidence = signal.get("confidence") or signal.get("strength", 0)

        emoji = {"BUY": "\u2b06\ufe0f", "SELL": "\u2b07\ufe0f"}.get(direction, "\u2753")

        lines = [
            f"{emoji} <b>{direction}</b> {instrument}",
            f"Strategy: {strategy}",
        ]
        if entry is not None:
            lines.append(f"Entry: <b>{entry}</b>")
        if sl is not None:
            lines.append(f"Stop Loss: {sl}")
        if tp is not None:
            lines.append(f"Take Profit: {tp}")
        if confidence:
            conf_val = confidence if isinstance(confidence, (int, float)) else 0
            lines.append(f"Confidence: <b>{conf_val:.0%}</b>")

        return "\n".join(lines)

    def deliver_signal(self, chat_id: str, signal: Dict[str, Any]) -> bool:
        """Format and send a signal to a Telegram chat."""
        text = self.format_signal(signal)
        return self.send_message(chat_id, text)
