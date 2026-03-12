"""Tests for the notification service."""

import hashlib
import hmac
import json
from unittest import mock

import pytest
import requests

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

SELL_SIGNAL = {**SAMPLE_SIGNAL, "signal_id": "def-456", "action": "SELL"}

HOLD_SIGNAL = {**SAMPLE_SIGNAL, "signal_id": "ghi-789", "action": "HOLD"}

MINIMAL_SIGNAL = {
    "signal_id": "min-001",
    "symbol": "ETH/USD",
    "action": "BUY",
    "confidence": 0.9,
}


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------


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

    def test_passes_at_exact_min_score(self):
        sig = {**SAMPLE_SIGNAL, "confidence": 0.7}
        assert _passes_filter(sig, min_score=0.7, tiers=[])

    def test_filtered_just_below_min_score(self):
        sig = {**SAMPLE_SIGNAL, "confidence": 0.6999}
        assert not _passes_filter(sig, min_score=0.7, tiers=[])

    def test_missing_confidence_defaults_to_zero(self):
        sig = {"signal_id": "x", "symbol": "X", "action": "BUY"}
        assert not _passes_filter(sig, min_score=0.1, tiers=[])

    def test_passes_with_zero_min_score_and_no_tiers(self):
        assert _passes_filter(SAMPLE_SIGNAL, min_score=0.0, tiers=[])

    def test_both_confidence_and_tier_must_pass(self):
        sig = {**SAMPLE_SIGNAL, "confidence": 0.5, "tier": "gold"}
        assert not _passes_filter(sig, min_score=0.7, tiers=["gold"])


# ---------------------------------------------------------------------------
# Telegram tests
# ---------------------------------------------------------------------------


class TestTelegramSender:
    def test_format_signal(self):
        sender = TelegramSender("fake-token", "123")
        text = sender._format_signal(SAMPLE_SIGNAL)
        assert "BUY" in text
        assert "BTC/USD" in text
        assert "85%" in text

    def test_format_signal_sell(self):
        sender = TelegramSender("fake-token", "123")
        text = sender._format_signal(SELL_SIGNAL)
        assert "SELL" in text
        assert "\u2b07\ufe0f" in text

    def test_format_signal_hold(self):
        sender = TelegramSender("fake-token", "123")
        text = sender._format_signal(HOLD_SIGNAL)
        assert "HOLD" in text
        assert "\u23f8\ufe0f" in text

    def test_format_signal_unknown_action(self):
        sender = TelegramSender("fake-token", "123")
        sig = {**SAMPLE_SIGNAL, "action": "CLOSE"}
        text = sender._format_signal(sig)
        assert "CLOSE" in text
        assert "\u2753" in text

    def test_format_signal_includes_opportunity_score(self):
        sender = TelegramSender("fake-token", "123")
        text = sender._format_signal(SAMPLE_SIGNAL)
        assert "42" in text

    def test_format_signal_without_score_or_summary(self):
        sender = TelegramSender("fake-token", "123")
        text = sender._format_signal(MINIMAL_SIGNAL)
        assert "ETH/USD" in text
        assert "90%" in text
        assert "Opportunity Score" not in text

    def test_format_signal_includes_summary(self):
        sender = TelegramSender("fake-token", "123")
        text = sender._format_signal(SAMPLE_SIGNAL)
        assert "Strong uptrend" in text

    def test_url_contains_token(self):
        sender = TelegramSender("my-bot-token", "123")
        assert "my-bot-token" in sender.url

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    def test_send_signal_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        sender = TelegramSender("fake-token", "123")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["chat_id"] == "123"

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    def test_send_signal_sends_html_parse_mode(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        sender = TelegramSender("fake-token", "123")
        sender.send_signal(SAMPLE_SIGNAL)
        payload = mock_post.call_args[1]["json"]
        assert payload["parse_mode"] == "HTML"

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    def test_send_signal_failure(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=400, text="Bad Request")
        sender = TelegramSender("fake-token", "123")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    def test_send_signal_network_error(self, mock_post):
        mock_post.side_effect = requests.RequestException("connection refused")
        sender = TelegramSender("fake-token", "123")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    def test_send_signal_sets_timeout(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        sender = TelegramSender("fake-token", "123")
        sender.send_signal(SAMPLE_SIGNAL)
        assert mock_post.call_args[1]["timeout"] == 10


# ---------------------------------------------------------------------------
# Discord tests
# ---------------------------------------------------------------------------


class TestDiscordSender:
    def test_build_embed_buy(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(SAMPLE_SIGNAL)
        assert embed["title"] == "BTC/USD Signal"
        assert embed["color"] == 0x00CC00
        assert any(f["value"] == "BUY" for f in embed["fields"])

    def test_build_embed_sell(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(SELL_SIGNAL)
        assert embed["color"] == 0xCC0000

    def test_build_embed_hold(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(HOLD_SIGNAL)
        assert embed["color"] == 0xFFAA00

    def test_build_embed_unknown_action(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        sig = {**SAMPLE_SIGNAL, "action": "CLOSE"}
        embed = sender._build_embed(sig)
        assert embed["color"] == 0x808080

    def test_build_embed_includes_confidence(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(SAMPLE_SIGNAL)
        assert any(f["value"] == "85%" for f in embed["fields"])

    def test_build_embed_includes_opportunity_score(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(SAMPLE_SIGNAL)
        assert any(f["value"] == "42" for f in embed["fields"])

    def test_build_embed_without_score(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(MINIMAL_SIGNAL)
        assert len(embed["fields"]) == 2  # action + confidence only

    def test_build_embed_includes_summary_as_description(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(SAMPLE_SIGNAL)
        assert embed["description"] == SAMPLE_SIGNAL["summary"]

    def test_build_embed_no_description_without_summary(self):
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        embed = sender._build_embed(MINIMAL_SIGNAL)
        assert "description" not in embed

    @mock.patch("services.notification_service.discord_sender.requests.post")
    def test_send_signal_success_204(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=204)
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        assert "embeds" in payload

    @mock.patch("services.notification_service.discord_sender.requests.post")
    def test_send_signal_success_200(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is True

    @mock.patch("services.notification_service.discord_sender.requests.post")
    def test_send_signal_http_error(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=429, text="Rate limited")
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.discord_sender.requests.post")
    def test_send_signal_network_error(self, mock_post):
        mock_post.side_effect = requests.RequestException("timeout")
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.discord_sender.requests.post")
    def test_send_signal_sets_timeout(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=204)
        sender = DiscordSender("https://discord.com/api/webhooks/fake")
        sender.send_signal(SAMPLE_SIGNAL)
        assert mock_post.call_args[1]["timeout"] == 10


# ---------------------------------------------------------------------------
# Slack tests
# ---------------------------------------------------------------------------


class TestSlackSender:
    def test_build_blocks_buy(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        blocks = sender._build_blocks(SAMPLE_SIGNAL)
        assert blocks[0]["type"] == "header"
        assert "BTC/USD" in blocks[0]["text"]["text"]
        fields = blocks[1]["fields"]
        assert any("BUY" in f["text"] for f in fields)
        assert any("85%" in f["text"] for f in fields)

    def test_build_blocks_sell_emoji(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        blocks = sender._build_blocks(SELL_SIGNAL)
        fields = blocks[1]["fields"]
        assert any(":chart_with_downwards_trend:" in f["text"] for f in fields)

    def test_build_blocks_hold_emoji(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        blocks = sender._build_blocks(HOLD_SIGNAL)
        fields = blocks[1]["fields"]
        assert any(":pause_button:" in f["text"] for f in fields)

    def test_build_blocks_unknown_action_emoji(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        sig = {**SAMPLE_SIGNAL, "action": "CLOSE"}
        blocks = sender._build_blocks(sig)
        fields = blocks[1]["fields"]
        assert any(":grey_question:" in f["text"] for f in fields)

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

    def test_build_blocks_includes_opportunity_score(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        blocks = sender._build_blocks(SAMPLE_SIGNAL)
        fields = blocks[1]["fields"]
        assert any("42" in f["text"] for f in fields)

    def test_build_blocks_without_score(self):
        sender = SlackSender("https://hooks.slack.com/services/fake")
        blocks = sender._build_blocks(MINIMAL_SIGNAL)
        fields = blocks[1]["fields"]
        assert len(fields) == 2  # action + confidence only

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
    def test_send_signal_http_error(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=500, text="server error")
        sender = SlackSender("https://hooks.slack.com/services/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.slack_sender.requests.post")
    def test_send_signal_network_error(self, mock_post):
        mock_post.side_effect = requests.RequestException("timeout")
        sender = SlackSender("https://hooks.slack.com/services/fake")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.slack_sender.requests.post")
    def test_send_signal_sets_timeout(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200, text="ok")
        sender = SlackSender("https://hooks.slack.com/services/fake")
        sender.send_signal(SAMPLE_SIGNAL)
        assert mock_post.call_args[1]["timeout"] == 10


# ---------------------------------------------------------------------------
# Webhook tests
# ---------------------------------------------------------------------------


class TestWebhookSender:
    def test_build_payload(self):
        sender = WebhookSender("https://example.com/webhook")
        payload = sender._build_payload(SAMPLE_SIGNAL)
        parsed = json.loads(payload)
        assert parsed["action"] == "BUY"
        assert parsed["symbol"] == "BTC/USD"

    def test_build_payload_sorted_keys(self):
        sender = WebhookSender("https://example.com/webhook")
        payload = sender._build_payload(SAMPLE_SIGNAL)
        parsed = json.loads(payload)
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_build_payload_includes_all_fields(self):
        sender = WebhookSender("https://example.com/webhook")
        payload = sender._build_payload(SAMPLE_SIGNAL)
        parsed = json.loads(payload)
        for key in SAMPLE_SIGNAL:
            assert key in parsed

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

    def test_build_headers_signature_is_valid_hmac(self):
        sender = WebhookSender("https://example.com/webhook", "test-secret")
        payload = sender._build_payload(SAMPLE_SIGNAL)
        headers = sender._build_headers(payload)
        ts = headers["X-TradeStream-Timestamp"]
        sig = headers["X-TradeStream-Signature"]
        expected = hmac.new(
            b"test-secret", f"{ts}.{payload}".encode(), hashlib.sha256
        ).hexdigest()
        assert sig == expected

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

    def test_compute_signature_changes_with_payload(self):
        sender = WebhookSender("https://example.com/webhook", "test-secret")
        sig1 = sender._compute_signature("12345", '{"key":"value1"}')
        sig2 = sender._compute_signature("12345", '{"key":"value2"}')
        assert sig1 != sig2

    def test_compute_signature_changes_with_secret(self):
        s1 = WebhookSender("https://example.com/webhook", "secret-a")
        s2 = WebhookSender("https://example.com/webhook", "secret-b")
        sig1 = s1._compute_signature("12345", '{"key":"value"}')
        sig2 = s2._compute_signature("12345", '{"key":"value"}')
        assert sig1 != sig2

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        sender = WebhookSender("https://example.com/webhook", "secret")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_post.assert_called_once()

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_success_201(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=201)
        sender = WebhookSender("https://example.com/webhook")
        assert sender.send_signal(SAMPLE_SIGNAL) is True

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_client_error_no_retry(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=400, text="Bad Request")
        sender = WebhookSender("https://example.com/webhook")
        assert sender.send_signal(SAMPLE_SIGNAL) is False
        assert mock_post.call_count == 1  # no retry for 4xx

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_server_error_retries(self, mock_post):
        mock_post.return_value = mock.Mock(
            status_code=500, text="Internal Server Error"
        )
        sender = WebhookSender("https://example.com/webhook")
        assert sender.send_signal(SAMPLE_SIGNAL) is False
        assert mock_post.call_count == 3  # 3 retries

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_server_error_then_success(self, mock_post):
        mock_post.side_effect = [
            mock.Mock(status_code=502, text="Bad Gateway"),
            mock.Mock(status_code=200),
        ]
        sender = WebhookSender("https://example.com/webhook")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        assert mock_post.call_count == 2

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_network_error_retries(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("refused")
        sender = WebhookSender("https://example.com/webhook")
        assert sender.send_signal(SAMPLE_SIGNAL) is False
        assert mock_post.call_count == 3

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_posts_to_correct_url(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        url = "https://example.com/my-webhook"
        sender = WebhookSender(url)
        sender.send_signal(SAMPLE_SIGNAL)
        assert mock_post.call_args[0][0] == url

    @mock.patch("services.notification_service.webhook_sender.requests.post")
    def test_send_signal_sends_json_body(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        sender = WebhookSender("https://example.com/webhook")
        sender.send_signal(SAMPLE_SIGNAL)
        data = mock_post.call_args[1]["data"]
        parsed = json.loads(data)
        assert parsed["action"] == "BUY"


# ---------------------------------------------------------------------------
# Email tests
# ---------------------------------------------------------------------------


class TestEmailSender:
    def _make_sender(self, **kwargs):
        defaults = dict(
            smtp_host="smtp.test.com",
            smtp_port=587,
            username="",
            password="",
            from_addr="from@test.com",
            to_addrs=["to@test.com"],
        )
        defaults.update(kwargs)
        return EmailSender(**defaults)

    def test_render_plain(self):
        sender = self._make_sender()
        text = sender._render_plain(SAMPLE_SIGNAL)
        assert "BUY" in text
        assert "BTC/USD" in text
        assert "85%" in text

    def test_render_plain_includes_score(self):
        sender = self._make_sender()
        text = sender._render_plain(SAMPLE_SIGNAL)
        assert "42" in text

    def test_render_plain_includes_summary(self):
        sender = self._make_sender()
        text = sender._render_plain(SAMPLE_SIGNAL)
        assert "Strong uptrend" in text

    def test_render_plain_without_score_or_summary(self):
        sender = self._make_sender()
        text = sender._render_plain(MINIMAL_SIGNAL)
        assert "ETH/USD" in text
        assert "Opportunity Score" not in text

    def test_render_html(self):
        sender = self._make_sender()
        html = sender._render_html(SAMPLE_SIGNAL)
        assert "BUY" in html
        assert "BTC/USD" in html
        assert "#00CC00" in html

    def test_render_html_sell(self):
        sender = self._make_sender()
        html = sender._render_html(SELL_SIGNAL)
        assert "#CC0000" in html

    def test_render_html_hold(self):
        sender = self._make_sender()
        html = sender._render_html(HOLD_SIGNAL)
        assert "#FFAA00" in html

    def test_render_html_unknown_action(self):
        sender = self._make_sender()
        sig = {**SAMPLE_SIGNAL, "action": "CLOSE"}
        html = sender._render_html(sig)
        assert "#808080" in html

    def test_render_html_includes_score(self):
        sender = self._make_sender()
        html = sender._render_html(SAMPLE_SIGNAL)
        assert "42" in html

    def test_render_html_without_score(self):
        sender = self._make_sender()
        html = sender._render_html(MINIMAL_SIGNAL)
        assert "Opportunity Score" not in html

    def test_render_html_includes_summary(self):
        sender = self._make_sender()
        html = sender._render_html(SAMPLE_SIGNAL)
        assert "Strong uptrend" in html

    def test_render_html_includes_footer(self):
        sender = self._make_sender()
        html = sender._render_html(SAMPLE_SIGNAL)
        assert "TradeStream Signal Service" in html

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_success(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        sender = self._make_sender(username="user", password="pass")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.sendmail.assert_called_once()

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_subject_line(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        sender = self._make_sender(username="user", password="pass")
        sender.send_signal(SAMPLE_SIGNAL)
        raw_msg = mock_server.sendmail.call_args[0][2]
        assert "TradeStream Signal: BUY BTC/USD" in raw_msg

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_from_address(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        sender = self._make_sender(from_addr="alerts@tradestream.io")
        sender.send_signal(SAMPLE_SIGNAL)
        from_addr = mock_server.sendmail.call_args[0][0]
        assert from_addr == "alerts@tradestream.io"

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_multiple_recipients(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        addrs = ["a@test.com", "b@test.com", "c@test.com"]
        sender = self._make_sender(to_addrs=addrs)
        sender.send_signal(SAMPLE_SIGNAL)
        to_addrs = mock_server.sendmail.call_args[0][1]
        assert to_addrs == addrs

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_no_tls(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        sender = self._make_sender(smtp_port=25, use_tls=False)
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_failure(self, mock_smtp_class):
        mock_smtp_class.side_effect = Exception("Connection refused")
        sender = self._make_sender(username="user", password="pass")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_auth_failure(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        mock_server.login.side_effect = Exception("Authentication failed")
        sender = self._make_sender(username="user", password="wrong")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.email_sender.smtplib.SMTP")
    def test_send_signal_contains_both_plain_and_html(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        sender = self._make_sender()
        sender.send_signal(SAMPLE_SIGNAL)
        raw_msg = mock_server.sendmail.call_args[0][2]
        assert "text/plain" in raw_msg
        assert "text/html" in raw_msg


# ---------------------------------------------------------------------------
# NotificationHistory tests
# ---------------------------------------------------------------------------


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

    def test_record_delivery_generates_notification_id(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        r1 = history.record_delivery("sig-1", "telegram", True, SAMPLE_SIGNAL)
        r2 = history.record_delivery("sig-1", "discord", True, SAMPLE_SIGNAL)
        assert r1.notification_id != r2.notification_id
        assert len(r1.notification_id) == 16

    def test_record_delivery_has_timestamp(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        record = history.record_delivery("sig-1", "slack", True, SAMPLE_SIGNAL)
        assert record.timestamp > 0

    def test_record_delivery_stores_signal_data(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        record = history.record_delivery("sig-1", "telegram", True, SAMPLE_SIGNAL)
        assert record.signal_data == SAMPLE_SIGNAL

    def test_record_delivery_without_signal_data(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        record = history.record_delivery("sig-1", "telegram", True)
        assert record.signal_data == {}

    def test_record_filtered(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        record = history.record_filtered("sig-1", "low confidence", SAMPLE_SIGNAL)
        assert record.status == "filtered"
        assert record.channel == "none"

    def test_record_filtered_stores_reason(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        record = history.record_filtered("sig-1", "confidence=0.5 < 0.7", SAMPLE_SIGNAL)
        assert record.error == "confidence=0.5 < 0.7"

    def test_get_recent_empty(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        assert history.get_recent() == []

    def test_get_recent_returns_records(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        history.record_delivery("sig-1", "telegram", True, SAMPLE_SIGNAL)
        history.record_delivery("sig-2", "discord", False, SAMPLE_SIGNAL, error="err")
        records = history.get_recent()
        assert len(records) == 2
        assert records[0]["signal_id"] == "sig-2"  # most recent first
        assert records[1]["signal_id"] == "sig-1"

    def test_get_recent_respects_count(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        for i in range(5):
            history.record_delivery(f"sig-{i}", "telegram", True, SAMPLE_SIGNAL)
        records = history.get_recent(count=3)
        assert len(records) == 3

    def test_get_stats_empty(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        stats = history.get_stats()
        assert stats["total"] == 0
        assert stats["delivered"] == 0
        assert stats["failed"] == 0
        assert stats["filtered"] == 0

    def test_get_stats_counts_correctly(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        history.record_delivery("sig-1", "telegram", True, SAMPLE_SIGNAL)
        history.record_delivery("sig-1", "discord", True, SAMPLE_SIGNAL)
        history.record_delivery("sig-1", "slack", False, SAMPLE_SIGNAL, error="err")
        history.record_filtered("sig-2", "low confidence", SAMPLE_SIGNAL)
        stats = history.get_stats()
        assert stats["total"] == 4
        assert stats["delivered"] == 2
        assert stats["failed"] == 1
        assert stats["filtered"] == 1

    def test_store_uses_pipeline(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        history.record_delivery("sig-1", "telegram", True, SAMPLE_SIGNAL)
        mock_redis.pipeline.assert_called()
        pipe = mock_redis.pipeline.return_value
        pipe.lpush.assert_called_once()
        pipe.ltrim.assert_called_once()
        pipe.expire.assert_called_once()
        pipe.execute.assert_called_once()

    def test_store_sets_correct_ttl(self):
        mock_redis = self._make_mock_redis()
        history = NotificationHistory(mock_redis)
        history.record_delivery("sig-1", "telegram", True, SAMPLE_SIGNAL)
        pipe = mock_redis.pipeline.return_value
        pipe.expire.assert_called_with(
            NotificationHistory.RECENT_KEY, NotificationHistory.TTL_SECONDS
        )

    def test_notification_record_dataclass(self):
        record = NotificationRecord(
            notification_id="abc",
            signal_id="sig-1",
            channel="telegram",
            status="delivered",
            timestamp=1234567890.0,
            signal_data={"key": "val"},
            error="",
        )
        assert record.notification_id == "abc"
        assert record.error == ""


# ---------------------------------------------------------------------------
# BuildSenders tests
# ---------------------------------------------------------------------------


class TestBuildSenders:
    @mock.patch.dict("os.environ", {}, clear=True)
    def test_no_senders_configured(self):
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
        config = get_config()
        senders = _build_senders(config)
        names = [name for name, _ in senders]
        assert "email" in names

    @mock.patch.dict(
        "os.environ",
        {"TELEGRAM_BOT_TOKEN": "bot123"},
        clear=True,
    )
    def test_telegram_needs_both_token_and_chat_id(self):
        config = get_config()
        senders = _build_senders(config)
        names = [name for name, _ in senders]
        assert "telegram" not in names

    @mock.patch.dict(
        "os.environ",
        {"EMAIL_SMTP_HOST": "smtp.test.com"},
        clear=True,
    )
    def test_email_needs_both_host_and_to(self):
        config = get_config()
        senders = _build_senders(config)
        names = [name for name, _ in senders]
        assert "email" not in names

    @mock.patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "bot123",
            "TELEGRAM_CHAT_ID": "-100",
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test",
            "WEBHOOK_URL": "https://example.com/webhook",
            "WEBHOOK_SIGNING_SECRET": "my-secret",
            "EMAIL_SMTP_HOST": "smtp.test.com",
            "EMAIL_TO": "a@b.com",
            "EMAIL_FROM": "from@test.com",
        },
    )
    def test_all_five_channels_configured(self):
        config = get_config()
        senders = _build_senders(config)
        assert len(senders) == 5
        names = [name for name, _ in senders]
        assert set(names) == {"telegram", "discord", "slack", "webhook", "email"}

    @mock.patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "bot123",
            "TELEGRAM_CHAT_ID": "-100",
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
            "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test",
            "WEBHOOK_URL": "https://example.com/webhook",
            "WEBHOOK_SIGNING_SECRET": "my-secret",
            "EMAIL_SMTP_HOST": "smtp.test.com",
            "EMAIL_TO": "a@b.com",
            "EMAIL_FROM": "from@test.com",
        },
    )
    def test_senders_are_correct_types(self):
        config = get_config()
        senders = _build_senders(config)
        sender_map = dict(senders)
        assert isinstance(sender_map["telegram"], TelegramSender)
        assert isinstance(sender_map["discord"], DiscordSender)
        assert isinstance(sender_map["slack"], SlackSender)
        assert isinstance(sender_map["webhook"], WebhookSender)
        assert isinstance(sender_map["email"], EmailSender)

    @mock.patch.dict(
        "os.environ",
        {
            "EMAIL_SMTP_HOST": "smtp.test.com",
            "EMAIL_TO": "a@b.com, c@d.com , e@f.com",
            "EMAIL_FROM": "from@test.com",
        },
    )
    def test_email_sender_splits_recipients(self):
        config = get_config()
        senders = _build_senders(config)
        email_sender = dict(senders)["email"]
        assert email_sender.to_addrs == ["a@b.com", "c@d.com", "e@f.com"]


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


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

    @mock.patch.dict("os.environ", {"EMAIL_USE_TLS": "false"}, clear=True)
    def test_config_email_tls_false(self):
        config = get_config()
        assert config["email_use_tls"] is False

    @mock.patch.dict("os.environ", {"EMAIL_USE_TLS": "true"}, clear=True)
    def test_config_email_tls_true(self):
        config = get_config()
        assert config["email_use_tls"] is True

    @mock.patch.dict("os.environ", {"EMAIL_USE_TLS": "TRUE"}, clear=True)
    def test_config_email_tls_case_insensitive(self):
        config = get_config()
        assert config["email_use_tls"] is True

    @mock.patch.dict("os.environ", {"ENABLE_HISTORY": "FALSE"}, clear=True)
    def test_config_enable_history_case_insensitive(self):
        config = get_config()
        assert config["enable_history"] is False

    @mock.patch.dict("os.environ", {"EMAIL_SMTP_PORT": "465"}, clear=True)
    def test_config_custom_smtp_port(self):
        config = get_config()
        assert config["email_smtp_port"] == 465

    @mock.patch.dict("os.environ", {}, clear=True)
    def test_config_default_smtp_port(self):
        config = get_config()
        assert config["email_smtp_port"] == 587


# ---------------------------------------------------------------------------
# Multi-channel delivery integration tests
# ---------------------------------------------------------------------------


class TestMultiChannelDelivery:
    """Tests verifying independent delivery across channels and error isolation."""

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    @mock.patch("services.notification_service.discord_sender.requests.post")
    def test_channels_deliver_independently(self, mock_discord, mock_telegram):
        mock_telegram.return_value = mock.Mock(status_code=200)
        mock_discord.return_value = mock.Mock(status_code=204)
        telegram = TelegramSender("token", "123")
        discord = DiscordSender("https://discord.com/api/webhooks/test")
        assert telegram.send_signal(SAMPLE_SIGNAL) is True
        assert discord.send_signal(SAMPLE_SIGNAL) is True
        mock_telegram.assert_called_once()
        mock_discord.assert_called_once()

    @mock.patch("services.notification_service.telegram_sender.requests.post")
    @mock.patch("services.notification_service.slack_sender.requests.post")
    def test_one_channel_failure_does_not_affect_other(self, mock_slack, mock_telegram):
        mock_telegram.side_effect = requests.RequestException("network error")
        mock_slack.return_value = mock.Mock(status_code=200, text="ok")
        telegram = TelegramSender("token", "123")
        slack = SlackSender("https://hooks.slack.com/services/fake")
        assert telegram.send_signal(SAMPLE_SIGNAL) is False
        assert slack.send_signal(SAMPLE_SIGNAL) is True

    def test_all_channels_format_same_signal_consistently(self):
        telegram = TelegramSender("token", "123")
        discord = DiscordSender("https://discord.com/api/webhooks/fake")
        slack = SlackSender("https://hooks.slack.com/services/fake")
        email = EmailSender(
            "smtp.test.com", 587, "", "", "from@test.com", ["to@test.com"]
        )
        webhook = WebhookSender("https://example.com/webhook")

        tg_text = telegram._format_signal(SAMPLE_SIGNAL)
        dc_embed = discord._build_embed(SAMPLE_SIGNAL)
        sl_blocks = slack._build_blocks(SAMPLE_SIGNAL)
        em_plain = email._render_plain(SAMPLE_SIGNAL)
        wh_payload = json.loads(webhook._build_payload(SAMPLE_SIGNAL))

        # All channels include the core signal data
        assert "BUY" in tg_text
        assert any(f["value"] == "BUY" for f in dc_embed["fields"])
        assert any("BUY" in f["text"] for f in sl_blocks[1]["fields"])
        assert "BUY" in em_plain
        assert wh_payload["action"] == "BUY"

    @mock.patch.dict(
        "os.environ",
        {
            "TELEGRAM_BOT_TOKEN": "bot123",
            "TELEGRAM_CHAT_ID": "-100",
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
        },
    )
    def test_build_senders_returns_tuples_with_correct_names(self):
        config = get_config()
        senders = _build_senders(config)
        for name, sender in senders:
            assert isinstance(name, str)
            assert hasattr(sender, "send_signal")
