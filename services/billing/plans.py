"""Subscription plan definitions for TradeStream Signal service."""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class Plan:
    tier: str
    name: str
    price_cents: int  # monthly price in cents
    signals_per_day: Optional[int]  # None = unlimited
    realtime: bool
    api_access: bool
    priority_signals: bool
    stripe_price_id_env: str  # env var name holding the Stripe Price ID


FREE_PLAN = Plan(
    tier="free",
    name="Free",
    price_cents=0,
    signals_per_day=3,
    realtime=False,
    api_access=False,
    priority_signals=False,
    stripe_price_id_env="",
)

PRO_PLAN = Plan(
    tier="pro",
    name="Pro",
    price_cents=2900,
    signals_per_day=None,
    realtime=True,
    api_access=False,
    priority_signals=False,
    stripe_price_id_env="STRIPE_PRO_PRICE_ID",
)

ENTERPRISE_PLAN = Plan(
    tier="enterprise",
    name="Enterprise",
    price_cents=9900,
    signals_per_day=None,
    realtime=True,
    api_access=True,
    priority_signals=True,
    stripe_price_id_env="STRIPE_ENTERPRISE_PRICE_ID",
)

PLANS: Dict[str, Plan] = {
    "free": FREE_PLAN,
    "pro": PRO_PLAN,
    "enterprise": ENTERPRISE_PLAN,
}


def get_plan(tier: str) -> Plan:
    return PLANS.get(tier, FREE_PLAN)


def plan_to_dict(plan: Plan) -> dict:
    return {
        "tier": plan.tier,
        "name": plan.name,
        "price_monthly": plan.price_cents / 100,
        "signals_per_day": plan.signals_per_day,
        "realtime_signals": plan.realtime,
        "api_access": plan.api_access,
        "priority_signals": plan.priority_signals,
    }
