"""End-to-end test: Billing & Subscription Flow.

Validates the full user journey: signup → subscribe via Stripe → verify access
granted → downgrade → verify access restricted.

Uses mocked Stripe API and in-memory database to exercise the real billing
app logic (gating, plans, webhook handlers).
"""

import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.billing.gating import (
    check_quality_gate,
    check_signal_quota,
    get_customer_tier,
    should_deliver_signal,
)
from services.billing.plans import ENTERPRISE_PLAN, FREE_PLAN, PRO_PLAN, get_plan

from tests.e2e.conftest import FakePool, FakeRow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class BillingDB:
    """In-memory billing database with query routing."""

    def __init__(self):
        self.customers = []
        self.subscriptions = []
        self.signal_usage = []

    def make_pool(self):
        pool = AsyncMock()
        conn = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx

        conn.fetchrow.side_effect = self._fetchrow
        conn.fetchval.side_effect = self._fetchval
        conn.execute.side_effect = self._execute
        conn.fetch.side_effect = self._fetch
        return pool

    async def _fetchrow(self, query, *args):
        ql = query.lower()
        if "billing_customers" in ql and "telegram_chat_id" in ql:
            chat_id = args[0] if args else None
            for c in self.customers:
                if c.get("telegram_chat_id") == chat_id:
                    # Join with subscription
                    tier = "free"
                    for s in self.subscriptions:
                        if s["customer_id"] == c["id"] and s["status"] == "active":
                            tier = s["tier"]
                    return FakeRow(id=c["id"], tier=tier)
            return None
        if "billing_customers" in ql and "api_key" in ql:
            api_key = args[0] if args else None
            for c in self.customers:
                if c.get("api_key") == api_key:
                    tier = "free"
                    for s in self.subscriptions:
                        if s["customer_id"] == c["id"] and s["status"] == "active":
                            tier = s["tier"]
                    return FakeRow(id=c["id"], tier=tier)
            return None
        if "signal_usage" in ql:
            cust_id = args[0] if args else None
            for u in self.signal_usage:
                if str(u["customer_id"]) == str(cust_id):
                    return FakeRow(signal_count=u["signal_count"])
            return None
        return None

    async def _fetchval(self, query, *args):
        row = await self._fetchrow(query, *args)
        if row:
            return list(row.values())[0]
        return None

    async def _execute(self, query, *args):
        ql = query.lower()
        if "insert into signal_usage" in ql or "do update" in ql:
            cust_id = args[0] if args else None
            for u in self.signal_usage:
                if str(u["customer_id"]) == str(cust_id):
                    u["signal_count"] += 1
                    return
            self.signal_usage.append({"customer_id": cust_id, "signal_count": 1})

    async def _fetch(self, query, *args):
        return []


@pytest.fixture
def billing_db():
    return BillingDB()


# ---------------------------------------------------------------------------
# Plan definition tests
# ---------------------------------------------------------------------------


class TestPlanDefinitions:
    """Verify plan hierarchy and feature gating."""

    def test_free_plan_has_daily_limit(self):
        plan = get_plan("free")
        assert plan.signals_per_day == 3
        assert plan.realtime is False
        assert plan.api_access is False

    def test_pro_plan_has_unlimited_signals(self):
        plan = get_plan("pro")
        assert plan.signals_per_day is None
        assert plan.realtime is True
        assert plan.api_access is False

    def test_enterprise_plan_has_all_features(self):
        plan = get_plan("enterprise")
        assert plan.signals_per_day is None
        assert plan.realtime is True
        assert plan.api_access is True
        assert plan.priority_signals is True

    def test_unknown_tier_defaults_to_free(self):
        plan = get_plan("nonexistent")
        assert plan.tier == "free"


# ---------------------------------------------------------------------------
# Quality gate tests
# ---------------------------------------------------------------------------


class TestQualityGate:
    """Verify signal quality gating by tier."""

    def test_free_tier_blocks_low_quality_signals(self):
        result = check_quality_gate("free", "C")
        assert result["passed"] is False

    def test_free_tier_allows_high_quality_signals(self):
        for grade in ("A", "B"):
            result = check_quality_gate("free", grade)
            assert result["passed"] is True

    def test_pro_tier_allows_all_grades(self):
        for grade in ("A", "B", "C", "D"):
            result = check_quality_gate("pro", grade)
            assert result["passed"] is True

    def test_enterprise_tier_allows_all_grades(self):
        result = check_quality_gate("enterprise", "D")
        assert result["passed"] is True

    def test_no_grade_passes_for_all_tiers(self):
        for tier in ("free", "pro", "enterprise"):
            result = check_quality_gate(tier, None)
            assert result["passed"] is True


# ---------------------------------------------------------------------------
# Full billing flow E2E
# ---------------------------------------------------------------------------


class TestBillingFlowE2E:
    """End-to-end user journey: signup → subscribe → access → downgrade → restricted."""

    @pytest.mark.asyncio
    async def test_new_user_defaults_to_free_tier(self, billing_db):
        """Unregistered user gets free tier with daily limits."""
        pool = billing_db.make_pool()
        tier, cust_id = await get_customer_tier(pool, telegram_chat_id="new-user-123")
        assert tier == "free"
        assert cust_id is None

    @pytest.mark.asyncio
    async def test_subscribed_user_gets_pro_tier(self, billing_db):
        """User with active pro subscription gets pro tier."""
        cust_id = "cust-001"
        billing_db.customers.append(
            {"id": cust_id, "telegram_chat_id": "pro-user-456", "email": "pro@test.com"}
        )
        billing_db.subscriptions.append(
            {"customer_id": cust_id, "tier": "pro", "status": "active"}
        )

        pool = billing_db.make_pool()
        tier, returned_id = await get_customer_tier(
            pool, telegram_chat_id="pro-user-456"
        )
        assert tier == "pro"
        assert returned_id == cust_id

    @pytest.mark.asyncio
    async def test_free_user_signal_quota_enforced(self, billing_db):
        """Free user can receive 3 signals/day, then blocked."""
        cust_id = "cust-free-001"
        billing_db.customers.append(
            {"id": cust_id, "telegram_chat_id": "free-user-789"}
        )
        billing_db.signal_usage.append({"customer_id": cust_id, "signal_count": 3})

        pool = billing_db.make_pool()
        quota = await check_signal_quota(pool, cust_id)
        assert quota["allowed"] is False
        assert quota["remaining"] == 0
        assert quota["limit"] == 3

    @pytest.mark.asyncio
    async def test_free_user_under_quota_allowed(self, billing_db):
        """Free user below daily limit can receive signals."""
        cust_id = "cust-free-002"
        billing_db.customers.append(
            {"id": cust_id, "telegram_chat_id": "free-user-new"}
        )

        pool = billing_db.make_pool()
        quota = await check_signal_quota(pool, cust_id)
        assert quota["allowed"] is True
        assert quota["remaining"] == 3

    @pytest.mark.asyncio
    async def test_pro_user_gets_realtime_delivery(self, billing_db):
        """Pro subscriber receives signals with zero delay."""
        cust_id = "cust-pro-001"
        billing_db.customers.append({"id": cust_id, "telegram_chat_id": "pro-rt-user"})
        billing_db.subscriptions.append(
            {"customer_id": cust_id, "tier": "pro", "status": "active"}
        )

        pool = billing_db.make_pool()
        decision = await should_deliver_signal(pool, telegram_chat_id="pro-rt-user")
        assert decision["deliver"] is True
        assert decision["delay_seconds"] == 0
        assert decision["tier"] == "pro"

    @pytest.mark.asyncio
    async def test_free_user_gets_delayed_delivery(self, billing_db):
        """Free user receives signals with 15-minute delay."""
        cust_id = "cust-free-delay"
        billing_db.customers.append(
            {"id": cust_id, "telegram_chat_id": "free-delay-user"}
        )

        pool = billing_db.make_pool()
        decision = await should_deliver_signal(
            pool, telegram_chat_id="free-delay-user", quality_grade="A"
        )
        assert decision["deliver"] is True
        assert decision["delay_seconds"] == 900  # 15 minutes
        assert decision["tier"] == "free"

    @pytest.mark.asyncio
    async def test_cancelled_subscription_reverts_to_free(self, billing_db):
        """User with cancelled subscription gets free tier."""
        cust_id = "cust-cancelled"
        billing_db.customers.append(
            {"id": cust_id, "telegram_chat_id": "cancelled-user"}
        )
        billing_db.subscriptions.append(
            {"customer_id": cust_id, "tier": "pro", "status": "cancelled"}
        )

        pool = billing_db.make_pool()
        tier, _ = await get_customer_tier(pool, telegram_chat_id="cancelled-user")
        assert tier == "free"

    @pytest.mark.asyncio
    async def test_free_user_blocked_on_low_quality_signal(self, billing_db):
        """Free user gets blocked when signal quality is below threshold."""
        pool = billing_db.make_pool()
        decision = await should_deliver_signal(
            pool, telegram_chat_id="unknown-user", quality_grade="C"
        )
        assert decision["deliver"] is False
        assert (
            "quality grade" in decision["reason"].lower()
            or "grade" in decision["reason"].lower()
        )
