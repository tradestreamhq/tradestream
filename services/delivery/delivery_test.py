"""Tests for the multi-channel delivery service."""

import json
from unittest import mock

import pytest

from services.delivery.channels.base import DeliveryChannel, DeliveryResult
from services.delivery.channels.discord import DiscordDeliveryChannel
from services.delivery.channels.email import EmailDeliveryChannel
from services.delivery.channels.slack import SlackDeliveryChannel
from services.delivery.channels.sms import SMSDeliveryChannel
from services.delivery.channels.telegram import TelegramDeliveryChannel
from services.delivery.channels.webhook import WebhookDeliveryChannel
from services.delivery.deduplication import CrossChannelDeduplicator
from services.delivery.preferences import (
    ChannelPreference,
    PreferenceStore,
    UserDeliveryPreferences,
)
from services.delivery.rate_limiter import DeliveryRateLimiter
from services.delivery.router import DeliveryRouter
from services.delivery.tracker import DeliveryTracker

SAMPLE_SIGNAL = {
    "signal_id": "sig-001",
    "symbol": "BTC/USD",
    "action": "BUY",
    "confidence": 0.85,
    "opportunity_score": 87,
    "opportunity_tier": "HOT",
    "summary": "Strong momentum confirmed.",
    "timestamp": "2026-03-19T12:00:00Z",
}


# ---- Channel Tests ----


class TestDeliveryResult:
    def test_ok(self):
        r = DeliveryResult.ok("telegram", "msg-123")
        assert r.success is True
        assert r.channel == "telegram"
        assert r.external_message_id == "msg-123"

    def test_fail(self):
        r = DeliveryResult.fail("discord", "timeout", retryable=True)
        assert r.success is False
        assert r.error == "timeout"
        assert r.retryable is True

    def test_fail_permanent(self):
        r = DeliveryResult.fail("sms", "invalid number", retryable=False)
        assert r.retryable is False


class TestTelegramDeliveryChannel:
    def test_name(self):
        ch = TelegramDeliveryChannel("fake-token")
        assert ch.name == "telegram"

    @mock.patch("services.delivery.channels.telegram.requests.post")
    def test_send_success(self, mock_post):
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=lambda: {"result": {"message_id": 42}},
        )
        ch = TelegramDeliveryChannel("fake-token")
        result = ch.send(SAMPLE_SIGNAL, "123456")
        assert result.success is True
        assert result.external_message_id == "42"

    @mock.patch("services.delivery.channels.telegram.requests.post")
    def test_send_blocked(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=403, text="Forbidden")
        ch = TelegramDeliveryChannel("fake-token")
        result = ch.send(SAMPLE_SIGNAL, "123456")
        assert result.success is False
        assert result.retryable is False

    @mock.patch("services.delivery.channels.telegram.requests.post")
    def test_send_server_error(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=500, text="Server Error")
        ch = TelegramDeliveryChannel("fake-token")
        result = ch.send(SAMPLE_SIGNAL, "123456")
        assert result.success is False
        assert result.retryable is True

    @mock.patch("services.delivery.channels.telegram.requests.post")
    def test_send_network_error(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("timeout")
        ch = TelegramDeliveryChannel("fake-token")
        result = ch.send(SAMPLE_SIGNAL, "123456")
        assert result.success is False
        assert result.retryable is True


class TestDiscordDeliveryChannel:
    def test_name(self):
        ch = DiscordDeliveryChannel()
        assert ch.name == "discord"

    @mock.patch("services.delivery.channels.discord.requests.post")
    def test_send_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=204)
        ch = DiscordDeliveryChannel()
        result = ch.send(SAMPLE_SIGNAL, "https://discord.com/api/webhooks/test")
        assert result.success is True

    @mock.patch("services.delivery.channels.discord.requests.post")
    def test_send_not_found(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=404, text="Not Found")
        ch = DiscordDeliveryChannel()
        result = ch.send(SAMPLE_SIGNAL, "https://discord.com/api/webhooks/bad")
        assert result.success is False
        assert result.retryable is False

    def test_build_embed(self):
        ch = DiscordDeliveryChannel()
        embed = ch._build_embed(SAMPLE_SIGNAL)
        assert embed["title"] == "BTC/USD Signal"
        assert embed["color"] == 0x00CC00
        assert any(f["value"] == "BUY" for f in embed["fields"])


class TestSlackDeliveryChannel:
    def test_name(self):
        ch = SlackDeliveryChannel()
        assert ch.name == "slack"

    @mock.patch("services.delivery.channels.slack.requests.post")
    def test_send_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200, text="ok")
        ch = SlackDeliveryChannel()
        result = ch.send(SAMPLE_SIGNAL, "https://hooks.slack.com/services/test")
        assert result.success is True

    @mock.patch("services.delivery.channels.slack.requests.post")
    def test_send_failure(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200, text="invalid_payload")
        ch = SlackDeliveryChannel()
        result = ch.send(SAMPLE_SIGNAL, "https://hooks.slack.com/services/test")
        assert result.success is False

    def test_build_blocks(self):
        ch = SlackDeliveryChannel()
        blocks = ch._build_blocks(SAMPLE_SIGNAL)
        assert blocks[0]["type"] == "header"
        assert "BTC/USD" in blocks[0]["text"]["text"]


class TestEmailDeliveryChannel:
    def test_name(self):
        ch = EmailDeliveryChannel("smtp.test.com")
        assert ch.name == "email"

    @mock.patch("services.delivery.channels.email.smtplib.SMTP")
    def test_send_success(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        ch = EmailDeliveryChannel("smtp.test.com", username="user", password="pass")
        result = ch.send(SAMPLE_SIGNAL, "user@test.com")
        assert result.success is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()

    @mock.patch("services.delivery.channels.email.smtplib.SMTP")
    def test_send_failure(self, mock_smtp_class):
        mock_smtp_class.side_effect = Exception("Connection refused")
        ch = EmailDeliveryChannel("smtp.test.com")
        result = ch.send(SAMPLE_SIGNAL, "user@test.com")
        assert result.success is False
        assert result.retryable is True

    @mock.patch("services.delivery.channels.email.smtplib.SMTP")
    def test_send_digest(self, mock_smtp_class):
        mock_server = mock.MagicMock()
        mock_smtp_class.return_value.__enter__ = mock.Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = mock.Mock(return_value=False)
        ch = EmailDeliveryChannel("smtp.test.com")
        signals = [SAMPLE_SIGNAL, {**SAMPLE_SIGNAL, "symbol": "ETH/USD"}]
        result = ch.send_digest(signals, "user@test.com")
        assert result.success is True

    def test_render_plain(self):
        ch = EmailDeliveryChannel("smtp.test.com")
        text = ch._render_plain(SAMPLE_SIGNAL)
        assert "BUY" in text
        assert "BTC/USD" in text

    def test_render_html(self):
        ch = EmailDeliveryChannel("smtp.test.com")
        html = ch._render_html(SAMPLE_SIGNAL)
        assert "#00CC00" in html
        assert "BUY" in html


class TestSMSDeliveryChannel:
    def test_name(self):
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        assert ch.name == "sms"

    def test_validate_recipient_valid(self):
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        assert ch.validate_recipient("+14155551234") is True

    def test_validate_recipient_invalid(self):
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        assert ch.validate_recipient("1234567890") is False
        assert ch.validate_recipient("+12") is False
        assert ch.validate_recipient("") is False

    @mock.patch("services.delivery.channels.sms.requests.post")
    def test_send_critical_signal(self, mock_post):
        mock_post.return_value = mock.Mock(
            status_code=201,
            json=lambda: {"sid": "SM123"},
        )
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        result = ch.send(SAMPLE_SIGNAL, "+14155551234")
        assert result.success is True
        assert result.external_message_id == "SM123"

    def test_send_non_critical_signal_blocked(self):
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        low_signal = {**SAMPLE_SIGNAL, "opportunity_score": 50, "opportunity_tier": "LOW"}
        result = ch.send(low_signal, "+14155551234")
        assert result.success is False
        assert result.retryable is False
        assert "threshold" in result.error

    def test_is_critical_hot_tier(self):
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        assert ch._is_critical({"opportunity_tier": "HOT", "opportunity_score": 50}) is True

    def test_is_critical_high_score(self):
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        assert ch._is_critical({"opportunity_tier": "GOOD", "opportunity_score": 85}) is True

    def test_is_critical_low(self):
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        assert ch._is_critical({"opportunity_tier": "LOW", "opportunity_score": 40}) is False

    def test_format(self):
        ch = SMSDeliveryChannel("sid", "token", "+1234567890")
        text = ch._format(SAMPLE_SIGNAL)
        assert "BUY" in text
        assert "BTC/USD" in text
        assert "87" in text


class TestWebhookDeliveryChannel:
    def test_name(self):
        ch = WebhookDeliveryChannel()
        assert ch.name == "webhook"

    @mock.patch("services.delivery.channels.webhook.requests.post")
    def test_send_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        ch = WebhookDeliveryChannel("secret")
        result = ch.send(SAMPLE_SIGNAL, "https://example.com/hook")
        assert result.success is True

    @mock.patch("services.delivery.channels.webhook.requests.post")
    def test_send_server_error(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=500, text="Error")
        ch = WebhookDeliveryChannel()
        result = ch.send(SAMPLE_SIGNAL, "https://example.com/hook")
        assert result.success is False
        assert result.retryable is True

    def test_build_headers_with_signature(self):
        ch = WebhookDeliveryChannel("my-secret")
        headers = ch._build_headers('{"test": true}')
        assert "X-TradeStream-Signature" in headers
        assert len(headers["X-TradeStream-Signature"]) == 64


# ---- Deduplication Tests ----


class TestCrossChannelDeduplicator:
    def _mock_redis(self):
        """Minimal Redis mock supporting smembers, sadd, setex, expire, exists."""
        store = {}

        def smembers(key):
            return store.get(key, set())

        def sadd(key, *values):
            store.setdefault(key, set()).update(values)

        def expire(key, ttl):
            pass

        def setex(key, ttl, value):
            store[key] = value

        def exists(key):
            return key in store

        r = mock.MagicMock()
        r.smembers = mock.MagicMock(side_effect=smembers)
        r.sadd = mock.MagicMock(side_effect=sadd)
        r.expire = mock.MagicMock(side_effect=expire)
        r.setex = mock.MagicMock(side_effect=setex)
        r.exists = mock.MagicMock(side_effect=exists)
        r._store = store
        return r

    def test_primary_only_first_delivery(self):
        dedup = CrossChannelDeduplicator(self._mock_redis())
        assert dedup.should_deliver("sig-1", "user-1", "telegram", "primary_only") is True

    def test_primary_only_blocks_second_channel(self):
        r = self._mock_redis()
        dedup = CrossChannelDeduplicator(r)
        dedup.mark_delivered("sig-1", "user-1", "telegram")
        assert dedup.should_deliver("sig-1", "user-1", "discord", "primary_only") is False

    def test_all_enabled_allows_all(self):
        r = self._mock_redis()
        dedup = CrossChannelDeduplicator(r)
        dedup.mark_delivered("sig-1", "user-1", "telegram")
        assert dedup.should_deliver("sig-1", "user-1", "discord", "all_enabled") is True

    def test_fallback_chain_allows_after_failure(self):
        r = self._mock_redis()
        dedup = CrossChannelDeduplicator(r)
        dedup.mark_delivered("sig-1", "user-1", "telegram")
        dedup.mark_failed("sig-1", "user-1", "telegram")
        assert dedup.should_deliver("sig-1", "user-1", "email", "fallback_chain") is True


# ---- Rate Limiter Tests ----


class TestDeliveryRateLimiter:
    def _mock_redis(self):
        store = {}

        def exists(key):
            return key in store

        def setex(key, ttl, value):
            store[key] = value

        def incr(key):
            store[key] = store.get(key, 0) + 1
            return store[key]

        def expire(key, ttl):
            pass

        r = mock.MagicMock()
        r.exists = mock.MagicMock(side_effect=exists)
        r.setex = mock.MagicMock(side_effect=setex)
        r.incr = mock.MagicMock(side_effect=incr)
        r.expire = mock.MagicMock(side_effect=expire)
        return r

    def test_first_message_not_limited(self):
        rl = DeliveryRateLimiter(self._mock_redis())
        assert rl.is_rate_limited("user-1", "telegram", "BTC/USD") is False

    def test_second_message_limited(self):
        r = self._mock_redis()
        rl = DeliveryRateLimiter(r)
        rl.is_rate_limited("user-1", "telegram", "BTC/USD")
        assert rl.is_rate_limited("user-1", "telegram", "BTC/USD") is True

    def test_different_symbol_not_limited(self):
        r = self._mock_redis()
        rl = DeliveryRateLimiter(r)
        rl.is_rate_limited("user-1", "telegram", "BTC/USD")
        assert rl.is_rate_limited("user-1", "telegram", "ETH/USD") is False

    def test_sms_hourly_limit(self):
        r = self._mock_redis()
        rl = DeliveryRateLimiter(r)
        # SMS default: 5 per hour for free tier
        for i in range(5):
            assert rl.is_rate_limited("user-1", "sms", f"SYM{i}") is False
        assert rl.is_rate_limited("user-1", "sms", "SYM6") is True

    def test_pro_tier_gets_higher_sms_limit(self):
        r = self._mock_redis()
        rl = DeliveryRateLimiter(r)
        # Pro tier: 5 * 2.0 = 10 per hour
        for i in range(10):
            assert rl.is_rate_limited("user-1", "sms", f"SYM{i}", "pro") is False
        assert rl.is_rate_limited("user-1", "sms", "SYM11", "pro") is True


# ---- Preferences Tests ----


class TestPreferenceStore:
    def _mock_redis(self):
        store = {}

        def get(key):
            return store.get(key)

        def set(key, value):
            store[key] = value

        r = mock.MagicMock()
        r.get = mock.MagicMock(side_effect=get)
        r.set = mock.MagicMock(side_effect=set)
        return r

    def test_save_and_load(self):
        r = self._mock_redis()
        ps = PreferenceStore(r)
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            channels={
                "telegram": ChannelPreference(
                    channel="telegram", channel_id="12345", is_primary=True
                ),
                "email": ChannelPreference(
                    channel="email", channel_id="user@test.com"
                ),
            },
        )
        ps.save_preferences(prefs)
        loaded = ps.get_preferences("user-1")
        assert loaded is not None
        assert loaded.user_id == "user-1"
        assert "telegram" in loaded.channels
        assert loaded.channels["telegram"].channel_id == "12345"

    def test_get_nonexistent_returns_none(self):
        r = self._mock_redis()
        ps = PreferenceStore(r)
        assert ps.get_preferences("nobody") is None

    def test_set_channel(self):
        r = self._mock_redis()
        ps = PreferenceStore(r)
        ps.set_channel("user-1", ChannelPreference(channel="discord", channel_id="https://discord.webhook"))
        prefs = ps.get_preferences("user-1")
        assert "discord" in prefs.channels

    def test_remove_channel(self):
        r = self._mock_redis()
        ps = PreferenceStore(r)
        ps.set_channel("user-1", ChannelPreference(channel="slack", channel_id="https://slack.webhook"))
        ps.remove_channel("user-1", "slack")
        prefs = ps.get_preferences("user-1")
        assert "slack" not in prefs.channels

    def test_get_enabled_channels(self):
        r = self._mock_redis()
        ps = PreferenceStore(r)
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            channels={
                "telegram": ChannelPreference(channel="telegram", channel_id="123", enabled=True),
                "email": ChannelPreference(channel="email", channel_id="a@b.com", enabled=False),
            },
        )
        ps.save_preferences(prefs)
        enabled = ps.get_enabled_channels("user-1")
        assert len(enabled) == 1
        assert enabled[0].channel == "telegram"


# ---- Tracker Tests ----


class TestDeliveryTracker:
    def _mock_redis(self):
        store = {}
        lists = {}

        def setex(key, ttl, value):
            store[key] = value

        def get(key):
            return store.get(key)

        def lpush(key, value):
            lists.setdefault(key, []).insert(0, value)

        def ltrim(key, start, end):
            if key in lists:
                lists[key] = lists[key][start : end + 1]

        def expire(key, ttl):
            pass

        def lrange(key, start, end):
            return lists.get(key, [])[start : end + 1]

        def hincrby(key, field, amount):
            store.setdefault(key, {})
            if not isinstance(store[key], dict):
                store[key] = {}
            store[key][field] = store[key].get(field, 0) + amount

        def hgetall(key):
            return store.get(key, {})

        mock_pipe = mock.MagicMock()
        mock_pipe.setex = mock.MagicMock(side_effect=setex)
        mock_pipe.lpush = mock.MagicMock(side_effect=lpush)
        mock_pipe.ltrim = mock.MagicMock(side_effect=ltrim)
        mock_pipe.expire = mock.MagicMock(side_effect=expire)
        mock_pipe.execute = mock.MagicMock()

        r = mock.MagicMock()
        r.pipeline.return_value = mock_pipe
        r.setex = mock.MagicMock(side_effect=setex)
        r.get = mock.MagicMock(side_effect=get)
        r.lrange = mock.MagicMock(side_effect=lrange)
        r.hincrby = mock.MagicMock(side_effect=hincrby)
        r.hgetall = mock.MagicMock(side_effect=hgetall)
        return r

    def test_create_receipt(self):
        tracker = DeliveryTracker(self._mock_redis())
        receipt = tracker.create_receipt("sig-1", "user-1", "telegram")
        assert receipt.status == "pending"
        assert receipt.signal_id == "sig-1"

    def test_get_recent_empty(self):
        tracker = DeliveryTracker(self._mock_redis())
        assert tracker.get_recent() == []


# ---- Router Tests ----


class _FakeChannel(DeliveryChannel):
    """Fake channel for testing the router."""

    def __init__(self, channel_name: str, succeed: bool = True):
        self._name = channel_name
        self._succeed = succeed
        self.sent_signals = []

    @property
    def name(self) -> str:
        return self._name

    def send(self, signal: dict, recipient: str) -> DeliveryResult:
        self.sent_signals.append((signal, recipient))
        if self._succeed:
            return DeliveryResult.ok(self._name, external_id="ext-123")
        return DeliveryResult.fail(self._name, "test failure", retryable=False)


class TestDeliveryRouter:
    def _mock_redis(self):
        store = {}
        sets = {}

        def get(key):
            return store.get(key)

        def set_fn(key, value):
            store[key] = value

        def exists(key):
            return key in store

        def setex(key, ttl, value):
            store[key] = value

        def sadd(key, *values):
            sets.setdefault(key, set()).update(values)

        def smembers(key):
            return sets.get(key, set())

        def expire(key, ttl):
            pass

        def incr(key):
            store[key] = store.get(key, 0) + 1
            return store[key]

        def lpush(key, value):
            store.setdefault(f"list:{key}", []).insert(0, value)

        def ltrim(key, start, end):
            pass

        def lrange(key, start, end):
            return store.get(f"list:{key}", [])[start : end + 1]

        def hincrby(key, field, amount):
            pass

        def hgetall(key):
            return {}

        mock_pipe = mock.MagicMock()
        mock_pipe.setex = mock.MagicMock(side_effect=setex)
        mock_pipe.lpush = mock.MagicMock(side_effect=lpush)
        mock_pipe.ltrim = mock.MagicMock(side_effect=ltrim)
        mock_pipe.expire = mock.MagicMock(side_effect=expire)
        mock_pipe.execute = mock.MagicMock()

        r = mock.MagicMock()
        r.get = mock.MagicMock(side_effect=get)
        r.set = mock.MagicMock(side_effect=set_fn)
        r.exists = mock.MagicMock(side_effect=exists)
        r.setex = mock.MagicMock(side_effect=setex)
        r.sadd = mock.MagicMock(side_effect=sadd)
        r.smembers = mock.MagicMock(side_effect=smembers)
        r.expire = mock.MagicMock(side_effect=expire)
        r.incr = mock.MagicMock(side_effect=incr)
        r.lpush = mock.MagicMock(side_effect=lpush)
        r.ltrim = mock.MagicMock(side_effect=ltrim)
        r.lrange = mock.MagicMock(side_effect=lrange)
        r.hincrby = mock.MagicMock(side_effect=hincrby)
        r.hgetall = mock.MagicMock(side_effect=hgetall)
        r.pipeline.return_value = mock_pipe
        return r

    def _build_router(self, redis_client, channels_config=None):
        if channels_config is None:
            channels_config = {
                "telegram": _FakeChannel("telegram"),
                "email": _FakeChannel("email"),
                "discord": _FakeChannel("discord"),
            }

        pref_store = PreferenceStore(redis_client)
        dedup = CrossChannelDeduplicator(redis_client)
        rate_limiter = DeliveryRateLimiter(redis_client)
        tracker = DeliveryTracker(redis_client)

        return DeliveryRouter(
            channels=channels_config,
            preference_store=pref_store,
            deduplicator=dedup,
            rate_limiter=rate_limiter,
            tracker=tracker,
        )

    def test_route_signal_no_preferences(self):
        r = self._mock_redis()
        router = self._build_router(r)
        results = router.route_signal(SAMPLE_SIGNAL, "user-1")
        assert results == []

    def test_route_signal_primary_only(self):
        r = self._mock_redis()
        router = self._build_router(r)

        # Set up user preferences
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            dedup_preference="primary_only",
            primary_channel="telegram",
            channels={
                "telegram": ChannelPreference(
                    channel="telegram", channel_id="12345", is_primary=True
                ),
                "email": ChannelPreference(
                    channel="email", channel_id="user@test.com"
                ),
            },
        )
        router.preference_store.save_preferences(prefs)

        results = router.route_signal(SAMPLE_SIGNAL, "user-1")
        assert len(results) == 1
        assert results[0].channel == "telegram"
        assert results[0].success is True

    def test_route_signal_all_enabled(self):
        r = self._mock_redis()
        router = self._build_router(r)

        prefs = UserDeliveryPreferences(
            user_id="user-1",
            dedup_preference="all_enabled",
            primary_channel="telegram",
            channels={
                "telegram": ChannelPreference(
                    channel="telegram", channel_id="12345", is_primary=True
                ),
                "email": ChannelPreference(
                    channel="email", channel_id="user@test.com"
                ),
            },
        )
        router.preference_store.save_preferences(prefs)

        results = router.route_signal(SAMPLE_SIGNAL, "user-1")
        assert len(results) == 2
        channels_sent = {r.channel for r in results}
        assert "telegram" in channels_sent
        assert "email" in channels_sent

    def test_route_signal_respects_min_score(self):
        r = self._mock_redis()
        router = self._build_router(r)

        prefs = UserDeliveryPreferences(
            user_id="user-1",
            dedup_preference="primary_only",
            primary_channel="telegram",
            channels={
                "telegram": ChannelPreference(
                    channel="telegram",
                    channel_id="12345",
                    is_primary=True,
                    min_opportunity_score=90,  # Signal score is 87
                ),
            },
        )
        router.preference_store.save_preferences(prefs)

        results = router.route_signal(SAMPLE_SIGNAL, "user-1")
        assert len(results) == 0

    def test_route_signal_respects_symbol_filter(self):
        r = self._mock_redis()
        router = self._build_router(r)

        prefs = UserDeliveryPreferences(
            user_id="user-1",
            dedup_preference="primary_only",
            primary_channel="telegram",
            channels={
                "telegram": ChannelPreference(
                    channel="telegram",
                    channel_id="12345",
                    is_primary=True,
                    symbols=["ETH/USD"],  # Not BTC/USD
                ),
            },
        )
        router.preference_store.save_preferences(prefs)

        results = router.route_signal(SAMPLE_SIGNAL, "user-1")
        assert len(results) == 0

    def test_route_signal_failed_channel(self):
        r = self._mock_redis()
        fail_channel = _FakeChannel("telegram", succeed=False)
        router = self._build_router(r, channels_config={"telegram": fail_channel})

        prefs = UserDeliveryPreferences(
            user_id="user-1",
            dedup_preference="primary_only",
            primary_channel="telegram",
            channels={
                "telegram": ChannelPreference(
                    channel="telegram", channel_id="12345", is_primary=True
                ),
            },
        )
        router.preference_store.save_preferences(prefs)

        results = router.route_signal(SAMPLE_SIGNAL, "user-1")
        assert len(results) == 1
        assert results[0].success is False

    def test_route_signal_to_all_users(self):
        r = self._mock_redis()
        router = self._build_router(r)

        for uid in ["user-1", "user-2"]:
            prefs = UserDeliveryPreferences(
                user_id=uid,
                dedup_preference="primary_only",
                primary_channel="telegram",
                channels={
                    "telegram": ChannelPreference(
                        channel="telegram", channel_id=f"chat-{uid}", is_primary=True
                    ),
                },
            )
            router.preference_store.save_preferences(prefs)

        results = router.route_signal_to_all_users(SAMPLE_SIGNAL, ["user-1", "user-2"])
        assert len(results) == 2
        assert len(results["user-1"]) == 1
        assert len(results["user-2"]) == 1


class TestRouterMatchesFilters:
    def test_matches_all_when_no_filters(self):
        router = DeliveryRouter.__new__(DeliveryRouter)
        ch_pref = ChannelPreference(channel="telegram", channel_id="123")
        assert router._matches_filters(ch_pref, SAMPLE_SIGNAL) is True

    def test_blocks_below_min_score(self):
        router = DeliveryRouter.__new__(DeliveryRouter)
        ch_pref = ChannelPreference(channel="telegram", channel_id="123", min_opportunity_score=95)
        assert router._matches_filters(ch_pref, SAMPLE_SIGNAL) is False

    def test_blocks_wrong_symbol(self):
        router = DeliveryRouter.__new__(DeliveryRouter)
        ch_pref = ChannelPreference(
            channel="telegram", channel_id="123", symbols=["ETH/USD"]
        )
        assert router._matches_filters(ch_pref, SAMPLE_SIGNAL) is False

    def test_passes_matching_symbol(self):
        router = DeliveryRouter.__new__(DeliveryRouter)
        ch_pref = ChannelPreference(
            channel="telegram", channel_id="123", symbols=["BTC/USD", "ETH/USD"]
        )
        assert router._matches_filters(ch_pref, SAMPLE_SIGNAL) is True

    def test_blocks_wrong_action(self):
        router = DeliveryRouter.__new__(DeliveryRouter)
        ch_pref = ChannelPreference(
            channel="telegram", channel_id="123", actions=["SELL"]
        )
        assert router._matches_filters(ch_pref, SAMPLE_SIGNAL) is False
