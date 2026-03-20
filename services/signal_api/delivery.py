"""
Signal delivery service.

Listens for new signals on Redis pub/sub and fans out to all active
subscribers (Telegram chats and webhook endpoints).

Integrates with pipeline metrics, circuit breaker, and dead letter queue
for reliable delivery with observability.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import asyncpg
import redis

from services.notification_service.telegram_sender import TelegramSender
from services.notification_service.webhook_sender import WebhookSender
from services.shared.circuit_breaker import CircuitBreaker
from services.shared.dead_letter_queue import DeadLetterQueue
from services.shared.pipeline_metrics import PipelineMetrics

logger = logging.getLogger(__name__)


class SignalDeliveryService:
    """Consumes signals from Redis and delivers to subscribers.

    Supports optional metrics collection, circuit breaking for Telegram,
    and dead letter queue for failed deliveries.
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        redis_client: redis.Redis,
        telegram_bot_token: str = "",
        metrics: Optional[PipelineMetrics] = None,
        telegram_circuit_breaker: Optional[CircuitBreaker] = None,
        dlq: Optional[DeadLetterQueue] = None,
    ):
        self.db_pool = db_pool
        self.redis_client = redis_client
        self.telegram_bot_token = telegram_bot_token
        self.metrics = metrics
        self.telegram_cb = telegram_circuit_breaker
        self.dlq = dlq

    async def get_active_subscriptions(
        self, strategy_name: str = None, instrument: str = None
    ) -> List[Dict[str, Any]]:
        """Fetch active subscriptions that match the signal."""
        query = """
            SELECT id, channel, endpoint, strategies, pairs
            FROM signal_subscriptions
            WHERE active = true
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        subs = []
        for row in rows:
            sub = dict(row)
            # Filter by strategy if subscriber specified strategies
            if sub["strategies"] and strategy_name:
                if strategy_name not in sub["strategies"]:
                    continue
            # Filter by pair if subscriber specified pairs
            if sub["pairs"] and instrument:
                if instrument not in sub["pairs"]:
                    continue
            subs.append(sub)
        return subs

    def deliver_to_telegram(self, chat_id: str, signal: Dict[str, Any]) -> bool:
        """Send signal to a Telegram subscriber, with circuit breaker protection."""
        if not self.telegram_bot_token:
            logger.warning("No Telegram bot token configured; skipping delivery")
            return False

        # Check circuit breaker before calling Telegram API
        if self.telegram_cb and not self.telegram_cb.allow_request():
            logger.warning(
                "Telegram circuit breaker OPEN, skipping delivery to %s", chat_id
            )
            if self.metrics:
                self.metrics.telegram_circuit_breaker_trips.inc()
            return False

        start = time.monotonic()
        sender = TelegramSender(self.telegram_bot_token, chat_id)
        mapped = {
            "action": signal.get("direction") or signal.get("signal_type", "UNKNOWN"),
            "symbol": signal.get("instrument", "N/A"),
            "confidence": signal.get("confidence") or signal.get("strength", 0),
            "opportunity_score": 0,
            "summary": _build_summary(signal),
        }
        ok = sender.send_signal(mapped)
        elapsed_ms = (time.monotonic() - start) * 1000

        if self.metrics:
            self.metrics.telegram_api_calls.inc()
            self.metrics.telegram_api_latency_ms.observe(elapsed_ms)

        if ok:
            if self.telegram_cb:
                self.telegram_cb.record_success()
        else:
            if self.metrics:
                self.metrics.telegram_api_errors.inc()
            if self.telegram_cb:
                self.telegram_cb.record_failure()

        return ok

    def deliver_to_webhook(
        self, url: str, signal: Dict[str, Any], signing_secret: str = ""
    ) -> bool:
        """Send signal to a webhook subscriber."""
        sender = WebhookSender(url, signing_secret)
        return sender.send_signal(signal)

    def _enqueue_to_dlq(self, signal: Dict[str, Any], sub: Dict[str, Any], error: str):
        """Enqueue a failed delivery to the dead letter queue."""
        if not self.dlq:
            return
        self.dlq.enqueue(
            signal=signal,
            subscriber_id=str(sub["id"]),
            channel=sub["channel"],
            endpoint=sub["endpoint"],
            error=error,
        )
        if self.metrics:
            self.metrics.dlq_enqueued.inc()

    async def deliver_signal(self, signal: Dict[str, Any]) -> Dict[str, int]:
        """Fan out a signal to all matching subscribers.

        Returns counts of successful and failed deliveries.
        """
        strategy = signal.get("strategy_name")
        instrument = signal.get("instrument")
        subs = await self.get_active_subscriptions(strategy, instrument)

        delivered = 0
        failed = 0

        for sub in subs:
            if self.metrics:
                self.metrics.deliveries_attempted.inc()

            start = time.monotonic()
            try:
                if sub["channel"] == "telegram":
                    ok = self.deliver_to_telegram(sub["endpoint"], signal)
                elif sub["channel"] == "webhook":
                    ok = self.deliver_to_webhook(sub["endpoint"], signal)
                else:
                    logger.warning("Unknown channel: %s", sub["channel"])
                    ok = False

                elapsed_ms = (time.monotonic() - start) * 1000

                if ok:
                    delivered += 1
                    if self.metrics:
                        self.metrics.deliveries_succeeded.inc()
                        self.metrics.record_channel_success(sub["channel"])
                        self.metrics.delivery_latency_ms.observe(elapsed_ms)
                else:
                    failed += 1
                    if self.metrics:
                        self.metrics.deliveries_failed.inc()
                        self.metrics.record_channel_failure(sub["channel"])
                    self._enqueue_to_dlq(signal, sub, "delivery_returned_false")
            except Exception as e:
                logger.error("Delivery failed for sub %s: %s", sub["id"], e)
                failed += 1
                if self.metrics:
                    self.metrics.deliveries_failed.inc()
                    self.metrics.record_channel_failure(sub["channel"])
                self._enqueue_to_dlq(signal, sub, str(e))

        logger.info(
            "Signal delivery complete: %d delivered, %d failed for %s %s",
            delivered,
            failed,
            strategy,
            instrument,
        )
        return {"delivered": delivered, "failed": failed}

    def listen_and_deliver(self, channels: List[str] = None):
        """Subscribe to Redis channels and deliver signals.

        This is a blocking call that runs the pub/sub listener.
        """
        pubsub = self.redis_client.pubsub()
        patterns = channels or ["signals:*"]
        pubsub.psubscribe(*patterns)

        logger.info("Listening for signals on %s", patterns)
        loop = asyncio.new_event_loop()

        try:
            for message in pubsub.listen():
                if message["type"] not in ("pmessage", "message"):
                    continue
                try:
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    signal = json.loads(data)
                    loop.run_until_complete(self.deliver_signal(signal))
                except (json.JSONDecodeError, Exception) as e:
                    logger.error("Error processing signal message: %s", e)
        finally:
            loop.close()


def _build_summary(signal: Dict[str, Any]) -> str:
    """Build a summary line from signal fields."""
    parts = []
    strategy = signal.get("strategy_name")
    if strategy:
        parts.append(f"Strategy: {strategy}")
    entry = signal.get("entry_price") or signal.get("price")
    if entry is not None:
        parts.append(f"Entry: {entry}")
    sl = signal.get("stop_loss")
    if sl is not None:
        parts.append(f"SL: {sl}")
    tp = signal.get("take_profit")
    if tp is not None:
        parts.append(f"TP: {tp}")
    return " | ".join(parts)
