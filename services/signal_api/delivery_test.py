"""Tests for the signal delivery service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.signal_api.delivery import SignalDeliveryService, _build_summary


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


@pytest.fixture
def service():
    pool, conn = _make_pool()
    redis_client = MagicMock()
    svc = SignalDeliveryService(
        db_pool=pool,
        redis_client=redis_client,
        telegram_bot_token="test-token",
    )
    return svc, conn


class TestGetActiveSubscriptions:
    @pytest.mark.asyncio
    async def test_all_subs(self, service):
        svc, conn = service
        conn.fetch.return_value = [
            FakeRecord(
                id=str(uuid.uuid4()),
                channel="telegram",
                endpoint="123",
                strategies=None,
                pairs=None,
            )
        ]
        subs = await svc.get_active_subscriptions()
        assert len(subs) == 1

    @pytest.mark.asyncio
    async def test_filter_by_strategy(self, service):
        svc, conn = service
        conn.fetch.return_value = [
            FakeRecord(
                id="1",
                channel="telegram",
                endpoint="123",
                strategies=["momentum_btc"],
                pairs=None,
            ),
            FakeRecord(
                id="2",
                channel="webhook",
                endpoint="https://example.com",
                strategies=["mean_reversion"],
                pairs=None,
            ),
        ]
        subs = await svc.get_active_subscriptions(strategy_name="momentum_btc")
        assert len(subs) == 1
        assert subs[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_filter_by_pair(self, service):
        svc, conn = service
        conn.fetch.return_value = [
            FakeRecord(
                id="1",
                channel="telegram",
                endpoint="123",
                strategies=None,
                pairs=["BTC/USD"],
            ),
        ]
        subs = await svc.get_active_subscriptions(instrument="ETH/USD")
        assert len(subs) == 0


class TestDeliverSignal:
    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.TelegramSender")
    async def test_deliver_telegram(self, mock_sender_cls, service):
        svc, conn = service
        mock_sender = MagicMock()
        mock_sender.send_signal.return_value = True
        mock_sender_cls.return_value = mock_sender

        conn.fetch.return_value = [
            FakeRecord(
                id="1",
                channel="telegram",
                endpoint="123",
                strategies=None,
                pairs=None,
            ),
        ]

        signal = {
            "strategy_name": "momentum_btc",
            "instrument": "BTC/USD",
            "direction": "BUY",
            "confidence": 0.85,
        }
        result = await svc.deliver_signal(signal)
        assert result["delivered"] == 1
        assert result["failed"] == 0

    @pytest.mark.asyncio
    @patch("services.signal_api.delivery.WebhookSender")
    async def test_deliver_webhook(self, mock_sender_cls, service):
        svc, conn = service
        mock_sender = MagicMock()
        mock_sender.send_signal.return_value = True
        mock_sender_cls.return_value = mock_sender

        conn.fetch.return_value = [
            FakeRecord(
                id="2",
                channel="webhook",
                endpoint="https://example.com/hook",
                strategies=None,
                pairs=None,
            ),
        ]

        signal = {
            "strategy_name": "mean_reversion",
            "instrument": "ETH/USD",
            "direction": "SELL",
        }
        result = await svc.deliver_signal(signal)
        assert result["delivered"] == 1

    @pytest.mark.asyncio
    async def test_no_subscribers(self, service):
        svc, conn = service
        conn.fetch.return_value = []

        result = await svc.deliver_signal({"strategy_name": "test", "instrument": "X"})
        assert result["delivered"] == 0
        assert result["failed"] == 0


class TestBuildSummary:
    def test_full_summary(self):
        signal = {
            "strategy_name": "momentum",
            "entry_price": 65000,
            "stop_loss": 63000,
            "take_profit": 70000,
        }
        summary = _build_summary(signal)
        assert "momentum" in summary
        assert "65000" in summary
        assert "63000" in summary

    def test_empty_signal(self):
        assert _build_summary({}) == ""
