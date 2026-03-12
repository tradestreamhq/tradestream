"""Tests for the notification service."""

import json
from unittest import mock

import pytest

from services.notification_service.config import get_config
from services.notification_service.discord_sender import DiscordSender
from services.notification_service.email_sender import EmailSender
from services.notification_service.main import _build_senders, _passes_filter
from services.notification_service.notification_history import (
    NotificationHistory,
    NotificationRecord,
)
from services.notification_service.slack_sender import SlackSender
from services.notification_service.telegram_sender import TelegramSender
from services.notification_service.webhook_sender import WebhookSender


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


class TestSlackSender:
    def test_build_blocks_buy(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        blocks = sender._build_blocks(SAMPLE_SIGNAL)
        assert blocks[0]["type"] == "header"
        assert "BTC/USD" in blocks[0]["text"]["text"]
        fields = blocks[1]["fields"]
        assert any("BUY" in f["text"] for f in fields)
        assert any("85%" in f["text"] for f in fields)

    def test_build_blocks_with_summary(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        blocks = sender._build_blocks(SAMPLE_SIGNAL)
        assert len(blocks) == 3
        assert "uptrend" in blocks[2]["text"]["text"]

    def test_build_blocks_without_summary(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        sig = {**SAMPLE_SIGNAL, "summary": ""}
        blocks = sender._build_blocks(sig)
        assert len(blocks) == 2

    @mock.patch("services.notification_service.slack_sender.requests.post")
    def test_send_signal_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200, text="ok")
        sender = SlackSender("https://hooks.slack.com/services/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert "blocks" in payload

    @mock.patch("services.notification_service.slack_sender.requests.post")
    def test_send_signal_failure(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200, text="invalid_payload")
        sender = SlackSender("https://hooks.slack.com/services/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.slack_sender.requests.post")
    def test_send_signal_network_error(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("timeout")
        sender = SlackSender("https://hooks.slack.com/services/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is False


class TestWebhookSender:
    def test_build_payload(self):
        sender = WebhookSender("https://example.com/webhook")
        payload = sender._build_payload(SAMPLE_SIGNAL)
        parsed = json.loads(payload)
        assert parsed["action"] == "BUY"
        assert parsed["symbol"] == "BTC/USD"

    def test_build_headers_without_secret(self):
        sender = WebhookSender("https://example.com/webhook")
        payload = sender._build_payload(SAMPLE_SIGNAL)
        headers = sender._build_headers(payload)
        assert headers["Content-Type"] == "application/json"
        assert "X-TradeStream-Timestamp" in headers
        assert "X-TradeStream-Signature" not in headers

    def test_build_headers_with_secret(self):
        sender = WebhookSender("https://example.com/webhook", "my-secret")
        payload = sender._build_payload(SAMPLE_SIGNAL)
        headers = sender._build_headers(payload)
        assert "X-TradeStream-Signature" in headers
        assert len(headers["X-TradeStream-Signature"]) == 64  # SHA256 hex

    def test_compute_signature_deterministic(self):
        sender = WebhookSender("https://example.com/webhook", "test-secret")
        sig1 = sender._compute_signature("12345", '{"key":"value"}')
        sig2 = sender._compute_signature("12345", '{"key":"value"}')
        assert sig1 == sig2

    def test_compute_signature_changes_with_timestamp(self):
        sender = WebhookSender("https://example.com/webhook", "test-secret")
        sig1 = sender._compute_signature("12345", '{"key":"value"}')
        sig2 = sender._compute_signature("12346", '{"key":"value"}')
        assert sig1 != sig2

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        sender = WebhookSender("https://example.com/webhook", "secret")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_post.assert_called_once()

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_client_error(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=400, text="Bad Request")
        sender = WebhookSender("https://example.com/webhook")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_server_error_retries(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=500, text="Internal Server Error")
        sender = WebhookSender("https://example.com/webhook")
        assert sender.send_signal(SAMPLE_SIGNAL) is False
        assert mock_post.call_count == 3  # 3 retries


class TestEmailSender:
    def test_render_plain(self):
        sender = EmailSender("smtp.test.com", 587, "", "", "from@test.com", ["to@test.com"])
        text = sender._render_plain(SAMPLE_SIGNAL)
        assert "BUY" in text
        assert "BTC/USD" in text
        assert "85%" in text

    def test_render_html(self):
        sender = EmailSender("smtp.test.com", 587, "", "", "from@test.com", ["to@test.com"])
        html = sender._render_html(SAMPLE_SIGNAL)
        assert "BUY" in html
        assert "BTC/USD" in html
        assert "#00CC00" in html

    def test_render_html_sell(self):
        sender = EmailSender("smtp.test.com", 587, "", "", "from@test.com", ["to@test.com"])
        sig = {**SAMPLE_SIGNAL, "action": "SELL"}
        html = sender._render_html(sig)
        assert "#CC0000" in html

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_success(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        sender = EmailSender(
            "smtp.test.com", 587, "user", "pass", "from@test.com", ["to@test.com"]
        )
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_no_tls(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        sender = EmailSender(
            "smtp.test.com", 25, "", "", "from@test.com", ["to@test.com"], use_tls=False
        )
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_failure(self, mock_smtp_class):
        mock_smtp_class.side_effect = Exception("Connection refused")
        sender = EmailSender(
            "smtp.test.com", 587, "user", "pass", "from@test.com", ["to@test.com"]
        )
        assert sender.send_signal(SAMPLE_SIGNAL) is False


class TestNotificationHistory:
    def _make_mock_redis(self):
        """Create a mock Redis client with list operations."""
        store = {}

        def lpush(key, value):
            store.setdefault(key, []).insert(0, value)
            return len(store[key])

        def ltrim(key, start, end):
            if key in store:
                store[key] = store[key][start : end + 1]

        def expire(key, ttl):
            pass

        def lrange(key, start, end):
            if key not in store:
                return []
            return store[key][start : end + 1 if end >= 0 else None]

        mock_redis = mock.MagicMock()
        mock_pipe = mock.MagicMock()
        mock_pipe.lpush = mock.MagicMock(side_effect=lpush)
        mock_pipe.ltrim = mock.MagicMock(side_effect=ltrim)
        mock_pipe.expire = mock.MagicMock(side_effect=expire)
        mock_pipe.execute = mock.MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_redis.lrange = mock.MagicMock(side_effect=lrange)
        mock_redis._store = store
        return mock_redis

    def test_record_delivery_success(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        record = history.record_delivery("sig-1", "telegram", True, SAMPLE_SIGNAL)
        assert record.status == "delivered"
        assert record.channel == "telegram"
        assert record.signal_id == "sig-1"

    def test_record_delivery_failure(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        record = history.record_delivery(
            "sig-1", "discord", False, SAMPLE_SIGNAL, error="timeout"
        )
        assert record.status == "failed"
        assert record.error == "timeout"

    def test_record_filtered(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        record = history.record_filtered("sig-1", "low confidence", SAMPLE_SIGNAL)
        assert record.status == "filtered"
        assert record.channel == "none"

    def test_get_recent_empty(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        assert history.get_recent() == []

    def test_get_stats_empty(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        stats = history.get_stats()
        assert stats["total"] == 0
        assert stats["delivered"] == 0
        assert stats["failed"] == 0
        assert stats["filtered"] == 0


class TestBuildSenders:
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_no_senders_configured(self):
        from services.notification_service.config import get_config

        config = get_config()
        senders = _build_senders(config)
        assert len(senders) == 0

    @mock.patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "bot123",
            "TELEGRAM_CHAT_ID": "-100",
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test",
            "WEBHOOK_URL": "https://example.com/webhook",
        },
    )
    def test_all_senders_configured(self):
        from services.notification_service.config import get_config

        config = get_config()
        senders = _build_senders(config)
        names = [name for name, _ in senders]
        assert "telegram" in names
        assert "discord" in names
        assert "slack" in names
        assert "webhook" in names

    @mock.patch.dict(
        "os.environ",
        {
            "EMAIL_SMTP_HOST": "smtp.test.com",
            "EMAIL_TO": "a@b.com,c@d.com",
            "EMAIL_FROM": "from@test.com",
        },
    )
    def test_email_sender_configured(self):
        from services.notification_service.config import get_config

        config = get_config()
        senders = _build_senders(config)
        names = [name for name, _ in senders]
        assert "email" in names


class TestConfig:
    @mock.patch.dict(
        "os.environ",
        {
            "REDIS_HOST": "redis.example.com",
            "REDIS_PORT": "6380",
            "TELEGRAM_BOT_TOKEN": "bot123",
            "TELEGRAM_CHAT_ID": "-100123",
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test",
            "WEBHOOK_URL": "https://example.com/hook",
            "WEBHOOK_SIGNING_SECRET": "s3cret",
            "MIN_SCORE": "0.8",
            "TIERS": "gold,platinum",
            "SYMBOLS": "BTC-USD,ETH-USD",
            "EMAIL_SMTP_HOST": "smtp.test.com",
            "EMAIL_TO": "user@test.com",
            "ENABLE_HISTORY": "false",
        },
    )
    def test_config_from_env(self):
        config = get_config()
        assert config["redis_host"] == "redis.example.com"
        assert config["redis_port"] == 6380
        assert config["telegram_bot_token"] == "bot123"
        assert config["telegram_chat_id"] == "-100123"
        assert config["discord_webhook_url"] == "https://discord.com/api/webhooks/test"
        assert config["slack_webhook_url"] == "https://hooks.slack.com/services/test"
        assert config["webhook_url"] == "https://example.com/hook"
        assert config["webhook_signing_secret"] == "s3cret"
        assert config["min_score"] == 0.8
        assert config["tiers"] == "gold,platinum"
        assert config["email_smtp_host"] == "smtp.test.com"
        assert config["email_to"] == "user@test.com"
        assert config["enable_history"] is False

    @mock.patch.dict("os.environ", {}, clear=True)
    def test_config_defaults(self):
        config = get_config()
        assert config["redis_host"] == "localhost"
        assert config["redis_port"] == 6379
        assert config["telegram_bot_token"] == ""
        assert config["min_score"] == 0.7
        assert config["slack_webhook_url"] == ""
        assert config["webhook_url"] == ""
        assert config["email_smtp_host"] == ""
        assert config["enable_history"] is True
