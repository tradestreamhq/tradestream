"""
Signal delivery gating based on subscription tier.

Free users: 3 signals/day, delayed by 15 minutes, only A/B grade signals.
Pro users: unlimited real-time signals (all grades).
Enterprise users: unlimited real-time + API access + priority delivery.
"""

import logging
from datetime import date
from typing import Dict, Optional, Tuple

import asyncpg

from services.billing.plans import FREE_PLAN, get_plan

logger = logging.getLogger(__name__)

SIGNAL_DELAY_SECONDS_FREE = 900  # 15 minutes

# Free tier only receives high-quality signals
FREE_TIER_MIN_GRADES = {"A", "B"}


async def get_customer_tier(
    db_pool: asyncpg.Pool, telegram_chat_id: str = None, api_key: str = None
) -> Tuple[str, Optional[str]]:
    """Look up a customer's subscription tier.

    Returns (tier, customer_id) tuple. Defaults to 'free' if not found.
    """
    async with db_pool.acquire() as conn:
        row = None
        if telegram_chat_id:
            row = await conn.fetchrow(
                """SELECT c.id, COALESCE(s.tier, 'free') AS tier
                   FROM billing_customers c
                   LEFT JOIN billing_subscriptions s
                     ON s.customer_id = c.id AND s.status = 'active'
                   WHERE c.telegram_chat_id = $1""",
                telegram_chat_id,
            )
        elif api_key:
            row = await conn.fetchrow(
                """SELECT c.id, COALESCE(s.tier, 'free') AS tier
                   FROM billing_customers c
                   LEFT JOIN billing_subscriptions s
                     ON s.customer_id = c.id AND s.status = 'active'
                   WHERE c.api_key = $1""",
                api_key,
            )

        if row:
            return row["tier"], str(row["id"])
        return "free", None


async def check_signal_quota(db_pool: asyncpg.Pool, customer_id: str) -> Dict:
    """Check whether a customer can receive another signal today.

    Returns dict with 'allowed', 'remaining', 'limit' keys.
    """
    plan = FREE_PLAN  # only free has limits
    limit = plan.signals_per_day
    if limit is None:
        return {"allowed": True, "remaining": None, "limit": None}

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT signal_count FROM signal_usage
               WHERE customer_id = $1::uuid AND signal_date = $2""",
            customer_id,
            date.today(),
        )
        current = row["signal_count"] if row else 0

    remaining = max(0, limit - current)
    return {
        "allowed": current < limit,
        "remaining": remaining,
        "limit": limit,
    }


async def record_signal_delivery(db_pool: asyncpg.Pool, customer_id: str) -> None:
    """Increment the daily signal counter for a customer."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO signal_usage (customer_id, signal_date, signal_count)
               VALUES ($1::uuid, CURRENT_DATE, 1)
               ON CONFLICT (customer_id, signal_date)
               DO UPDATE SET signal_count = signal_usage.signal_count + 1""",
            customer_id,
        )


def check_quality_gate(tier: str, quality_grade: str = None) -> Dict:
    """Check whether a signal's quality grade passes the tier's quality gate.

    Free tier only receives A/B grade signals.
    Pro and Enterprise receive all grades.
    """
    if tier in ("pro", "enterprise"):
        return {"passed": True, "reason": None}

    if quality_grade is None:
        return {"passed": True, "reason": None}

    if quality_grade not in FREE_TIER_MIN_GRADES:
        return {
            "passed": False,
            "reason": (
                f"Signal quality grade '{quality_grade}' below free tier minimum (A/B required). "
                "Upgrade to Pro for all signal grades."
            ),
        }

    return {"passed": True, "reason": None}


async def should_deliver_signal(
    db_pool: asyncpg.Pool,
    telegram_chat_id: str = None,
    api_key: str = None,
    quality_grade: str = None,
) -> Dict:
    """Determine if a signal should be delivered and how.

    Returns:
        {
            'deliver': bool,
            'tier': str,
            'delay_seconds': int,  # 0 for real-time
            'reason': str or None,
        }
    """
    tier, customer_id = await get_customer_tier(
        db_pool, telegram_chat_id=telegram_chat_id, api_key=api_key
    )
    plan = get_plan(tier)

    # Enterprise and Pro get immediate delivery
    if plan.realtime:
        return {
            "deliver": True,
            "tier": tier,
            "delay_seconds": 0,
            "reason": None,
        }

    # Free tier: check quality gate
    quality_check = check_quality_gate(tier, quality_grade)
    if not quality_check["passed"]:
        return {
            "deliver": False,
            "tier": tier,
            "delay_seconds": 0,
            "reason": quality_check["reason"],
        }

    # Free tier: check quota
    if customer_id:
        quota = await check_signal_quota(db_pool, customer_id)
        if not quota["allowed"]:
            return {
                "deliver": False,
                "tier": tier,
                "delay_seconds": 0,
                "reason": f"Daily signal limit reached ({quota['limit']}/day). Upgrade to Pro for unlimited signals.",
            }
        # Record usage
        await record_signal_delivery(db_pool, customer_id)

    return {
        "deliver": True,
        "tier": tier,
        "delay_seconds": SIGNAL_DELAY_SECONDS_FREE,
        "reason": "Free tier signals are delayed by 15 minutes. Upgrade to Pro for real-time delivery.",
    }
