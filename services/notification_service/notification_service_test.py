"""Tests for the notification service."""

import json
from unittest import mock

import pytest

from services.notification_service.config import get_config
from services.notification_service.discord_sender import DiscordSender
from services.notification_service.main import _passes_filter
from services.notification_service.telegram_sender import TelegramSender


SAMPLE_SIGNAL = {
    "signal_id": "abc-123",
    "symbol": "BTC/USD",
    "action": "BUY",
    "confidence": 0.85,
    "opportunity_score": 42,
    "summary": "Strong uptrend confirmed by multiple indicators.",
    "timestamp": "2026-03-10T12:00:00Z",
}


class TestPassesFilter:
    def test_passes_when_above_min_score(self):
        assert _passes_filter(SAMPLE_SIGNAL, min_score=0.7, tiers=[])

    def test_filtered_when_below_min_score(self):
        low = {**SAMPLE_SIGNAL, "confidence": 0.5}
        assert not _passes_filter(low, min_score=0.7, tiers=[])

    def test_passes_when_tier_matches(self):
        sig = {**SAMPLE_SIGNAL, "tier": "gold"}
        assert _passes_filter(sig, min_score=0.0, tiers=["gold", "platinum"])

    def test_filtered_when_tier_does_not_match(self):
        sig = {**SAMPLE_SIGNAL, "tier": "bronze"}
        assert not _passes_filter(sig, min_score=0.0, tiers=["gold", "platinum"])

    def test_passes_when_no_tier_filter(self):
        sig = {**SAMPLE_SIGNAL, "tier": "bronze"}
        assert _passes_filter(sig, min_score=0.0, tiers=[])

    def test_passes_when_signal_has_no_tier(self):
        assert _passes_filter(SAMPLE_SIGNAL, min_score=0.0, tiers=["gold"])


class TestTelegramSender:
    def test_format_signal(self):
        sender = TelegramSender("fake-token", "123")
        text = sender._format_signal(SAMPLE_SIGNAL)
        assert "BUY" in text
        assert "BTC/USD" in text
        assert "85%" in text

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    def test_send_signal_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        sender = TelegramSender("fake-token", "123")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["chat_id"] == "123"

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    def test_send_signal_failure(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=400, text="Bad Request")
        sender = TelegramSender("fake-token", "123")
        assert sender.send_signal(SAMPLE_SIGNAL) is False


class TestDiscordSender:
    def test_build_embed_buy(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(SAMPLE_SIGNAL)
        assert embed["title"] == "BTC/USD Signal"
        assert embed["color"] == 0x00CC00
        assert any(f["value"] == "BUY" for f in embed["fields"])

    def test_build_embed_sell(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        sig = {**SAMPLE_SIGNAL, "action": "SELL"}
        embed = sender._build_embed(sig)
        assert embed["color"] == 0xCC0000

    @mock.patch("services.notification_service.discord_sender.requests.post")
    def test_send_signal_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=204)
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert "embeds" in payload

    @mock.patch("services.notification_service.discord_sender.requests.post")
    def test_send_signal_network_error(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("timeout")
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is False


class TestConfig:
    @mock.patch.dict(
        "os.environ",
        {
            "REDIS_HOST": "redis.example.com",
            "REDIS_PORT": "6380",
            "TELEGRAM_BOT_TOKEN": "bot123",
            "TELEGRAM_CHAT_ID": "-100123",
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "MIN_SCORE": "0.8",
            "TIERS": "gold,platinum",
            "SYMBOLS": "BTC-USD,ETH-USD",
        },
    )
    def test_config_from_env(self):
        config = get_config()
        assert config["redis_host"] == "redis.example.com"
        assert config["redis_port"] == 6380
        assert config["telegram_bot_token"] == "bot123"
        assert config["telegram_chat_id"] == "-100123"
        assert config["discord_webhook_url"] == "https://discord.com/api/webhooks/test"
        assert config["min_score"] == 0.8
        assert config["tiers"] == "gold,platinum"

    @mock.patch.dict("os.environ", {}, clear=True)
    def test_config_defaults(self):
        config = get_config()
        assert config["redis_host"] == "localhost"
        assert config["redis_port"] == 6379
        assert config["telegram_bot_token"] == ""
        assert config["min_score"] == 0.7
