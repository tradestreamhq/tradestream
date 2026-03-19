"""Tests for the Telegram signal bot."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.telegram_bot.bot import TelegramSignalBot


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
def bot():
    pool, conn = _make_pool()
    bot = TelegramSignalBot(bot_token="test-token", db_pool=pool)
    return bot, conn


class TestCommands:
    @pytest.mark.asyncio
    async def test_start(self, bot):
        b, conn = bot
        result = await b.handle_command("123", "/start")
        assert "TradeStream Signal Bot" in result
        assert "/subscribe" in result

    @pytest.mark.asyncio
    async def test_help(self, bot):
        b, conn = bot
        result = await b.handle_command("123", "/help")
        assert "Commands" in result

    @pytest.mark.asyncio
    async def test_subscribe_new(self, bot):
        b, conn = bot
        conn.fetchrow.return_value = None
        conn.execute.return_value = "INSERT 0 1"

        result = await b.handle_command("123", "/subscribe")
        assert "Subscribed" in result

    @pytest.mark.asyncio
    async def test_subscribe_duplicate(self, bot):
        b, conn = bot
        conn.fetchrow.return_value = FakeRecord(id=str(uuid.uuid4()))

        result = await b.handle_command("123", "/subscribe")
        assert "already subscribed" in result

    @pytest.mark.asyncio
    async def test_unsubscribe_success(self, bot):
        b, conn = bot
        conn.execute.return_value = "UPDATE 1"

        result = await b.handle_command("123", "/unsubscribe")
        assert "Unsubscribed" in result

    @pytest.mark.asyncio
    async def test_unsubscribe_not_found(self, bot):
        b, conn = bot
        conn.execute.return_value = "UPDATE 0"

        result = await b.handle_command("123", "/unsubscribe")
        assert "don't have" in result

    @pytest.mark.asyncio
    async def test_status_active(self, bot):
        b, conn = bot
        conn.fetchrow.return_value = FakeRecord(
            id=str(uuid.uuid4()),
            strategies=["momentum_btc"],
            pairs=["BTC/USD"],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        result = await b.handle_command("123", "/status")
        assert "Subscription Status" in result
        assert "momentum_btc" in result

    @pytest.mark.asyncio
    async def test_status_no_sub(self, bot):
        b, conn = bot
        conn.fetchrow.return_value = None

        result = await b.handle_command("123", "/status")
        assert "No active subscription" in result

    @pytest.mark.asyncio
    async def test_unknown_command(self, bot):
        b, conn = bot
        result = await b.handle_command("123", "/foo")
        assert "Unknown command" in result

    @pytest.mark.asyncio
    async def test_command_with_bot_suffix(self, bot):
        b, conn = bot
        result = await b.handle_command("123", "/start@MyBot")
        assert "TradeStream Signal Bot" in result


class TestFormatSignal:
    def test_buy_signal(self, bot):
        b, _ = bot
        signal = {
            "direction": "BUY",
            "instrument": "BTC/USD",
            "strategy_name": "momentum_btc",
            "entry_price": 65000.0,
            "stop_loss": 63000.0,
            "take_profit": 70000.0,
            "confidence": 0.85,
        }
        text = b.format_signal(signal)
        assert "BUY" in text
        assert "BTC/USD" in text
        assert "65000" in text
        assert "85%" in text

    def test_sell_signal(self, bot):
        b, _ = bot
        signal = {
            "direction": "SELL",
            "instrument": "ETH/USD",
            "strategy_name": "mean_reversion",
            "entry_price": 3200.0,
            "confidence": 0.72,
        }
        text = b.format_signal(signal)
        assert "SELL" in text
        assert "ETH/USD" in text


class TestDeliverSignal:
    @patch("services.telegram_bot.bot.requests.post")
    def test_deliver_success(self, mock_post, bot):
        b, _ = bot
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        signal = {
            "direction": "BUY",
            "instrument": "BTC/USD",
            "strategy_name": "test",
            "confidence": 0.9,
        }
        assert b.deliver_signal("123", signal) is True
        mock_post.assert_called_once()

    @patch("services.telegram_bot.bot.requests.post")
    def test_deliver_failure(self, mock_post, bot):
        b, _ = bot
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal error"
        mock_post.return_value = mock_resp

        signal = {"direction": "SELL", "instrument": "ETH/USD"}
        assert b.deliver_signal("123", signal) is False


class TestSendMessage:
    @patch("services.telegram_bot.bot.requests.post")
    def test_send_success(self, mock_post, bot):
        b, _ = bot
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        assert b.send_message("123", "Hello") is True

    @patch("services.telegram_bot.bot.requests.post")
    def test_send_network_error(self, mock_post, bot):
        b, _ = bot
        import requests
        mock_post.side_effect = requests.RequestException("timeout")

        assert b.send_message("123", "Hello") is False
