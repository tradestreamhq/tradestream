"""
Beta User Onboarding API — Phase 4.

Manages invite codes, beta user registration, and onboarding flow:
1. REGISTERED - user redeems invite code
2. TELEGRAM_CONNECTED - user links Telegram
3. STRATEGY_SELECTED - user picks strategies/pairs
4. FIRST_SIGNAL - user receives first signal
5. COMPLETED - onboarding done
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import asyncpg
from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    error_response,
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


class RedeemInviteRequest(BaseModel):
    code: str = Field(..., description="Invite code to redeem")
    email: str = Field(..., description="User email address")


class ConnectTelegramRequest(BaseModel):
    telegram_chat_id: str = Field(..., description="Telegram chat ID")


class SelectStrategiesRequest(BaseModel):
    strategies: List[str] = Field(..., min_length=1, description="Strategy names")
    pairs: List[str] = Field(..., min_length=1, description="Trading pairs")


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    app = FastAPI(
        title="Beta Onboarding API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/beta",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("beta-onboarding-api", check_deps))

    # ------------------------------------------------------------------
    # Invite code redemption
    # ------------------------------------------------------------------

    @app.post("/redeem", tags=["Onboarding"])
    async def redeem_invite(body: RedeemInviteRequest):
        """Redeem an invite code to join the beta."""
        async with db_pool.acquire() as conn:
            # Validate invite code
            invite = await conn.fetchrow(
                """SELECT id, code, max_uses, current_uses, tier, expires_at, is_active
                   FROM invite_codes WHERE code = $1""",
                body.code,
            )
            if not invite:
                return not_found("Invite code", body.code)

            if not invite["is_active"]:
                return error_response("INACTIVE", "This invite code is no longer active", 410)

            if invite["current_uses"] >= invite["max_uses"]:
                return error_response("EXHAUSTED", "This invite code has been fully used", 410)

            if invite["expires_at"] and invite["expires_at"] < datetime.now(timezone.utc):
                return error_response("EXPIRED", "This invite code has expired", 410)

            # Check for existing beta user
            existing = await conn.fetchrow(
                "SELECT id FROM beta_users WHERE email = $1", body.email
            )
            if existing:
                return error_response(
                    "ALREADY_REGISTERED",
                    "This email is already registered for the beta",
                    409,
                )

            # Create billing customer
            customer_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO billing_customers (id, email)
                   VALUES ($1::uuid, $2)
                   ON CONFLICT (email) DO UPDATE SET email = $2
                   RETURNING id""",
                customer_id, body.email,
            )

            # Create subscription at the invite tier
            sub_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO billing_subscriptions
                   (id, customer_id, tier, status, current_period_start, current_period_end)
                   VALUES ($1::uuid, $2::uuid, $3, 'active', NOW(), NOW() + INTERVAL '90 days')""",
                sub_id, customer_id, invite["tier"],
            )

            # Create beta user
            beta_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO beta_users (id, customer_id, invite_code_id, email, onboarding_step)
                   VALUES ($1::uuid, $2::uuid, $3, $4, 'REGISTERED')""",
                beta_id, customer_id, str(invite["id"]), body.email,
            )

            # Increment invite usage
            await conn.execute(
                "UPDATE invite_codes SET current_uses = current_uses + 1 WHERE id = $1",
                invite["id"],
            )

        return success_response(
            {
                "beta_user_id": beta_id,
                "email": body.email,
                "tier": invite["tier"],
                "onboarding_step": "REGISTERED",
                "next_step": "Connect your Telegram account via POST /connect-telegram",
            },
            "beta_user",
            resource_id=beta_id,
            status_code=201,
        )

    # ------------------------------------------------------------------
    # Telegram connection
    # ------------------------------------------------------------------

    @app.post("/users/{beta_user_id}/connect-telegram", tags=["Onboarding"])
    async def connect_telegram(beta_user_id: str, body: ConnectTelegramRequest):
        """Link a Telegram account to the beta user."""
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id, customer_id, onboarding_step FROM beta_users WHERE id = $1::uuid",
                beta_user_id,
            )
            if not user:
                return not_found("Beta user", beta_user_id)

            await conn.execute(
                """UPDATE beta_users
                   SET telegram_chat_id = $1, onboarding_step = 'TELEGRAM_CONNECTED'
                   WHERE id = $2::uuid""",
                body.telegram_chat_id, beta_user_id,
            )

            # Update billing customer with telegram ID
            await conn.execute(
                "UPDATE billing_customers SET telegram_chat_id = $1 WHERE id = $2::uuid",
                body.telegram_chat_id, str(user["customer_id"]),
            )

        return success_response(
            {
                "beta_user_id": beta_user_id,
                "telegram_chat_id": body.telegram_chat_id,
                "onboarding_step": "TELEGRAM_CONNECTED",
                "next_step": "Select strategies and pairs via POST /select-strategies",
            },
            "beta_user",
            resource_id=beta_user_id,
        )

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    @app.post("/users/{beta_user_id}/select-strategies", tags=["Onboarding"])
    async def select_strategies(beta_user_id: str, body: SelectStrategiesRequest):
        """Select strategies and trading pairs for signal delivery."""
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT id, telegram_chat_id, customer_id FROM beta_users WHERE id = $1::uuid",
                beta_user_id,
            )
            if not user:
                return not_found("Beta user", beta_user_id)

            # Validate strategies exist
            valid = await conn.fetch(
                "SELECT name FROM strategy_specs WHERE name = ANY($1::text[])",
                body.strategies,
            )
            valid_names = {r["name"] for r in valid}
            invalid = [s for s in body.strategies if s not in valid_names]
            if invalid:
                return validation_error(
                    f"Unknown strategies: {', '.join(invalid)}"
                )

            await conn.execute(
                """UPDATE beta_users
                   SET strategies = $1, pairs = $2, onboarding_step = 'STRATEGY_SELECTED'
                   WHERE id = $3::uuid""",
                body.strategies, body.pairs, beta_user_id,
            )

            # Auto-create signal subscription if telegram is connected
            if user["telegram_chat_id"]:
                sub_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO signal_subscriptions
                       (id, channel, endpoint, strategies, pairs, active, created_at)
                       VALUES ($1, 'telegram', $2, $3, $4, true, NOW())
                       ON CONFLICT DO NOTHING""",
                    sub_id, user["telegram_chat_id"],
                    body.strategies, body.pairs,
                )

        return success_response(
            {
                "beta_user_id": beta_user_id,
                "strategies": body.strategies,
                "pairs": body.pairs,
                "onboarding_step": "STRATEGY_SELECTED",
                "next_step": "You will receive your first signal soon!",
            },
            "beta_user",
            resource_id=beta_user_id,
        )

    # ------------------------------------------------------------------
    # Onboarding status
    # ------------------------------------------------------------------

    @app.get("/users/{beta_user_id}", tags=["Onboarding"])
    async def get_user_status(beta_user_id: str):
        """Get current onboarding status for a beta user."""
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """SELECT bu.id, bu.email, bu.telegram_chat_id, bu.onboarding_step,
                          bu.strategies, bu.pairs, bu.welcomed_at, bu.completed_at,
                          bu.created_at, ic.code AS invite_code, bs.tier
                   FROM beta_users bu
                   LEFT JOIN invite_codes ic ON ic.id = bu.invite_code_id
                   LEFT JOIN billing_subscriptions bs
                     ON bs.customer_id = bu.customer_id AND bs.status = 'active'
                   WHERE bu.id = $1::uuid""",
                beta_user_id,
            )
        if not user:
            return not_found("Beta user", beta_user_id)

        item = dict(user)
        item["id"] = str(item["id"])
        for k in ("welcomed_at", "completed_at", "created_at"):
            if item.get(k):
                item[k] = item[k].isoformat()

        return success_response(item, "beta_user", resource_id=item["id"])

    # ------------------------------------------------------------------
    # Admin: list beta users
    # ------------------------------------------------------------------

    @app.get("/users", tags=["Admin"])
    async def list_beta_users(
        step: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=200),
    ):
        """List beta users, optionally filtered by onboarding step."""
        params = []
        idx = 1
        where = ""
        if step:
            where = f"WHERE bu.onboarding_step = ${idx}"
            params.append(step)
            idx += 1
        params.append(limit)

        query = f"""
            SELECT bu.id, bu.email, bu.onboarding_step, bu.strategies,
                   bu.pairs, bu.created_at, ic.code AS invite_code
            FROM beta_users bu
            LEFT JOIN invite_codes ic ON ic.id = bu.invite_code_id
            {where}
            ORDER BY bu.created_at DESC
            LIMIT ${idx}
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)

        return collection_response(items, "beta_user")

    # ------------------------------------------------------------------
    # Admin: manage invite codes
    # ------------------------------------------------------------------

    @app.get("/invite-codes", tags=["Admin"])
    async def list_invite_codes():
        """List all invite codes with usage stats."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, code, created_by, max_uses, current_uses,
                       tier, expires_at, is_active, created_at
                FROM invite_codes
                ORDER BY created_at DESC
            """)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["remaining"] = item["max_uses"] - item["current_uses"]
            for k in ("expires_at", "created_at"):
                if item.get(k):
                    item[k] = item[k].isoformat()
            items.append(item)

        return collection_response(items, "invite_code")

    return app
