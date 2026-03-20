"""Tests for multi-channel delivery: SMS, deduplication, rate limiting, routing, tracking."""

import json
import time
from unittest import mock

import pytest

from services.notification_service.channel import DeliveryChannel
from services.notification_service.deduplicator import CrossChannelDeduplicator
from services.notification_service.delivery_router import (
    DeliveryResult,
    DeliveryRouter,
    RoutingResult,
)
from services.notification_service.delivery_tracker import (
    DeliveryReceipt,
    DeliveryTracker,
)
from services.notification_service.rate_limiter import DeliveryRateLimiter
from services.notification_service.sms_sender import SmsSender
from services.notification_service.user_preferences import (
    ChannelPreference,
    QuietHours,
    UserDeliveryPreferences,
    UserPreferencesStore,
)


SAMPLE_SIGNAL = {
    "signal_id": "sig-001",
    "symbol": "BTC/USD",
    "action": "BUY",
    "confidence": 0.85,
    "opportunity_score": 42,
    "summary": "Strong uptrend confirmed.",
    "priority": "normal",
}

CRITICAL_SIGNAL = {
    **SAMPLE_SIGNAL,
    "signal_id": "sig-crit",
    "priority": "critical",
    "action": "SELL",
    "summary": "Stop-loss triggered.",
}


# --- Mock Redis ---


class MockRedis:
    """In-memory Redis mock for testing."""

    def __init__(self):
        self._data = {}
        self._sorted_sets = {}
        self._hashes = {}
        self._lists = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._data:
            return False
        self._data[key] = value
        return True

    def get(self, key):
        return self._data.get(key)

    def setex(self, key, ttl, value):
        self._data[key] = value

    def exists(self, key):
        return key in self._data

    def zadd(self, key, mapping):
        self._sorted_sets.setdefault(key, {}).update(mapping)

    def zremrangebyscore(self, key, min_score, max_score):
        ss = self._sorted_sets.get(key, {})
        if min_score == "-inf":
            min_score = float("-inf")
        to_remove = [k for k, v in ss.items() if v <= float(max_score)]
        for k in to_remove:
            del ss[k]

    def zcard(self, key):
        return len(self._sorted_sets.get(key, {}))

    def expire(self, key, ttl):
        pass

    def hincrby(self, key, field, amount):
        self._hashes.setdefault(key, {})
        current = int(self._hashes[key].get(field, 0))
        self._hashes[key][field] = str(current + amount)

    def hincrbyfloat(self, key, field, amount):
        self._hashes.setdefault(key, {})
        current = float(self._hashes[key].get(field, 0))
        self._hashes[key][field] = str(current + amount)

    def hgetall(self, key):
        return self._hashes.get(key, {})

    def lpush(self, key, value):
        self._lists.setdefault(key, []).insert(0, value)

    def ltrim(self, key, start, end):
        if key in self._lists:
            self._lists[key] = self._lists[key][start : end + 1]

    def lrange(self, key, start, end):
        lst = self._lists.get(key, [])
        return lst[start : end + 1 if end >= 0 else None]

    def pipeline(self):
        return MockPipeline(self)


class MockPipeline:
    """Mock Redis pipeline that executes immediately."""

    def __init__(self, redis):
        self._redis = redis
        self._results = []

    def __getattr__(self, name):
        method = getattr(self._redis, name)

        def wrapper(*args, **kwargs):
            result = method(*args, **kwargs)
            self._results.append(result)
            return self

        return wrapper

    def execute(self):
        results = self._results
        self._results = []
        return results


# --- SMS Sender Tests ---


class TestSmsSender:
    def test_format_signal(self):
        sender = SmsSender("SID", "TOKEN", "+1111", "+2222")
        msg = sender._format_signal(SAMPLE_SIGNAL)
        assert "BUY" in msg
        assert "BTC/USD" in msg
        assert "85%" in msg
        assert "TradeStream" in msg

    def test_format_signal_truncates_long_summary(self):
        sender = SmsSender("SID", "TOKEN", "+1111", "+2222")
        sig = {**SAMPLE_SIGNAL, "summary": "A" * 200}
        msg = sender._format_signal(sig)
        assert len(msg) <= 160

    @mock.patch("services.notification_service.sms_sender.requests.post")
    def test_send_signal_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=201)
        sender = SmsSender("SID", "TOKEN", "+1111", "+2222")
        assert sender.send_signal(SAMPLE_SIGNAL) is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["data"]["To"] == "+2222"
        assert call_kwargs[1]["auth"] == ("SID", "TOKEN")

    @mock.patch("services.notification_service.sms_sender.requests.post")
    def test_send_signal_failure(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=400, text="Invalid number")
        sender = SmsSender("SID", "TOKEN", "+1111", "+2222")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    @mock.patch("services.notification_service.sms_sender.requests.post")
    def test_send_signal_network_error(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("timeout")
        sender = SmsSender("SID", "TOKEN", "+1111", "+2222")
        assert sender.send_signal(SAMPLE_SIGNAL) is False

    def test_supports_priority_critical(self):
        sender = SmsSender("SID", "TOKEN", "+1111", "+2222")
        assert sender.supports_priority("critical") is True
        assert sender.supports_priority("high") is True

    def test_rejects_normal_priority(self):
        sender = SmsSender("SID", "TOKEN", "+1111", "+2222")
        assert sender.supports_priority("normal") is False
        assert sender.supports_priority("low") is False

    def test_name_property(self):
        sender = SmsSender("SID", "TOKEN", "+1111", "+2222")
        assert sender.name == "sms"


# --- Deduplicator Tests ---


class TestDeduplicator:
    def test_primary_only_allows_first(self):
        redis = MockRedis()
        dedup = CrossChannelDeduplicator(redis)
        assert (
            dedup.should_deliver(
                "sig-1", "user-1", "telegram", "primary_only", "telegram"
            )
            is True
        )

    def test_primary_only_blocks_non_primary(self):
        redis = MockRedis()
        dedup = CrossChannelDeduplicator(redis)
        assert (
            dedup.should_deliver(
                "sig-1", "user-1", "discord", "primary_only", "telegram"
            )
            is False
        )

    def test_primary_only_blocks_duplicate(self):
        redis = MockRedis()
        dedup = CrossChannelDeduplicator(redis)
        assert (
            dedup.should_deliver(
                "sig-1", "user-1", "telegram", "primary_only", "telegram"
            )
            is True
        )
        assert (
            dedup.should_deliver(
                "sig-1", "user-1", "telegram", "primary_only", "telegram"
            )
            is False
        )

    def test_all_enabled_allows_all_channels(self):
        redis = MockRedis()
        dedup = CrossChannelDeduplicator(redis)
        assert (
            dedup.should_deliver("sig-1", "user-1", "telegram", "all_enabled") is True
        )
        assert dedup.should_deliver("sig-1", "user-1", "discord", "all_enabled") is True
        assert dedup.should_deliver("sig-1", "user-1", "slack", "all_enabled") is True

    def test_all_enabled_blocks_same_channel_duplicate(self):
        redis = MockRedis()
        dedup = CrossChannelDeduplicator(redis)
        assert (
            dedup.should_deliver("sig-1", "user-1", "telegram", "all_enabled") is True
        )
        assert (
            dedup.should_deliver("sig-1", "user-1", "telegram", "all_enabled") is False
        )

    def test_fallback_chain_allows_first(self):
        redis = MockRedis()
        dedup = CrossChannelDeduplicator(redis)
        assert (
            dedup.should_deliver("sig-1", "user-1", "telegram", "fallback_chain")
            is True
        )

    def test_fallback_chain_blocks_after_success(self):
        redis = MockRedis()
        dedup = CrossChannelDeduplicator(redis)
        dedup.should_deliver("sig-1", "user-1", "telegram", "fallback_chain")
        dedup.mark_success("sig-1", "user-1")
        assert (
            dedup.should_deliver("sig-1", "user-1", "discord", "fallback_chain")
            is False
        )

    def test_different_users_independent(self):
        redis = MockRedis()
        dedup = CrossChannelDeduplicator(redis)
        assert (
            dedup.should_deliver(
                "sig-1", "user-1", "telegram", "primary_only", "telegram"
            )
            is True
        )
        assert (
            dedup.should_deliver(
                "sig-1", "user-2", "telegram", "primary_only", "telegram"
            )
            is True
        )


# --- Rate Limiter Tests ---


class TestRateLimiter:
    def test_allows_under_limit(self):
        redis = MockRedis()
        limiter = DeliveryRateLimiter(redis)
        assert limiter.allow("user-1", "telegram") is True

    def test_blocks_over_limit(self):
        redis = MockRedis()
        limiter = DeliveryRateLimiter(redis, limits={"telegram": (2, 3600)})
        assert limiter.allow("user-1", "telegram") is True
        assert limiter.allow("user-1", "telegram") is True
        assert limiter.allow("user-1", "telegram") is False

    def test_tier_multiplier_increases_limit(self):
        redis = MockRedis()
        limiter = DeliveryRateLimiter(redis, limits={"telegram": (2, 3600)})
        # Pro tier = 2x multiplier = 4 allowed
        for _ in range(4):
            assert limiter.allow("user-1", "telegram", tier="pro") is True
        assert limiter.allow("user-1", "telegram", tier="pro") is False

    def test_different_users_independent(self):
        redis = MockRedis()
        limiter = DeliveryRateLimiter(redis, limits={"telegram": (1, 3600)})
        assert limiter.allow("user-1", "telegram") is True
        assert limiter.allow("user-2", "telegram") is True

    def test_different_channels_independent(self):
        redis = MockRedis()
        limiter = DeliveryRateLimiter(
            redis, limits={"telegram": (1, 3600), "discord": (1, 3600)}
        )
        assert limiter.allow("user-1", "telegram") is True
        assert limiter.allow("user-1", "discord") is True

    def test_remaining_count(self):
        redis = MockRedis()
        limiter = DeliveryRateLimiter(redis, limits={"telegram": (5, 3600)})
        assert limiter.remaining("user-1", "telegram") == 5
        limiter.allow("user-1", "telegram")
        assert limiter.remaining("user-1", "telegram") == 4


# --- User Preferences Tests ---


class TestUserPreferences:
    def test_default_preferences(self):
        prefs = UserDeliveryPreferences(user_id="user-1")
        assert prefs.primary_channel == "telegram"
        assert prefs.delivery_mode == "primary_only"
        assert prefs.tier == "free"
        assert prefs.quiet_hours.enabled is False

    def test_channel_enabled_default(self):
        prefs = UserDeliveryPreferences(user_id="user-1", primary_channel="telegram")
        assert prefs.is_channel_enabled("telegram") is True
        assert prefs.is_channel_enabled("discord") is False

    def test_channel_enabled_explicit(self):
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            channels={"discord": ChannelPreference(enabled=True)},
        )
        assert prefs.is_channel_enabled("discord") is True

    def test_channel_filter_confidence(self):
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            channels={"telegram": ChannelPreference(min_confidence=0.9)},
        )
        assert prefs.passes_channel_filter("telegram", SAMPLE_SIGNAL) is False
        high_conf = {**SAMPLE_SIGNAL, "confidence": 0.95}
        assert prefs.passes_channel_filter("telegram", high_conf) is True

    def test_channel_filter_actions(self):
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            channels={"telegram": ChannelPreference(actions=["SELL"])},
        )
        assert prefs.passes_channel_filter("telegram", SAMPLE_SIGNAL) is False
        sell = {**SAMPLE_SIGNAL, "action": "SELL"}
        assert prefs.passes_channel_filter("telegram", sell) is True

    def test_channel_filter_symbols(self):
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            channels={"telegram": ChannelPreference(symbols=["ETH/USD"])},
        )
        assert prefs.passes_channel_filter("telegram", SAMPLE_SIGNAL) is False

    def test_store_roundtrip(self):
        redis = MockRedis()
        store = UserPreferencesStore(redis)
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="discord",
            delivery_mode="all_enabled",
            tier="pro",
            quiet_hours=QuietHours(enabled=True, start_hour=23, end_hour=7),
            channels={
                "discord": ChannelPreference(enabled=True, min_confidence=0.8),
                "sms": ChannelPreference(enabled=True, actions=["SELL"]),
            },
        )
        store.save(prefs)
        loaded = store.get("user-1")
        assert loaded.primary_channel == "discord"
        assert loaded.delivery_mode == "all_enabled"
        assert loaded.tier == "pro"
        assert loaded.quiet_hours.enabled is True
        assert loaded.quiet_hours.start_hour == 23
        assert loaded.channels["discord"].min_confidence == 0.8
        assert loaded.channels["sms"].actions == ["SELL"]

    def test_store_returns_defaults_for_unknown_user(self):
        redis = MockRedis()
        store = UserPreferencesStore(redis)
        prefs = store.get("unknown-user")
        assert prefs.user_id == "unknown-user"
        assert prefs.primary_channel == "telegram"


# --- Delivery Router Tests ---


class MockSender:
    """Test sender that records calls."""

    def __init__(self, name, success=True, priority_filter=None):
        self._name = name
        self._success = success
        self._priority_filter = priority_filter
        self.calls = []

    @property
    def name(self):
        return self._name

    def send_signal(self, signal):
        self.calls.append(signal)
        return self._success

    def supports_priority(self, priority):
        if self._priority_filter is None:
            return True
        return priority in self._priority_filter


class TestDeliveryRouter:
    def _make_router(self, senders=None, redis=None):
        redis = redis or MockRedis()
        if senders is None:
            senders = {
                "telegram": MockSender("telegram"),
                "discord": MockSender("discord"),
                "slack": MockSender("slack"),
            }
        return (
            DeliveryRouter(
                senders=senders,
                redis_client=redis,
            ),
            redis,
        )

    def test_primary_only_sends_to_primary(self):
        router, _ = self._make_router()
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            delivery_mode="primary_only",
        )
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert len(result.results) == 1
        assert result.results[0].channel == "telegram"
        assert result.results[0].success is True

    def test_all_enabled_sends_to_all(self):
        router, _ = self._make_router()
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            delivery_mode="all_enabled",
            channels={
                "telegram": ChannelPreference(enabled=True),
                "discord": ChannelPreference(enabled=True),
                "slack": ChannelPreference(enabled=True),
            },
        )
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        delivered = [r for r in result.results if r.success]
        assert len(delivered) == 3

    def test_disabled_channel_skipped(self):
        router, _ = self._make_router()
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            delivery_mode="all_enabled",
            channels={
                "telegram": ChannelPreference(enabled=True),
                "discord": ChannelPreference(enabled=False),
            },
        )
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        channels = [r.channel for r in result.results if r.success]
        assert "discord" not in channels

    def test_channel_filter_skips_low_confidence(self):
        router, _ = self._make_router()
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            delivery_mode="primary_only",
            channels={"telegram": ChannelPreference(min_confidence=0.95)},
        )
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert result.results[0].skipped_reason == "channel_filter"

    def test_rate_limited_signal_skipped(self):
        redis = MockRedis()
        senders = {"telegram": MockSender("telegram")}
        limiter = DeliveryRateLimiter(redis, limits={"telegram": (0, 3600)})
        router = DeliveryRouter(
            senders=senders,
            redis_client=redis,
            rate_limiter=limiter,
        )
        prefs = UserDeliveryPreferences(user_id="user-1", primary_channel="telegram")
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert result.results[0].skipped_reason == "rate_limited"

    def test_quiet_hours_blocks_normal_signals(self):
        router, _ = self._make_router()
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            quiet_hours=QuietHours(enabled=True, start_hour=0, end_hour=24),
        )
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert result.results[0].skipped_reason == "quiet_hours"

    def test_quiet_hours_allows_critical_signals(self):
        router, _ = self._make_router()
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            quiet_hours=QuietHours(enabled=True, start_hour=0, end_hour=24),
        )
        result = router.route(CRITICAL_SIGNAL, "user-1", prefs)
        assert not result.all_skipped

    def test_priority_filter_on_sender(self):
        sms_sender = MockSender("sms", priority_filter={"critical", "high"})
        senders = {"sms": sms_sender}
        redis = MockRedis()
        router = DeliveryRouter(senders=senders, redis_client=redis)
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="sms",
            delivery_mode="primary_only",
        )
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert result.results[0].skipped_reason == "priority_not_supported"

        result = router.route(CRITICAL_SIGNAL, "user-1", prefs)
        assert result.results[0].success is True

    def test_fallback_chain_stops_after_success(self):
        telegram = MockSender("telegram")
        discord = MockSender("discord")
        senders = {"telegram": telegram, "discord": discord}
        redis = MockRedis()
        router = DeliveryRouter(senders=senders, redis_client=redis)
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            delivery_mode="fallback_chain",
            channels={
                "telegram": ChannelPreference(enabled=True),
                "discord": ChannelPreference(enabled=True),
            },
        )
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert len(telegram.calls) == 1
        assert len(discord.calls) == 0

    def test_fallback_chain_falls_through_on_failure(self):
        telegram = MockSender("telegram", success=False)
        discord = MockSender("discord", success=True)
        senders = {"telegram": telegram, "discord": discord}
        redis = MockRedis()
        router = DeliveryRouter(senders=senders, redis_client=redis)
        prefs = UserDeliveryPreferences(
            user_id="user-1",
            primary_channel="telegram",
            delivery_mode="fallback_chain",
            channels={
                "telegram": ChannelPreference(enabled=True),
                "discord": ChannelPreference(enabled=True),
            },
        )
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert len(telegram.calls) == 1
        assert len(discord.calls) == 1
        assert result.any_success is True

    def test_sender_exception_handled(self):
        class FailingSender:
            name = "broken"

            def send_signal(self, signal):
                raise RuntimeError("connection reset")

            def supports_priority(self, p):
                return True

        senders = {"broken": FailingSender()}
        redis = MockRedis()
        router = DeliveryRouter(senders=senders, redis_client=redis)
        prefs = UserDeliveryPreferences(user_id="user-1", primary_channel="broken")
        result = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert result.results[0].success is False
        assert "connection reset" in result.results[0].error

    def test_deduplication_blocks_second_delivery(self):
        router, _ = self._make_router()
        prefs = UserDeliveryPreferences(user_id="user-1", primary_channel="telegram")
        result1 = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert result1.results[0].success is True
        result2 = router.route(SAMPLE_SIGNAL, "user-1", prefs)
        assert result2.results[0].skipped_reason == "deduplicated"


# --- Delivery Tracker Tests ---


class TestDeliveryTracker:
    def test_record_and_get_receipt(self):
        redis = MockRedis()
        tracker = DeliveryTracker(redis)
        receipt = DeliveryReceipt(
            receipt_id="r-1",
            signal_id="sig-1",
            user_id="user-1",
            channel="telegram",
            status="delivered",
            timestamp=time.time(),
            latency_ms=42.5,
        )
        tracker.record(receipt)
        loaded = tracker.get_receipt("sig-1", "telegram")
        assert loaded is not None
        assert loaded["status"] == "delivered"
        assert loaded["latency_ms"] == 42.5

    def test_channel_metrics(self):
        redis = MockRedis()
        tracker = DeliveryTracker(redis)
        for i in range(3):
            tracker.record(
                DeliveryReceipt(
                    receipt_id=f"r-{i}",
                    signal_id=f"sig-{i}",
                    user_id="user-1",
                    channel="telegram",
                    status="delivered",
                    timestamp=time.time(),
                    latency_ms=10.0,
                )
            )
        tracker.record(
            DeliveryReceipt(
                receipt_id="r-fail",
                signal_id="sig-fail",
                user_id="user-1",
                channel="telegram",
                status="failed",
                timestamp=time.time(),
                error="timeout",
            )
        )
        metrics = tracker.get_channel_metrics("telegram")
        assert metrics["total"] == 4
        assert metrics["delivered"] == 3
        assert metrics["failed"] == 1

    def test_dlq_captures_failures(self):
        redis = MockRedis()
        tracker = DeliveryTracker(redis)
        tracker.record(
            DeliveryReceipt(
                receipt_id="r-fail",
                signal_id="sig-fail",
                user_id="user-1",
                channel="slack",
                status="failed",
                timestamp=time.time(),
                error="webhook 500",
            )
        )
        dlq = tracker.get_dlq()
        assert len(dlq) == 1
        assert dlq[0]["error"] == "webhook 500"

    def test_get_receipt_missing(self):
        redis = MockRedis()
        tracker = DeliveryTracker(redis)
        assert tracker.get_receipt("none", "none") is None


# --- Abstract Channel Interface Test ---


class TestDeliveryChannelInterface:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            DeliveryChannel()

    def test_concrete_implementation(self):
        class TestChannel(DeliveryChannel):
            @property
            def name(self):
                return "test"

            def send_signal(self, signal):
                return True

        ch = TestChannel()
        assert ch.name == "test"
        assert ch.send_signal({}) is True
        assert ch.supports_priority("any") is True
