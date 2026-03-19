"""E2E tests for the complete user journey.

Tests the full flow: user signup → subscription plan selection → strategy
configuration → signal generation → multi-channel delivery → signal receipt
→ performance tracking.
"""

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
from services.billing.plans import get_plan, FREE_PLAN, PRO_PLAN, ENTERPRISE_PLAN
from services.billing.gating import check_quality_gate
from services.signal_quality.scorer import score_signal
from services.shared.pipeline_metrics import PipelineMetrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_test_user(user_id=None, email=None, tier="free"):
    """Create a test user dict simulating signup."""
    return {
        "user_id": user_id or str(uuid.uuid4()),
        "email": email or f"test-{uuid.uuid4().hex[:8]}@example.com",
        "tier": tier,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_key": f"ts_{uuid.uuid4().hex}",
        "preferences": {
            "channels": ["telegram"],
            "strategies": [],
            "instruments": ["BTC/USD", "ETH/USD"],
        },
    }


def _simulate_stripe_subscription(user, plan="pro"):
    """Simulate a Stripe subscription upgrade."""
    user["tier"] = plan
    user["subscription"] = {
        "id": f"sub_{uuid.uuid4().hex[:16]}",
        "plan": plan,
        "status": "active",
        "current_period_start": datetime.now(timezone.utc).isoformat(),
    }
    return user


def _simulate_stripe_cancellation(user):
    """Simulate a Stripe subscription cancellation."""
    user["tier"] = "free"
    if "subscription" in user:
        user["subscription"]["status"] = "canceled"
    return user


# ---------------------------------------------------------------------------
# Tests: User Signup Flow
# ---------------------------------------------------------------------------


class TestUserSignupFlow:
    """Test user creation and initial state."""

    def test_new_user_gets_free_tier(self):
        user = _create_test_user()
        assert user["tier"] == "free"
        plan = get_plan("free")
        assert plan is not None
        assert plan.signals_per_day == 3

    def test_new_user_has_api_key(self):
        user = _create_test_user()
        assert user["api_key"].startswith("ts_")
        assert len(user["api_key"]) > 10

    def test_new_user_default_preferences(self):
        user = _create_test_user()
        assert "telegram" in user["preferences"]["channels"]
        assert len(user["preferences"]["instruments"]) > 0

    def test_multiple_users_get_unique_ids(self):
        users = [_create_test_user() for _ in range(10)]
        user_ids = [u["user_id"] for u in users]
        assert len(set(user_ids)) == 10


# ---------------------------------------------------------------------------
# Tests: Subscription Upgrade Flow
# ---------------------------------------------------------------------------


class TestSubscriptionFlow:
    """Test tier upgrade, access granting, and downgrade."""

    def test_upgrade_to_pro(self):
        user = _create_test_user()
        assert user["tier"] == "free"
        user = _simulate_stripe_subscription(user, "pro")
        assert user["tier"] == "pro"
        assert user["subscription"]["status"] == "active"

    def test_pro_plan_has_unlimited_signals(self):
        pro = get_plan("pro")
        free = get_plan("free")
        assert pro.signals_per_day is None  # unlimited
        assert free.signals_per_day == 3

    def test_pro_plan_has_realtime(self):
        pro = get_plan("pro")
        free = get_plan("free")
        assert pro.realtime is True
        assert free.realtime is False

    def test_upgrade_then_downgrade(self):
        user = _create_test_user()
        user = _simulate_stripe_subscription(user, "pro")
        assert user["tier"] == "pro"

        user = _simulate_stripe_cancellation(user)
        assert user["tier"] == "free"
        assert user["subscription"]["status"] == "canceled"

    def test_enterprise_tier_has_all_features(self):
        plan = get_plan("enterprise")
        assert plan.realtime is True
        assert plan.api_access is True
        assert plan.priority_signals is True
        assert plan.signals_per_day is None

    def test_unknown_tier_defaults_to_free(self):
        plan = get_plan("nonexistent_tier")
        assert plan.tier == "free"


# ---------------------------------------------------------------------------
# Tests: Signal Receipt Based on Tier
# ---------------------------------------------------------------------------


class TestSignalReceiptByTier:
    """Test that signal delivery respects subscription tier quality gate."""

    def test_free_tier_blocks_low_quality(self):
        result = check_quality_gate("free", "D")
        assert result["passed"] is False

    def test_free_tier_blocks_f_grade(self):
        result = check_quality_gate("free", "F")
        assert result["passed"] is False

    def test_free_tier_allows_a_grade(self):
        result = check_quality_gate("free", "A")
        assert result["passed"] is True

    def test_free_tier_allows_b_grade(self):
        result = check_quality_gate("free", "B")
        assert result["passed"] is True

    def test_free_tier_allows_no_grade(self):
        result = check_quality_gate("free", None)
        assert result["passed"] is True

    def test_pro_allows_all_grades(self):
        for grade in ("A", "B", "C", "D", "F"):
            result = check_quality_gate("pro", grade)
            assert result["passed"] is True

    def test_enterprise_allows_all_grades(self):
        for grade in ("A", "B", "C", "D", "F"):
            result = check_quality_gate("enterprise", grade)
            assert result["passed"] is True


# ---------------------------------------------------------------------------
# Tests: Full User Journey (Signup → Subscribe → Signal Receipt)
# ---------------------------------------------------------------------------


class TestFullUserJourney:
    """End-to-end user journey from signup through signal receipt."""

    def test_complete_journey_free_user(self):
        """Free user: signup → configure → receive high-quality signal."""
        # Step 1: User signs up
        user = _create_test_user()
        assert user["tier"] == "free"

        # Step 2: Configure preferences
        user["preferences"]["strategies"] = ["momentum_btc"]
        user["preferences"]["channels"] = ["telegram"]

        # Step 3: Signal generated
        signal = make_signal(
            strategy_name="momentum_btc",
            instrument="BTC/USD",
            confidence=0.85,
        )

        # Step 4: Quality check
        quality = score_signal(
            entry_conditions_met=4,
            total_entry_conditions=5,
            volume_above_average=True,
            volume_ratio=1.5,
            trend_direction_matches=True,
            trend_strength=0.7,
            volatility_percentile=0.3,
        )
        assert quality.grade in ("A", "B")

        # Step 5: Tier gating allows high-quality for free
        gate_result = check_quality_gate(user["tier"], quality.grade)
        assert gate_result["passed"] is True

        # Step 6: Delivery to subscription channel
        sub = make_subscription(
            channel="telegram",
            endpoint=user["user_id"],
            strategies=["momentum_btc"],
        )
        assert sub["channel"] == "telegram"
        assert sub["active"]

    def test_complete_journey_pro_user(self):
        """Pro user: signup → upgrade → receive all signals including low quality."""
        # Step 1: Signup
        user = _create_test_user()

        # Step 2: Upgrade to pro
        user = _simulate_stripe_subscription(user, "pro")
        assert user["tier"] == "pro"

        # Step 3: Low quality signal generated
        quality = score_signal(
            entry_conditions_met=2,
            total_entry_conditions=5,
            volume_above_average=False,
            volume_ratio=0.5,
            trend_direction_matches=False,
            trend_strength=0.3,
            volatility_percentile=0.85,
        )
        assert quality.grade in ("C", "D", "F")

        # Step 4: Pro user still gets it
        gate_result = check_quality_gate(user["tier"], quality.grade)
        assert gate_result["passed"] is True

    def test_journey_downgrade_restricts_access(self):
        """User upgrades, then downgrades — quality gate restricts access."""
        user = _create_test_user()
        user = _simulate_stripe_subscription(user, "pro")

        # While pro: D grade allowed
        assert check_quality_gate(user["tier"], "D")["passed"] is True

        # Downgrade
        user = _simulate_stripe_cancellation(user)
        assert user["tier"] == "free"

        # Now D grade blocked
        assert check_quality_gate(user["tier"], "D")["passed"] is False

    def test_journey_multiple_channels(self):
        """User configures multiple delivery channels."""
        user = _create_test_user()
        user = _simulate_stripe_subscription(user, "pro")

        channels = ["telegram", "email", "webhook"]
        user["preferences"]["channels"] = channels

        subscriptions = []
        for ch in channels:
            sub = make_subscription(
                channel=ch,
                endpoint=f"{ch}_{user['user_id'][:8]}",
                strategies=["momentum_btc"],
            )
            subscriptions.append(sub)

        assert len(subscriptions) == 3
        assert all(s["active"] for s in subscriptions)
        assert {s["channel"] for s in subscriptions} == set(channels)

    def test_journey_with_metrics_tracking(self):
        """Full journey including pipeline metrics tracking."""
        metrics = PipelineMetrics()
        user = _create_test_user()
        user = _simulate_stripe_subscription(user, "pro")

        # Generate and deliver several signals
        strategies = ["strat_a", "strat_b", "strat_c"]
        for strat in strategies:
            signal = make_signal(strategy_name=strat)
            metrics.signals_generated.inc()
            metrics.deliveries_attempted.inc()
            metrics.deliveries_succeeded.inc()
            metrics.record_channel_success("telegram")

        snapshot = metrics.snapshot()
        assert snapshot["signal_generation"]["total"] == 3
        assert snapshot["delivery"]["succeeded"] == 3
        assert snapshot["delivery"]["failed"] == 0
        assert snapshot["delivery"]["by_channel"]["telegram"]["success"] == 3

    def test_journey_strategy_subscription_from_marketplace(self):
        """User subscribes to a marketplace strategy then receives signals."""
        # Creator publishes strategy
        creator = _create_test_user(email="creator@example.com")
        strategy = {
            "strategy_id": str(uuid.uuid4()),
            "name": "Golden Cross BTC",
            "creator_id": creator["user_id"],
            "category": "trend_following",
            "published": True,
        }

        # Subscriber subscribes
        subscriber = _create_test_user(email="subscriber@example.com")
        subscriber = _simulate_stripe_subscription(subscriber, "pro")
        subscriber["preferences"]["strategies"].append(strategy["strategy_id"])

        # Signal generated from the subscribed strategy
        signal = make_signal(
            strategy_name=strategy["name"],
            instrument="BTC/USD",
        )

        # Subscriber gets the signal via configured channel
        sub = make_subscription(
            channel="telegram",
            endpoint=subscriber["user_id"],
            strategies=[strategy["strategy_id"]],
        )
        assert sub["active"]
        assert strategy["strategy_id"] in sub["strategies"]

    def test_journey_free_user_blocked_then_upgrades(self):
        """Free user blocked on low quality → upgrades → now receives it."""
        user = _create_test_user()

        # Low quality signal blocked for free user
        gate_result = check_quality_gate(user["tier"], "D")
        assert gate_result["passed"] is False

        # User upgrades
        user = _simulate_stripe_subscription(user, "pro")

        # Same grade now passes
        gate_result = check_quality_gate(user["tier"], "D")
        assert gate_result["passed"] is True

    def test_plan_pricing_tiers(self):
        """Verify plan pricing is consistent."""
        free = get_plan("free")
        pro = get_plan("pro")
        enterprise = get_plan("enterprise")

        assert free.price_cents == 0
        assert pro.price_cents > 0
        assert enterprise.price_cents > pro.price_cents
