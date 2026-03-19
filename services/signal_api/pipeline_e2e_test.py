"""End-to-end signal pipeline test.

Verifies the full path: generate signal -> deliver to subscriber -> verify receipt.
Uses mocked external services (Telegram API, database) but exercises real
metrics collection, circuit breaker, DLQ, and alerting logic.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.shared.alerting import AlertEvaluator
from services.shared.circuit_breaker import CircuitBreaker
from services.shared.dead_letter_queue import DeadLetterQueue
from services.shared.pipeline_metrics import PipelineMetrics
from services.signal_api.delivery import SignalDeliveryService


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


class TestSignalPipelineE2E:
    """End-to-end tests for the signal delivery pipeline with full monitoring."""

    @pytest.fixture
    def pipeline(self):
        pool, conn = _make_pool()
        redis_client = MagicMock()
        metrics = PipelineMetrics()
        cb = CircuitBreaker("telegram-api", failure_threshold=3, recovery_timeout=60)
        dlq = DeadLetterQueue(redis_client, max_retries=3, base_delay=10)

        svc = SignalDeliveryService(
            db_pool=pool,
            redis_client=redis_client,
            telegram_bot_token="test-token",
            metrics=metrics,
            telegram_circuit_breaker=cb,
            dlq=dlq,
        )
        return svc, conn, metrics, cb, dlq

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_successful_delivery_updates_metrics(self, mock_sender_cls, pipeline):
        svc, conn, metrics, cb, dlq = pipeline
        mock_sender = MagicMock()
        mock_sender.send_signal.return_value = True
        mock_sender_cls.return_value = mock_sender

        conn.fetch.return_value = [
            FakeRecord(
                id=str(uuid.uuid4()),
                channel="telegram",
                endpoint="12345",
                strategies=None,
                pairs=None,
            )
        ]

        signal = {
            "strategy_name": "momentum_btc",
            "instrument": "BTC/USD",
            "direction": "BUY",
            "confidence": 0.85,
            "entry_price": 65000,
        }

        result = await svc.deliver_signal(signal)

        assert result["delivered"] == 1
        assert result["failed"] == 0

        # Verify metrics
        assert metrics.deliveries_attempted.value == 1
        assert metrics.deliveries_succeeded.value == 1
        assert metrics.deliveries_failed.value == 0
        assert metrics.telegram_api_calls.value == 1
        assert metrics.telegram_api_errors.value == 0
        assert metrics.delivery_latency_ms.count == 1

        # Verify circuit breaker remains closed
        assert cb.state == "closed"

        # Verify no DLQ entries
        dlq.redis.lpush.assert_not_called()

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_failed_delivery_updates_metrics_and_dlq(
        self, mock_sender_cls, pipeline
    ):
        svc, conn, metrics, cb, dlq = pipeline
        mock_sender = MagicMock()
        mock_sender.send_signal.return_value = False
        mock_sender_cls.return_value = mock_sender

        sub_id = str(uuid.uuid4())
        conn.fetch.return_value = [
            FakeRecord(
                id=sub_id,
                channel="telegram",
                endpoint="12345",
                strategies=None,
                pairs=None,
            )
        ]

        signal = {
            "strategy_name": "test_strategy",
            "instrument": "ETH/USD",
            "direction": "SELL",
        }

        result = await svc.deliver_signal(signal)

        assert result["delivered"] == 0
        assert result["failed"] == 1

        # Verify metrics
        assert metrics.deliveries_attempted.value == 1
        assert metrics.deliveries_failed.value == 1
        assert metrics.telegram_api_errors.value == 1

        # Verify DLQ enqueue
        assert metrics.dlq_enqueued.value == 1
        assert dlq.redis.lpush.called

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_circuit_breaker_opens_after_failures(
        self, mock_sender_cls, pipeline
    ):
        svc, conn, metrics, cb, dlq = pipeline
        mock_sender = MagicMock()
        mock_sender.send_signal.return_value = False
        mock_sender_cls.return_value = mock_sender

        conn.fetch.return_value = [
            FakeRecord(
                id="sub-1",
                channel="telegram",
                endpoint="12345",
                strategies=None,
                pairs=None,
            )
        ]

        signal = {"strategy_name": "test", "instrument": "BTC/USD", "direction": "BUY"}

        # Deliver 3 times to trip the circuit breaker (threshold=3)
        for _ in range(3):
            await svc.deliver_signal(signal)

        assert cb.state == "open"

        # Next delivery should be blocked by circuit breaker
        result = await svc.deliver_signal(signal)
        assert result["failed"] == 1
        assert metrics.telegram_circuit_breaker_trips.value >= 1

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    @patch("services.signal_api.delivery.WebhookSender")
    async def test_mixed_channel_delivery(self, mock_wh_cls, mock_tg_cls, pipeline):
        svc, conn, metrics, cb, dlq = pipeline
        mock_tg = MagicMock()
        mock_tg.send_signal.return_value = True
        mock_tg_cls.return_value = mock_tg
        mock_wh = MagicMock()
        mock_wh.send_signal.return_value = True
        mock_wh_cls.return_value = mock_wh

        conn.fetch.return_value = [
            FakeRecord(
                id="sub-1",
                channel="telegram",
                endpoint="12345",
                strategies=None,
                pairs=None,
            ),
            FakeRecord(
                id="sub-2",
                channel="webhook",
                endpoint="https://example.com/hook",
                strategies=None,
                pairs=None,
            ),
        ]

        signal = {"strategy_name": "test", "instrument": "BTC/USD", "direction": "BUY"}
        result = await svc.deliver_signal(signal)

        assert result["delivered"] == 2
        assert result["failed"] == 0
        assert metrics.deliveries_attempted.value == 2
        assert metrics.deliveries_succeeded.value == 2

        snap = metrics.snapshot()
        assert snap["delivery"]["by_channel"]["telegram"]["success"] == 1
        assert snap["delivery"]["by_channel"]["webhook"]["success"] == 1

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_alerting_fires_on_high_failure_rate(self, mock_sender_cls, pipeline):
        svc, conn, metrics, cb, dlq = pipeline
        mock_sender = MagicMock()
        mock_sender_cls.return_value = mock_sender

        conn.fetch.return_value = [
            FakeRecord(
                id="sub-1",
                channel="telegram",
                endpoint="12345",
                strategies=None,
                pairs=None,
            )
        ]

        signal = {"strategy_name": "test", "instrument": "BTC/USD", "direction": "BUY"}

        # Simulate 8 successes and 5 failures (>5% failure rate)
        mock_sender.send_signal.return_value = True
        for _ in range(8):
            await svc.deliver_signal(signal)

        mock_sender.send_signal.return_value = False
        for _ in range(5):
            await svc.deliver_signal(signal)

        # Evaluate alerts
        evaluator = AlertEvaluator()
        alerts = evaluator.evaluate(metrics.snapshot())
        rule_names = {a.rule_name for a in alerts}
        assert "delivery_failure_rate_high" in rule_names

    @pytest.mark.asyncio
    async def test_no_subscribers_no_metrics(self, pipeline):
        svc, conn, metrics, cb, dlq = pipeline
        conn.fetch.return_value = []

        signal = {"strategy_name": "test", "instrument": "BTC/USD"}
        result = await svc.deliver_signal(signal)

        assert result["delivered"] == 0
        assert result["failed"] == 0
        assert metrics.deliveries_attempted.value == 0
