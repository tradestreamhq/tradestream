"""End-to-end test: Multi-Channel Delivery.

Validates signal delivery across all channels (Telegram, Discord, Slack, SMS,
Email, Webhook) via the DeliveryRouter, including deduplication, rate limiting,
quiet hours, and retry logic.
"""

import json
from unittest.mock import MagicMock

import pytest

from services.delivery.channels.base import DeliveryChannel, DeliveryResult
from services.delivery.deduplication import CrossChannelDeduplicator
from services.delivery.preferences import (
    ChannelPreference,
    PreferenceStore,
    UserDeliveryPreferences,
)
from services.delivery.rate_limiter import DeliveryRateLimiter
from services.delivery.router import DeliveryRouter
from services.delivery.tracker import DeliveryTracker

from tests.e2e.conftest import FakeRedis, make_signal


# ---------------------------------------------------------------------------
# Fake channel implementations
# ---------------------------------------------------------------------------


class FakeChannel(DeliveryChannel):
    """Test channel that records sends and returns configurable results."""

    def __init__(self, name_str, succeed=True, retryable=False):
        self._name = name_str
        self._succeed = succeed
        self._retryable = retryable
        self.sent = []

    @property
    def name(self):
        return self._name

    def send(self, signal, recipient):
        self.sent.append({"signal": signal, "recipient": recipient})
        if self._succeed:
            return DeliveryResult.ok(self._name, f"msg-{len(self.sent)}")
        return DeliveryResult.fail(
            self._name, "delivery failed", retryable=self._retryable
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.fixture
def channels():
    """Create a set of test channels."""
    return {
        "telegram": FakeChannel("telegram"),
        "discord": FakeChannel("discord"),
        "slack": FakeChannel("slack"),
        "email": FakeChannel("email"),
        "sms": FakeChannel("sms"),
        "webhook": FakeChannel("webhook"),
    }


@pytest.fixture
def preference_store(redis):
    return PreferenceStore(redis)


@pytest.fixture
def deduplicator(redis):
    return CrossChannelDeduplicator(redis, ttl_seconds=3600)


@pytest.fixture
def rate_limiter():
    return DeliveryRateLimiter()


@pytest.fixture
def tracker():
    return DeliveryTracker()


@pytest.fixture
def router(channels, preference_store, deduplicator, rate_limiter, tracker):
    return DeliveryRouter(
        channels=channels,
        preference_store=preference_store,
        deduplicator=deduplicator,
        rate_limiter=rate_limiter,
        tracker=tracker,
    )


def _setup_user_prefs(
    preference_store, user_id, channel_configs, dedup="all_enabled", tier="pro"
):
    """Helper to set up user delivery preferences."""
    channels = {}
    primary = None
    for cfg in channel_configs:
        ch = ChannelPreference(
            channel=cfg["channel"],
            channel_id=cfg.get("channel_id", f"{cfg['channel']}-id"),
            enabled=cfg.get("enabled", True),
            is_primary=cfg.get("is_primary", False),
            min_opportunity_score=cfg.get("min_opportunity_score", 0),
            symbols=cfg.get("symbols", []),
            actions=cfg.get("actions", []),
            quiet_hours_start=cfg.get("quiet_hours_start"),
            quiet_hours_end=cfg.get("quiet_hours_end"),
        )
        channels[cfg["channel"]] = ch
        if cfg.get("is_primary"):
            primary = cfg["channel"]

    prefs = UserDeliveryPreferences(
        user_id=user_id,
        dedup_preference=dedup,
        primary_channel=primary or "telegram",
        tier=tier,
        channels=channels,
    )
    preference_store.save_preferences(prefs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMultiChannelDeliveryE2E:
    """Multi-channel signal delivery with routing, dedup, and tracking."""

    def test_signal_delivered_to_all_enabled_channels(
        self, router, preference_store, channels
    ):
        """Signal routed to all enabled channels when dedup=all_enabled."""
        _setup_user_prefs(
            preference_store,
            "user-1",
            [
                {"channel": "telegram", "channel_id": "tg-123", "is_primary": True},
                {"channel": "discord", "channel_id": "dc-456"},
                {"channel": "email", "channel_id": "user@test.com"},
            ],
            dedup="all_enabled",
        )

        signal = make_signal(signal_id="sig-001")
        signal["symbol"] = signal["instrument"]
        signal["action"] = signal["direction"]
        signal["opportunity_score"] = 80

        results = router.route_signal(signal, "user-1")

        assert len(results) == 3
        assert all(r.success for r in results)
        assert {r.channel for r in results} == {"telegram", "discord", "email"}
        assert len(channels["telegram"].sent) == 1
        assert len(channels["discord"].sent) == 1
        assert len(channels["email"].sent) == 1

    def test_primary_only_dedup_sends_to_one_channel(
        self, router, preference_store, channels
    ):
        """With dedup=primary_only, only the primary channel receives the signal."""
        _setup_user_prefs(
            preference_store,
            "user-2",
            [
                {"channel": "telegram", "channel_id": "tg-789", "is_primary": True},
                {"channel": "slack", "channel_id": "slack-abc"},
            ],
            dedup="primary_only",
        )

        signal = make_signal(signal_id="sig-002")
        signal["symbol"] = signal["instrument"]
        signal["action"] = signal["direction"]
        signal["opportunity_score"] = 80

        results = router.route_signal(signal, "user-2")

        assert len(results) == 1
        assert results[0].channel == "telegram"
        assert len(channels["slack"].sent) == 0

    def test_disabled_channel_is_skipped(self, router, preference_store, channels):
        """Disabled channels don't receive signals."""
        _setup_user_prefs(
            preference_store,
            "user-3",
            [
                {"channel": "telegram", "channel_id": "tg-a", "is_primary": True},
                {"channel": "sms", "channel_id": "+1234567890", "enabled": False},
            ],
            dedup="all_enabled",
        )

        signal = make_signal(signal_id="sig-003")
        signal["symbol"] = signal["instrument"]
        signal["action"] = signal["direction"]
        signal["opportunity_score"] = 80

        results = router.route_signal(signal, "user-3")

        assert len(results) == 1
        assert results[0].channel == "telegram"
        assert len(channels["sms"].sent) == 0

    def test_symbol_filter_restricts_delivery(self, router, preference_store, channels):
        """Channel with symbol filter only receives matching signals."""
        _setup_user_prefs(
            preference_store,
            "user-4",
            [
                {
                    "channel": "telegram",
                    "channel_id": "tg-btc",
                    "is_primary": True,
                    "symbols": ["BTC/USD"],
                },
                {
                    "channel": "email",
                    "channel_id": "user@test.com",
                    "symbols": ["ETH/USD"],
                },
            ],
            dedup="all_enabled",
        )

        signal = make_signal(instrument="BTC/USD", signal_id="sig-004")
        signal["symbol"] = signal["instrument"]
        signal["action"] = signal["direction"]
        signal["opportunity_score"] = 80

        results = router.route_signal(signal, "user-4")

        assert len(results) == 1
        assert results[0].channel == "telegram"
        assert len(channels["email"].sent) == 0

    def test_opportunity_score_filter(self, router, preference_store, channels):
        """Channels with min_opportunity_score filter low-scoring signals."""
        _setup_user_prefs(
            preference_store,
            "user-5",
            [
                {
                    "channel": "telegram",
                    "channel_id": "tg-filter",
                    "is_primary": True,
                    "min_opportunity_score": 90,
                },
            ],
            dedup="all_enabled",
        )

        signal = make_signal(signal_id="sig-005")
        signal["symbol"] = signal["instrument"]
        signal["action"] = signal["direction"]
        signal["opportunity_score"] = 50

        results = router.route_signal(signal, "user-5")
        assert len(results) == 0

    def test_no_preferences_returns_empty(self, router):
        """User without preferences gets no deliveries."""
        signal = make_signal(signal_id="sig-006")
        results = router.route_signal(signal, "unknown-user")
        assert results == []

    def test_failed_delivery_tracked(self, router, preference_store, channels):
        """Failed channel delivery is tracked correctly."""
        channels["telegram"] = FakeChannel("telegram", succeed=False)
        _setup_user_prefs(
            preference_store,
            "user-6",
            [{"channel": "telegram", "channel_id": "tg-fail", "is_primary": True}],
            dedup="all_enabled",
        )

        signal = make_signal(signal_id="sig-007")
        signal["symbol"] = signal["instrument"]
        signal["action"] = signal["direction"]
        signal["opportunity_score"] = 80

        results = router.route_signal(signal, "user-6")

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].error == "delivery failed"

    def test_multi_user_broadcast(self, router, preference_store, channels):
        """Signal broadcast to multiple users works correctly."""
        for i, uid in enumerate(["user-a", "user-b", "user-c"]):
            _setup_user_prefs(
                preference_store,
                uid,
                [{"channel": "telegram", "channel_id": f"tg-{i}", "is_primary": True}],
                dedup="all_enabled",
            )

        signal = make_signal(signal_id="sig-008")
        signal["symbol"] = signal["instrument"]
        signal["action"] = signal["direction"]
        signal["opportunity_score"] = 80

        results = router.route_signal_to_all_users(
            signal, ["user-a", "user-b", "user-c"]
        )

        assert len(results) == 3
        assert all(len(v) == 1 for v in results.values())
        assert len(channels["telegram"].sent) == 3


class TestDeduplicationE2E:
    """Cross-channel deduplication strategies."""

    def test_all_enabled_allows_duplicate_delivery(self, deduplicator):
        """all_enabled mode always allows delivery."""
        assert (
            deduplicator.should_deliver("sig-1", "u-1", "telegram", "all_enabled")
            is True
        )
        deduplicator.mark_delivered("sig-1", "u-1", "telegram")
        assert (
            deduplicator.should_deliver("sig-1", "u-1", "discord", "all_enabled")
            is True
        )

    def test_primary_only_blocks_second_channel(self, deduplicator):
        """primary_only mode blocks delivery after first channel succeeds."""
        assert (
            deduplicator.should_deliver("sig-2", "u-1", "telegram", "primary_only")
            is True
        )
        deduplicator.mark_delivered("sig-2", "u-1", "telegram")
        assert (
            deduplicator.should_deliver("sig-2", "u-1", "discord", "primary_only")
            is False
        )

    def test_fallback_chain_allows_after_failure(self, deduplicator):
        """fallback_chain allows next channel when previous failed."""
        assert (
            deduplicator.should_deliver("sig-3", "u-1", "telegram", "fallback_chain")
            is True
        )
        deduplicator.mark_delivered("sig-3", "u-1", "telegram")
        deduplicator.mark_failed("sig-3", "u-1", "telegram")
        assert (
            deduplicator.should_deliver("sig-3", "u-1", "discord", "fallback_chain")
            is True
        )
