"""Tests for E2E test data generators and cleanup utilities.

Validates that test data factories produce realistic, well-formed data
and that cleanup utilities properly reset state.
"""

import json
import uuid
from datetime import datetime, timezone

import pytest

from tests.e2e.conftest import (
    FakePool,
    FakeRedis,
    FakeRow,
    make_candles,
    make_signal,
    make_strategy_performance,
    make_subscription,
)


# ---------------------------------------------------------------------------
# Tests: Signal Factory
# ---------------------------------------------------------------------------


class TestSignalFactory:
    """Validate make_signal produces well-formed signals."""

    def test_default_signal_has_required_fields(self):
        signal = make_signal()
        required = [
            "signal_id",
            "strategy_name",
            "instrument",
            "direction",
            "confidence",
            "entry_price",
            "stop_loss",
            "take_profit",
            "timestamp",
        ]
        for field in required:
            assert field in signal, f"Missing field: {field}"

    def test_signal_id_is_valid_uuid(self):
        signal = make_signal()
        uuid.UUID(signal["signal_id"])  # raises if invalid

    def test_signal_timestamp_is_iso_format(self):
        signal = make_signal()
        # Should not raise
        datetime.fromisoformat(signal["timestamp"])

    def test_signal_confidence_in_range(self):
        signal = make_signal(confidence=0.95)
        assert 0.0 <= signal["confidence"] <= 1.0

    def test_signal_overrides_work(self):
        signal = make_signal(
            strategy_name="custom_strat",
            instrument="SOL/USD",
            direction="SELL",
            extra_field="hello",
        )
        assert signal["strategy_name"] == "custom_strat"
        assert signal["instrument"] == "SOL/USD"
        assert signal["direction"] == "SELL"
        assert signal["extra_field"] == "hello"

    def test_each_signal_gets_unique_id(self):
        signals = [make_signal() for _ in range(100)]
        ids = [s["signal_id"] for s in signals]
        assert len(set(ids)) == 100

    def test_signal_stop_loss_below_entry_for_buy(self):
        signal = make_signal(direction="BUY", entry_price=100, stop_loss=95)
        assert signal["stop_loss"] < signal["entry_price"]

    def test_signal_take_profit_above_entry_for_buy(self):
        signal = make_signal(direction="BUY", entry_price=100, take_profit=110)
        assert signal["take_profit"] > signal["entry_price"]


# ---------------------------------------------------------------------------
# Tests: Candle Factory
# ---------------------------------------------------------------------------


class TestCandleFactory:
    """Validate make_candles produces realistic OHLCV data."""

    def test_default_candle_count(self):
        candles = make_candles()
        assert len(candles) == 30

    def test_custom_candle_count(self):
        candles = make_candles(n=100)
        assert len(candles) == 100

    def test_candle_has_ohlcv_fields(self):
        candles = make_candles(n=1)
        c = candles[0]
        assert "open" in c
        assert "high" in c
        assert "low" in c
        assert "close" in c
        assert "volume" in c

    def test_high_is_highest(self):
        candles = make_candles(n=50)
        for c in candles:
            assert c["high"] >= c["low"]

    def test_volume_is_non_negative(self):
        candles = make_candles(n=50)
        for c in candles:
            assert c["volume"] >= 0

    def test_uptrend_has_rising_prices(self):
        candles = make_candles(n=30, trend="up", base_price=100)
        assert candles[-1]["close"] > candles[0]["close"]

    def test_downtrend_has_falling_prices(self):
        candles = make_candles(n=30, trend="down", base_price=100)
        assert candles[-1]["close"] < candles[0]["close"]

    def test_high_volatility_wider_ranges(self):
        low_vol = make_candles(n=30, volatility=0.01)
        high_vol = make_candles(n=30, volatility=0.10)
        low_ranges = [c["high"] - c["low"] for c in low_vol]
        high_ranges = [c["high"] - c["low"] for c in high_vol]
        avg_low = sum(low_ranges) / len(low_ranges)
        avg_high = sum(high_ranges) / len(high_ranges)
        assert avg_high > avg_low

    def test_deterministic_with_seed(self):
        """make_candles uses seed(42), so two calls produce the same data."""
        c1 = make_candles(n=10)
        c2 = make_candles(n=10)
        assert c1 == c2


# ---------------------------------------------------------------------------
# Tests: Strategy Performance Factory
# ---------------------------------------------------------------------------


class TestStrategyPerformanceFactory:
    """Validate make_strategy_performance produces correct data."""

    def test_default_performance_has_required_fields(self):
        perf = make_strategy_performance()
        required = [
            "strategy_spec_id",
            "sharpe_ratio",
            "win_rate",
            "avg_pnl_percent",
            "trade_count",
        ]
        for field in required:
            assert field in perf

    def test_custom_values(self):
        perf = make_strategy_performance(
            strategy_spec_id="my_strat",
            sharpe_ratio=2.5,
            win_rate=0.75,
        )
        assert perf["strategy_spec_id"] == "my_strat"
        assert perf["sharpe_ratio"] == 2.5
        assert perf["win_rate"] == 0.75

    def test_overrides(self):
        perf = make_strategy_performance(custom_metric=42)
        assert perf["custom_metric"] == 42


# ---------------------------------------------------------------------------
# Tests: Subscription Factory
# ---------------------------------------------------------------------------


class TestSubscriptionFactory:
    """Validate make_subscription produces well-formed subscriptions."""

    def test_default_subscription(self):
        sub = make_subscription()
        assert sub["channel"] == "telegram"
        assert sub["active"] is True

    def test_custom_subscription(self):
        sub = make_subscription(
            channel="webhook",
            endpoint="https://example.com/hook",
            strategies=["strat_a"],
            active=False,
        )
        assert sub["channel"] == "webhook"
        assert sub["endpoint"] == "https://example.com/hook"
        assert sub["strategies"] == ["strat_a"]
        assert sub["active"] is False

    def test_subscription_has_id(self):
        sub = make_subscription()
        uuid.UUID(sub["id"])  # validates it's a proper UUID


# ---------------------------------------------------------------------------
# Tests: FakeRedis Cleanup
# ---------------------------------------------------------------------------


class TestFakeRedisCleanup:
    """Validate FakeRedis state isolation between tests."""

    def test_fresh_redis_is_empty(self):
        redis = FakeRedis()
        assert redis.get("any_key") is None
        assert redis.smembers("any_set") == set()
        assert redis.llen("any_list") == 0

    def test_set_and_delete(self):
        redis = FakeRedis()
        redis.set("key", "value")
        assert redis.get("key") == "value"
        redis.delete("key")
        assert redis.get("key") is None

    def test_set_operations_cleanup(self):
        redis = FakeRedis()
        redis.sadd("myset", "a", "b", "c")
        assert redis.smembers("myset") == {"a", "b", "c"}
        # New instance is clean
        redis2 = FakeRedis()
        assert redis2.smembers("myset") == set()

    def test_list_operations_cleanup(self):
        redis = FakeRedis()
        redis.lpush("mylist", "x", "y")
        assert redis.llen("mylist") == 2
        # New instance is clean
        redis2 = FakeRedis()
        assert redis2.llen("mylist") == 0

    def test_pubsub_messages_isolated(self):
        redis = FakeRedis()
        redis.publish("ch1", "msg1")
        assert len(redis._pubsub_messages) == 1
        # New instance has no messages
        redis2 = FakeRedis()
        assert len(redis2._pubsub_messages) == 0


# ---------------------------------------------------------------------------
# Tests: FakePool Cleanup
# ---------------------------------------------------------------------------


class TestFakePoolCleanup:
    """Validate FakePool state isolation."""

    def test_fresh_pool_has_no_tables(self):
        pool = FakePool()
        assert pool.tables == {}

    def test_pool_with_custom_tables(self):
        tables = {"users": [{"id": 1, "name": "test"}]}
        pool = FakePool(tables=tables)
        assert "users" in pool.tables

    @pytest.mark.asyncio
    async def test_pool_connection_tracks_queries(self):
        pool = FakePool()
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO test VALUES (1)")
            await conn.fetch("SELECT 1")
        assert len(pool._conn._queries) == 2

    @pytest.mark.asyncio
    async def test_new_pool_has_no_query_history(self):
        pool = FakePool()
        assert len(pool._conn._queries) == 0


# ---------------------------------------------------------------------------
# Tests: FakeRow
# ---------------------------------------------------------------------------


class TestFakeRow:
    """Validate FakeRow dict/attribute access."""

    def test_dict_access(self):
        row = FakeRow(name="alice", age=30)
        assert row["name"] == "alice"
        assert row["age"] == 30

    def test_attribute_access(self):
        row = FakeRow(name="alice", age=30)
        assert row.name == "alice"
        assert row.age == 30

    def test_missing_attribute_raises(self):
        row = FakeRow(name="alice")
        with pytest.raises(AttributeError):
            _ = row.missing_field

    def test_iteration(self):
        row = FakeRow(a=1, b=2, c=3)
        assert set(row.keys()) == {"a", "b", "c"}
