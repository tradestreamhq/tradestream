"""Tests for the sliding window rate limiter."""

import time
from unittest.mock import patch

import pytest

from services.usage_api.rate_limiter import (
    SlidingWindowRateLimiter,
    TierConfig,
)


class TestTierConfiguration:
    def test_default_tiers(self):
        limiter = SlidingWindowRateLimiter()
        assert limiter.get_user_tier("new_user") == "free"

    def test_set_user_tier(self):
        limiter = SlidingWindowRateLimiter()
        limiter.set_user_tier("user1", "pro")
        assert limiter.get_user_tier("user1") == "pro"

    def test_invalid_tier_raises(self):
        limiter = SlidingWindowRateLimiter()
        with pytest.raises(ValueError, match="Unknown tier"):
            limiter.set_user_tier("user1", "enterprise")

    def test_custom_tiers(self):
        custom = {"test": TierConfig(name="test", requests_per_hour=5)}
        limiter = SlidingWindowRateLimiter(tier_configs=custom)
        limiter.set_user_tier("user1", "test")
        assert limiter.get_user_tier("user1") == "test"


class TestSlidingWindowCounter:
    def test_allows_within_limit(self):
        limiter = SlidingWindowRateLimiter(
            tier_configs={"free": TierConfig("free", 5)},
            window_seconds=60,
        )
        for i in range(5):
            allowed, limit, remaining, reset = limiter.check_and_record(
                "user1", "/api/test"
            )
            assert allowed is True
            assert limit == 5
            assert remaining == 5 - i - 1

    def test_blocks_at_limit(self):
        limiter = SlidingWindowRateLimiter(
            tier_configs={"free": TierConfig("free", 3)},
            window_seconds=60,
        )
        for _ in range(3):
            allowed, _, _, _ = limiter.check_and_record("user1", "/api/test")
            assert allowed is True

        allowed, limit, remaining, reset = limiter.check_and_record(
            "user1", "/api/test"
        )
        assert allowed is False
        assert limit == 3
        assert remaining == 0

    def test_window_expiration(self):
        limiter = SlidingWindowRateLimiter(
            tier_configs={"free": TierConfig("free", 2)},
            window_seconds=10,
        )

        base_time = 1000.0
        with patch("services.usage_api.rate_limiter.time") as mock_time:
            mock_time.time.return_value = base_time
            mock_time.strftime = time.strftime
            mock_time.gmtime = time.gmtime

            limiter.check_and_record("user1", "/api/a")
            limiter.check_and_record("user1", "/api/b")

            allowed, _, _, _ = limiter.check_and_record("user1", "/api/c")
            assert allowed is False

            # Advance past window
            mock_time.time.return_value = base_time + 11
            allowed, _, remaining, _ = limiter.check_and_record("user1", "/api/c")
            assert allowed is True
            assert remaining == 1

    def test_separate_users_independent(self):
        limiter = SlidingWindowRateLimiter(
            tier_configs={"free": TierConfig("free", 2)},
            window_seconds=60,
        )
        limiter.check_and_record("user1", "/api/test")
        limiter.check_and_record("user1", "/api/test")

        allowed, _, remaining, _ = limiter.check_and_record("user2", "/api/test")
        assert allowed is True
        assert remaining == 1

    def test_different_tiers_different_limits(self):
        tiers = {
            "free": TierConfig("free", 2),
            "pro": TierConfig("pro", 100),
        }
        limiter = SlidingWindowRateLimiter(tier_configs=tiers, window_seconds=60)
        limiter.set_user_tier("pro_user", "pro")

        # Free user hits limit after 2
        limiter.check_and_record("free_user", "/api/test")
        limiter.check_and_record("free_user", "/api/test")
        allowed, _, _, _ = limiter.check_and_record("free_user", "/api/test")
        assert allowed is False

        # Pro user still has plenty of room
        for _ in range(10):
            allowed, _, _, _ = limiter.check_and_record("pro_user", "/api/test")
            assert allowed is True

    def test_reset_timestamp(self):
        limiter = SlidingWindowRateLimiter(
            tier_configs={"free": TierConfig("free", 1)},
            window_seconds=3600,
        )

        base_time = 1000.0
        with patch("services.usage_api.rate_limiter.time") as mock_time:
            mock_time.time.return_value = base_time
            mock_time.strftime = time.strftime
            mock_time.gmtime = time.gmtime

            _, _, _, reset = limiter.check_and_record("user1", "/api/test")
            assert reset == base_time + 3600

            # When blocked, reset should be based on earliest record
            allowed, _, _, reset = limiter.check_and_record("user1", "/api/test")
            assert allowed is False
            assert reset == base_time + 3600


class TestUsageTracking:
    def test_current_usage(self):
        limiter = SlidingWindowRateLimiter(
            tier_configs={"free": TierConfig("free", 100)},
            window_seconds=3600,
        )
        limiter.check_and_record("user1", "/api/a")
        limiter.check_and_record("user1", "/api/a")
        limiter.check_and_record("user1", "/api/b")

        usage = limiter.get_current_usage("user1")
        assert usage["user_id"] == "user1"
        assert usage["tier"] == "free"
        assert usage["used"] == 3
        assert usage["remaining"] == 97
        assert usage["limit"] == 100
        assert usage["endpoints"] == {"/api/a": 2, "/api/b": 1}

    def test_current_usage_empty(self):
        limiter = SlidingWindowRateLimiter()
        usage = limiter.get_current_usage("new_user")
        assert usage["used"] == 0
        assert usage["remaining"] == 100
        assert usage["endpoints"] == {}

    def test_usage_history(self):
        limiter = SlidingWindowRateLimiter(
            tier_configs={"free": TierConfig("free", 100)},
            window_seconds=3600,
        )
        limiter.check_and_record("user1", "/api/test")
        limiter.check_and_record("user1", "/api/other")

        history = limiter.get_usage_history("user1")
        assert len(history) >= 1
        day_entry = history[0]
        assert "date" in day_entry
        assert day_entry["total_requests"] == 2

    def test_usage_history_empty(self):
        limiter = SlidingWindowRateLimiter()
        history = limiter.get_usage_history("new_user")
        assert history == []
