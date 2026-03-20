"""Tests for signal delivery gating logic."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from services.billing.gating import (
    FREE_TIER_MIN_GRADES,
    SIGNAL_DELAY_SECONDS_FREE,
    check_quality_gate,
    check_signal_quota,
    get_customer_tier,
    record_signal_delivery,
    should_deliver_signal,
)


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)


def _make_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx
    return pool, conn


@pytest.mark.asyncio
class TestGetCustomerTier:
    async def test_known_telegram_customer(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(id="cust-123", tier="pro")

        tier, cust_id = await get_customer_tier(pool, telegram_chat_id="12345")
        assert tier == "pro"
        assert cust_id == "cust-123"

    async def test_unknown_customer_returns_free(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None

        tier, cust_id = await get_customer_tier(pool, telegram_chat_id="unknown")
        assert tier == "free"
        assert cust_id is None

    async def test_api_key_lookup(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(id="cust-456", tier="enterprise")

        tier, cust_id = await get_customer_tier(pool, api_key="sk-test-key")
        assert tier == "enterprise"

    async def test_no_identifiers_returns_free(self):
        pool, conn = _make_pool()
        tier, cust_id = await get_customer_tier(pool)
        assert tier == "free"
        assert cust_id is None


@pytest.mark.asyncio
class TestCheckSignalQuota:
    async def test_under_limit(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(signal_count=1)

        result = await check_signal_quota(pool, "cust-123")
        assert result["allowed"] is True
        assert result["remaining"] == 2
        assert result["limit"] == 3

    async def test_at_limit(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(signal_count=3)

        result = await check_signal_quota(pool, "cust-123")
        assert result["allowed"] is False
        assert result["remaining"] == 0

    async def test_no_usage_record(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None

        result = await check_signal_quota(pool, "cust-123")
        assert result["allowed"] is True
        assert result["remaining"] == 3


@pytest.mark.asyncio
class TestShouldDeliverSignal:
    async def test_pro_user_gets_realtime(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(id="cust-1", tier="pro")

        result = await should_deliver_signal(pool, telegram_chat_id="12345")
        assert result["deliver"] is True
        assert result["delay_seconds"] == 0
        assert result["tier"] == "pro"

    async def test_enterprise_gets_realtime(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(id="cust-2", tier="enterprise")

        result = await should_deliver_signal(pool, api_key="sk-ent")
        assert result["deliver"] is True
        assert result["delay_seconds"] == 0

    async def test_free_user_gets_delayed(self):
        pool, conn = _make_pool()
        # First call: get_customer_tier returns free with a customer_id
        # Second call: check_signal_quota returns under-limit
        conn.fetchrow.side_effect = [
            FakeRecord(id="cust-free", tier="free"),  # get_customer_tier
            FakeRecord(signal_count=1),  # check_signal_quota
        ]

        result = await should_deliver_signal(pool, telegram_chat_id="99999")
        assert result["deliver"] is True
        assert result["delay_seconds"] == SIGNAL_DELAY_SECONDS_FREE
        assert "delayed" in result["reason"]

    async def test_free_user_over_quota_blocked(self):
        pool, conn = _make_pool()
        conn.fetchrow.side_effect = [
            FakeRecord(id="cust-free", tier="free"),
            FakeRecord(signal_count=3),
        ]

        result = await should_deliver_signal(pool, telegram_chat_id="99999")
        assert result["deliver"] is False
        assert "limit reached" in result["reason"]

    async def test_unknown_user_gets_delayed(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None  # no customer record

        result = await should_deliver_signal(pool, telegram_chat_id="new-user")
        assert result["deliver"] is True
        assert result["delay_seconds"] == SIGNAL_DELAY_SECONDS_FREE
        assert result["tier"] == "free"

    async def test_free_user_low_quality_blocked(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None  # no customer record

        result = await should_deliver_signal(
            pool, telegram_chat_id="free-user", quality_grade="D"
        )
        assert result["deliver"] is False
        assert "quality grade" in result["reason"]

    async def test_free_user_high_quality_allowed(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = None  # no customer record

        result = await should_deliver_signal(
            pool, telegram_chat_id="free-user", quality_grade="A"
        )
        assert result["deliver"] is True

    async def test_pro_user_low_quality_allowed(self):
        pool, conn = _make_pool()
        conn.fetchrow.return_value = FakeRecord(id="cust-pro", tier="pro")

        result = await should_deliver_signal(
            pool, telegram_chat_id="pro-user", quality_grade="D"
        )
        assert result["deliver"] is True
        assert result["delay_seconds"] == 0


class TestCheckQualityGate:
    def test_pro_passes_all_grades(self):
        for grade in ("A", "B", "C", "D", "F"):
            result = check_quality_gate("pro", grade)
            assert result["passed"] is True

    def test_enterprise_passes_all_grades(self):
        result = check_quality_gate("enterprise", "F")
        assert result["passed"] is True

    def test_free_passes_a_grade(self):
        result = check_quality_gate("free", "A")
        assert result["passed"] is True

    def test_free_passes_b_grade(self):
        result = check_quality_gate("free", "B")
        assert result["passed"] is True

    def test_free_blocks_c_grade(self):
        result = check_quality_gate("free", "C")
        assert result["passed"] is False
        assert "quality grade" in result["reason"]

    def test_free_blocks_d_grade(self):
        result = check_quality_gate("free", "D")
        assert result["passed"] is False

    def test_free_blocks_f_grade(self):
        result = check_quality_gate("free", "F")
        assert result["passed"] is False

    def test_none_grade_passes(self):
        result = check_quality_gate("free", None)
        assert result["passed"] is True
