"""Shared fixtures for end-to-end integration tests.

Provides test doubles for external services (database, Redis, Stripe, Telegram,
webhooks) and factory helpers for building realistic test data.
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fake database row (dict-like, as returned by asyncpg)
# ---------------------------------------------------------------------------


class FakeRow(dict):
    """Simulates an asyncpg Record that supports both dict and attribute access."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


# ---------------------------------------------------------------------------
# In-memory database pool stub
# ---------------------------------------------------------------------------


class FakeConnection:
    """In-memory database connection that stores rows in plain dicts."""

    def __init__(self, tables: Dict[str, List[dict]]):
        self._tables = tables
        self._queries: List[str] = []

    async def fetch(self, query, *args):
        self._queries.append(query)
        return self._match(query, args)

    async def fetchrow(self, query, *args):
        rows = self._match(query, args)
        return rows[0] if rows else None

    async def fetchval(self, query, *args):
        rows = self._match(query, args)
        if rows:
            first = rows[0]
            return list(first.values())[0] if first else None
        return None

    async def execute(self, query, *args):
        self._queries.append(query)

    def _match(self, query, args):
        """Very simple query pattern matching for test scenarios."""
        ql = query.lower().strip()
        if "select 1" in ql:
            return [FakeRow({"?column?": 1})]
        # Return empty by default; specific tests override via fixtures.
        return []


class FakePool:
    """Minimal asyncpg.Pool stand-in that yields FakeConnection instances."""

    def __init__(self, tables=None):
        self.tables = tables or {}
        self._conn = FakeConnection(self.tables)

    def acquire(self):
        return _FakeAcquireCtx(self._conn)

    @property
    def connection(self):
        return self._conn


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


# ---------------------------------------------------------------------------
# In-memory Redis stub
# ---------------------------------------------------------------------------


class FakeRedis:
    """In-memory Redis client stub with basic operations."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._sets: Dict[str, set] = {}
        self._lists: Dict[str, list] = {}
        self._pubsub_messages: list = []

    # String ops
    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ex=None):
        self._store[key] = value

    def setex(self, key, ttl, value):
        self._store[key] = value

    def delete(self, key):
        self._store.pop(key, None)

    def exists(self, key):
        return key in self._store

    # Set ops
    def sadd(self, key, *values):
        s = self._sets.setdefault(key, set())
        s.update(values)

    def smembers(self, key):
        return self._sets.get(key, set())

    def expire(self, key, ttl):
        pass

    # List ops
    def lpush(self, key, *values):
        lst = self._lists.setdefault(key, [])
        for v in values:
            lst.insert(0, v)

    def rpop(self, key):
        lst = self._lists.get(key, [])
        return lst.pop() if lst else None

    def lrange(self, key, start, end):
        lst = self._lists.get(key, [])
        return lst[start : end + 1 if end >= 0 else None]

    def llen(self, key):
        return len(self._lists.get(key, []))

    # Pub/sub
    def pubsub(self):
        return FakePubSub(self)

    def publish(self, channel, message):
        self._pubsub_messages.append({"channel": channel, "data": message})


class FakePubSub:
    def __init__(self, redis):
        self._redis = redis

    def psubscribe(self, *patterns):
        pass

    def subscribe(self, *channels):
        pass

    def listen(self):
        for msg in self._redis._pubsub_messages:
            yield {"type": "pmessage", "data": msg["data"]}


# ---------------------------------------------------------------------------
# Test data factories
# ---------------------------------------------------------------------------


def make_signal(
    strategy_name="momentum_btc",
    instrument="BTC/USD",
    direction="BUY",
    confidence=0.85,
    entry_price=65000,
    stop_loss=63000,
    take_profit=70000,
    **overrides,
):
    """Create a realistic trade signal dict."""
    signal = {
        "signal_id": str(uuid.uuid4()),
        "strategy_name": strategy_name,
        "instrument": instrument,
        "direction": direction,
        "confidence": confidence,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    signal.update(overrides)
    return signal


def make_subscription(
    channel="telegram",
    endpoint="12345",
    strategies=None,
    pairs=None,
    active=True,
):
    """Create a subscription row."""
    return FakeRow(
        id=str(uuid.uuid4()),
        channel=channel,
        endpoint=endpoint,
        strategies=strategies,
        pairs=pairs,
        active=active,
    )


def make_candles(
    n=30,
    base_price=100.0,
    trend="up",
    volatility=0.02,
    base_volume=1000.0,
):
    """Generate synthetic OHLCV candle data for testing.

    Args:
        n: Number of candles.
        base_price: Starting close price.
        trend: 'up', 'down', or 'flat'.
        volatility: Per-candle return standard deviation.
        base_volume: Average volume.
    """
    import random

    random.seed(42)
    candles = []
    price = base_price
    for i in range(n):
        if trend == "up":
            drift = volatility * 0.5
        elif trend == "down":
            drift = -volatility * 0.5
        else:
            drift = 0
        ret = drift + random.gauss(0, volatility)
        price *= 1 + ret
        high = price * (1 + abs(random.gauss(0, volatility * 0.5)))
        low = price * (1 - abs(random.gauss(0, volatility * 0.5)))
        vol = base_volume * (1 + random.gauss(0, 0.3))
        candles.append(
            {
                "open": round(price / (1 + ret), 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(price, 2),
                "volume": round(max(0, vol), 2),
            }
        )
    return candles


def make_strategy_performance(
    strategy_spec_id="strat-001",
    sharpe_ratio=1.5,
    win_rate=0.6,
    avg_pnl_percent=2.0,
    trade_count=20,
    **overrides,
):
    """Create a strategy performance dict for weight optimization."""
    perf = {
        "strategy_spec_id": strategy_spec_id,
        "sharpe_ratio": sharpe_ratio,
        "win_rate": win_rate,
        "avg_pnl_percent": avg_pnl_percent,
        "trade_count": trade_count,
    }
    perf.update(overrides)
    return perf


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_redis():
    """Provide a fresh FakeRedis instance."""
    return FakeRedis()


@pytest.fixture
def fake_pool():
    """Provide a fresh FakePool instance."""
    return FakePool()


@pytest.fixture
def sample_signal():
    """Provide a default BUY signal for BTC/USD."""
    return make_signal()


@pytest.fixture
def sample_candles_uptrend():
    """Provide 30 candles with a clear upward trend."""
    return make_candles(n=30, trend="up", volatility=0.02)


@pytest.fixture
def sample_candles_downtrend():
    """Provide 30 candles with a clear downward trend."""
    return make_candles(n=30, trend="down", volatility=0.02)


@pytest.fixture
def sample_candles_volatile():
    """Provide 30 candles with high volatility and no trend."""
    return make_candles(n=30, trend="flat", volatility=0.06)
