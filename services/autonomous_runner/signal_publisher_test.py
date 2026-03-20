"""Tests for Redis signal publisher."""

import json

import pytest

from services.autonomous_runner.signal_publisher import (
    DEFAULT_CHANNEL,
    SignalPublisher,
)


class FakeRedis:
    def __init__(self):
        self.published = []

    def publish(self, channel, message):
        self.published.append({"channel": channel, "message": message})
        return 1


class BrokenRedis:
    def publish(self, channel, message):
        raise ConnectionError("Redis unavailable")


class TestSignalPublisher:
    def test_publish_success(self):
        redis = FakeRedis()
        pub = SignalPublisher(redis)
        result = pub.publish({"symbol": "BTC-USD", "action": "BUY", "confidence": 0.85})
        assert result is True
        assert len(redis.published) == 1
        msg = json.loads(redis.published[0]["message"])
        assert msg["symbol"] == "BTC-USD"
        assert msg["action"] == "BUY"
        assert "published_at" in msg

    def test_publish_to_correct_channel(self):
        redis = FakeRedis()
        pub = SignalPublisher(redis, channel="custom:channel")
        pub.publish({"symbol": "ETH-USD", "action": "SELL"})
        assert redis.published[0]["channel"] == "custom:channel"

    def test_publish_default_channel(self):
        redis = FakeRedis()
        pub = SignalPublisher(redis)
        pub.publish({"symbol": "BTC-USD", "action": "HOLD"})
        assert redis.published[0]["channel"] == DEFAULT_CHANNEL

    def test_publish_no_redis(self):
        pub = SignalPublisher(redis_client=None)
        result = pub.publish({"symbol": "BTC-USD", "action": "BUY"})
        assert result is False

    def test_publish_redis_error(self):
        pub = SignalPublisher(BrokenRedis())
        result = pub.publish({"symbol": "BTC-USD", "action": "BUY"})
        assert result is False

    def test_publish_batch(self):
        redis = FakeRedis()
        pub = SignalPublisher(redis)
        signals = [
            {"symbol": "BTC-USD", "action": "BUY"},
            {"symbol": "ETH-USD", "action": "SELL"},
            {"symbol": "SOL-USD", "action": "HOLD"},
        ]
        count = pub.publish_batch(signals)
        assert count == 3
        assert len(redis.published) == 3

    def test_get_stats(self):
        redis = FakeRedis()
        pub = SignalPublisher(redis)
        pub.publish({"symbol": "BTC-USD", "action": "BUY"})
        stats = pub.get_stats()
        assert stats["published_count"] == 1
        assert stats["failed_count"] == 0
        assert stats["redis_connected"] is True

    def test_get_stats_with_failures(self):
        pub = SignalPublisher(BrokenRedis())
        pub.publish({"symbol": "BTC-USD", "action": "BUY"})
        stats = pub.get_stats()
        assert stats["published_count"] == 0
        assert stats["failed_count"] == 1

    def test_stats_no_redis(self):
        pub = SignalPublisher(redis_client=None)
        stats = pub.get_stats()
        assert stats["redis_connected"] is False
