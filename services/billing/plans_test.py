"""Tests for subscription plan definitions."""

import pytest

from services.billing.plans import (
    ENTERPRISE_PLAN,
    FREE_PLAN,
    PLANS,
    PRO_PLAN,
    get_plan,
    plan_to_dict,
)


class TestPlanDefinitions:
    def test_free_plan_limits(self):
        assert FREE_PLAN.signals_per_day == 3
        assert FREE_PLAN.realtime is False
        assert FREE_PLAN.api_access is False
        assert FREE_PLAN.price_cents == 0

    def test_pro_plan_features(self):
        assert PRO_PLAN.signals_per_day is None
        assert PRO_PLAN.realtime is True
        assert PRO_PLAN.api_access is False
        assert PRO_PLAN.price_cents == 2900

    def test_enterprise_plan_features(self):
        assert ENTERPRISE_PLAN.signals_per_day is None
        assert ENTERPRISE_PLAN.realtime is True
        assert ENTERPRISE_PLAN.api_access is True
        assert ENTERPRISE_PLAN.priority_signals is True
        assert ENTERPRISE_PLAN.price_cents == 9900

    def test_all_plans_registered(self):
        assert set(PLANS.keys()) == {"free", "pro", "enterprise"}


class TestGetPlan:
    def test_get_known_tier(self):
        assert get_plan("pro") == PRO_PLAN

    def test_get_unknown_tier_returns_free(self):
        assert get_plan("nonexistent") == FREE_PLAN


class TestPlanToDict:
    def test_conversion(self):
        d = plan_to_dict(PRO_PLAN)
        assert d["tier"] == "pro"
        assert d["price_monthly"] == 29.0
        assert d["signals_per_day"] is None
        assert d["realtime_signals"] is True

    def test_free_plan_conversion(self):
        d = plan_to_dict(FREE_PLAN)
        assert d["price_monthly"] == 0.0
        assert d["signals_per_day"] == 3
