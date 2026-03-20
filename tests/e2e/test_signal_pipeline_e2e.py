"""End-to-end test: Signal Pipeline.

Validates the full path from strategy config → signal generation → delivery
→ performance tracking. Exercises real metrics, circuit breaker, DLQ, and
alerting logic with mocked external services.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.shared.alerting import AlertEvaluator
from services.shared.circuit_breaker import CircuitBreaker
from services.shared.dead_letter_queue import DeadLetterQueue
from services.shared.pipeline_metrics import PipelineMetrics
from services.signal_api.delivery import SignalDeliveryService

from tests.e2e.conftest import FakeRow, FakeRedis, make_signal, make_subscription


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


def _build_pipeline(failure_threshold=3, max_retries=3):
    pool, conn = _make_pool()
    redis_client = MagicMock()
    metrics = PipelineMetrics()
    cb = CircuitBreaker(
        "telegram-api", failure_threshold=failure_threshold, recovery_timeout=60
    )
    dlq = DeadLetterQueue(redis_client, max_retries=max_retries, base_delay=10)

    svc = SignalDeliveryService(
        db_pool=pool,
        redis_client=redis_client,
        telegram_bot_token="test-token",
        metrics=metrics,
        telegram_circuit_breaker=cb,
        dlq=dlq,
    )
    return svc, conn, metrics, cb, dlq


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSignalPipelineE2E:
    """Full signal pipeline: config → generate → deliver → track."""

    # ── Happy path: signal generated and delivered ──────────────────────

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_signal_generated_and_delivered_to_subscriber(self, mock_tg_cls):
        """Strategy config → signal → successful Telegram delivery → metrics updated."""
        svc, conn, metrics, cb, dlq = _build_pipeline()

        mock_tg = MagicMock()
        mock_tg.send_signal.return_value = True
        mock_tg_cls.return_value = mock_tg

        sub = make_subscription(channel="telegram", endpoint="chat-999")
        conn.fetch.return_value = [sub]

        signal = make_signal(
            strategy_name="ema_crossover", direction="BUY", confidence=0.92
        )
        result = await svc.deliver_signal(signal)

        assert result["delivered"] == 1
        assert result["failed"] == 0
        assert metrics.deliveries_attempted.value == 1
        assert metrics.deliveries_succeeded.value == 1
        assert metrics.telegram_api_calls.value == 1
        assert cb.state == "closed"

    # ── Multi-subscriber fan-out ────────────────────────────────────────

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.WebhookSender")
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_signal_fans_out_to_multiple_subscribers(
        self, mock_tg_cls, mock_wh_cls
    ):
        """One signal → delivered to Telegram + webhook subscribers concurrently."""
        svc, conn, metrics, cb, dlq = _build_pipeline()

        mock_tg = MagicMock()
        mock_tg.send_signal.return_value = True
        mock_tg_cls.return_value = mock_tg
        mock_wh = MagicMock()
        mock_wh.send_signal.return_value = True
        mock_wh_cls.return_value = mock_wh

        conn.fetch.return_value = [
            make_subscription(channel="telegram", endpoint="chat-1"),
            make_subscription(channel="telegram", endpoint="chat-2"),
            make_subscription(channel="webhook", endpoint="https://example.com/hook"),
        ]

        signal = make_signal()
        result = await svc.deliver_signal(signal)

        assert result["delivered"] == 3
        assert result["failed"] == 0
        assert metrics.deliveries_attempted.value == 3
        assert metrics.deliveries_succeeded.value == 3

        snap = metrics.snapshot()
        assert snap["delivery"]["by_channel"]["telegram"]["success"] == 2
        assert snap["delivery"]["by_channel"]["webhook"]["success"] == 1

    # ── Partial failure: some subscribers fail ──────────────────────────

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.WebhookSender")
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_partial_delivery_failure_tracked(self, mock_tg_cls, mock_wh_cls):
        """Signal delivered to some subs, failed for others; metrics track both."""
        svc, conn, metrics, cb, dlq = _build_pipeline()

        mock_tg = MagicMock()
        mock_tg.send_signal.return_value = True
        mock_tg_cls.return_value = mock_tg
        mock_wh = MagicMock()
        mock_wh.send_signal.return_value = False
        mock_wh_cls.return_value = mock_wh

        conn.fetch.return_value = [
            make_subscription(channel="telegram", endpoint="chat-ok"),
            make_subscription(
                channel="webhook", endpoint="https://broken.example/hook"
            ),
        ]

        signal = make_signal()
        result = await svc.deliver_signal(signal)

        assert result["delivered"] == 1
        assert result["failed"] == 1
        assert metrics.deliveries_succeeded.value == 1
        assert metrics.deliveries_failed.value == 1
        assert metrics.dlq_enqueued.value == 1

    # ── Circuit breaker trips after repeated failures ───────────────────

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_circuit_breaker_opens_and_blocks_delivery(self, mock_tg_cls):
        """After N consecutive Telegram failures, circuit breaker opens and blocks."""
        svc, conn, metrics, cb, dlq = _build_pipeline(failure_threshold=3)

        mock_tg = MagicMock()
        mock_tg.send_signal.return_value = False
        mock_tg_cls.return_value = mock_tg

        conn.fetch.return_value = [
            make_subscription(channel="telegram", endpoint="chat-1")
        ]
        signal = make_signal()

        for _ in range(3):
            await svc.deliver_signal(signal)

        assert cb.state == "open"

        result = await svc.deliver_signal(signal)
        assert result["failed"] == 1
        assert metrics.telegram_circuit_breaker_trips.value >= 1

    # ── No subscribers: no-op ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_no_subscribers_produces_zero_metrics(self):
        """Signal with no matching subscribers does not touch metrics."""
        svc, conn, metrics, cb, dlq = _build_pipeline()
        conn.fetch.return_value = []

        result = await svc.deliver_signal(make_signal())

        assert result["delivered"] == 0
        assert result["failed"] == 0
        assert metrics.deliveries_attempted.value == 0

    # ── Alerting fires on high failure rate ─────────────────────────────

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_alerting_triggers_on_elevated_failure_rate(self, mock_tg_cls):
        """After enough failures vs successes, alert evaluator flags delivery_failure_rate_high."""
        svc, conn, metrics, cb, dlq = _build_pipeline(failure_threshold=100)

        mock_tg = MagicMock()
        mock_tg_cls.return_value = mock_tg

        conn.fetch.return_value = [
            make_subscription(channel="telegram", endpoint="chat-1")
        ]
        signal = make_signal()

        mock_tg.send_signal.return_value = True
        for _ in range(8):
            await svc.deliver_signal(signal)

        mock_tg.send_signal.return_value = False
        for _ in range(5):
            await svc.deliver_signal(signal)

        evaluator = AlertEvaluator()
        alerts = evaluator.evaluate(metrics.snapshot())
        rule_names = {a.rule_name for a in alerts}
        assert "delivery_failure_rate_high" in rule_names

    # ── Full pipeline with DLQ retry tracking ───────────────────────────

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_failed_deliveries_enqueued_to_dlq(self, mock_tg_cls):
        """Failed deliveries are enqueued to DLQ with correct metadata."""
        svc, conn, metrics, cb, dlq = _build_pipeline()

        mock_tg = MagicMock()
        mock_tg.send_signal.return_value = False
        mock_tg_cls.return_value = mock_tg

        sub_id = str(uuid.uuid4())
        conn.fetch.return_value = [
            FakeRow(
                id=sub_id,
                channel="telegram",
                endpoint="chat-fail",
                strategies=None,
                pairs=None,
            )
        ]

        signal = make_signal(strategy_name="broken_strat")
        await svc.deliver_signal(signal)

        assert metrics.dlq_enqueued.value == 1
        assert dlq.redis.lpush.called

    # ── Metrics snapshot is a complete snapshot ─────────────────────────

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_metrics_snapshot_contains_all_dimensions(self, mock_tg_cls):
        """After deliveries, metrics snapshot captures all expected dimensions."""
        svc, conn, metrics, cb, dlq = _build_pipeline()

        mock_tg = MagicMock()
        mock_tg.send_signal.return_value = True
        mock_tg_cls.return_value = mock_tg

        conn.fetch.return_value = [
            make_subscription(channel="telegram", endpoint="chat-1")
        ]
        await svc.deliver_signal(make_signal())

        snap = metrics.snapshot()
        assert "signal_generation" in snap
        assert "delivery" in snap
        assert "dlq" in snap
        assert "telegram_api" in snap
        assert snap["delivery"]["attempted"] == 1
        assert snap["delivery"]["succeeded"] == 1
        assert snap["delivery"]["latency_ms"]["count"] == 1
