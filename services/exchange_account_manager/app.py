"""
Exchange Account Manager REST API — RMM Level 2.

Provides CRUD endpoints for exchange accounts with encrypted credential
storage, per-account balance fetching, and a unified portfolio view.
"""

import json
import logging
import uuid
from typing import List

import asyncpg
from fastapi import FastAPI
from pydantic import BaseModel

from services.exchange_account_manager import credential_store, exchange_client
from services.exchange_account_manager.models import (
    AccountBalance,
    ExchangeAccountCreate,
    ExchangeAccountResponse,
    ExchangeAccountUpdate,
    UnifiedPortfolio,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    conflict,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Exchange Account Manager FastAPI application."""
    app = FastAPI(
        title="Exchange Account Manager API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/exchange-accounts",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("exchange-account-manager", check_deps))

    # --- Create account ---

    @app.post("/accounts", tags=["Accounts"], status_code=201)
    async def create_account(body: ExchangeAccountCreate):
        """Connect a new exchange account with encrypted credentials."""
        encrypted_key = credential_store.encrypt(body.api_key)
        encrypted_secret = credential_store.encrypt(body.api_secret)
        account_id = str(uuid.uuid4())

        query = """
            INSERT INTO exchange_accounts
                (id, exchange, label, encrypted_api_key, encrypted_api_secret,
                 permissions, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, TRUE)
            RETURNING id, exchange, label, permissions, is_active, created_at, updated_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    account_id,
                    body.exchange.lower(),
                    body.label,
                    encrypted_key,
                    encrypted_secret,
                    json.dumps(body.permissions),
                )
        except asyncpg.UniqueViolationError:
            return conflict(
                f"Account with label '{body.label}' already exists for {body.exchange}"
            )

        return success_response(
            _row_to_dict(row),
            "exchange_account",
            resource_id=account_id,
        )

    # --- List accounts ---

    @app.get("/accounts", tags=["Accounts"])
    async def list_accounts():
        """List all connected exchange accounts (credentials omitted)."""
        query = """
            SELECT id, exchange, label, permissions, is_active, created_at, updated_at
            FROM exchange_accounts
            ORDER BY created_at
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)
        return collection_response(
            [_row_to_dict(r) for r in rows], "exchange_account"
        )

    # --- Get single account ---

    @app.get("/accounts/{account_id}", tags=["Accounts"])
    async def get_account(account_id: str):
        """Get details for a single exchange account."""
        row = await _fetch_account(db_pool, account_id)
        if not row:
            return not_found("Exchange account", account_id)
        return success_response(
            _row_to_dict(row), "exchange_account", resource_id=account_id
        )

    # --- Update account ---

    @app.patch("/accounts/{account_id}", tags=["Accounts"])
    async def update_account(account_id: str, body: ExchangeAccountUpdate):
        """Update an exchange account's label, credentials, or permissions."""
        existing = await _fetch_account(db_pool, account_id)
        if not existing:
            return not_found("Exchange account", account_id)

        sets: list[str] = []
        params: list = []
        idx = 1

        if body.label is not None:
            sets.append(f"label = ${idx}")
            params.append(body.label)
            idx += 1
        if body.api_key is not None:
            sets.append(f"encrypted_api_key = ${idx}")
            params.append(credential_store.encrypt(body.api_key))
            idx += 1
        if body.api_secret is not None:
            sets.append(f"encrypted_api_secret = ${idx}")
            params.append(credential_store.encrypt(body.api_secret))
            idx += 1
        if body.permissions is not None:
            sets.append(f"permissions = ${idx}")
            params.append(json.dumps(body.permissions))
            idx += 1

        if not sets:
            return validation_error("No fields to update")

        sets.append("updated_at = NOW()")
        params.append(account_id)
        query = f"""
            UPDATE exchange_accounts SET {', '.join(sets)}
            WHERE id = ${idx}
            RETURNING id, exchange, label, permissions, is_active, created_at, updated_at
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
        return success_response(
            _row_to_dict(row), "exchange_account", resource_id=account_id
        )

    # --- Delete account ---

    @app.delete("/accounts/{account_id}", tags=["Accounts"])
    async def delete_account(account_id: str):
        """Disconnect (soft-delete) an exchange account."""
        query = """
            UPDATE exchange_accounts SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1 AND is_active = TRUE
            RETURNING id
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, account_id)
        if not row:
            return not_found("Exchange account", account_id)
        return success_response(
            {"deleted": True}, "exchange_account", resource_id=account_id
        )

    # --- Fetch balances for one account ---

    @app.get("/accounts/{account_id}/balances", tags=["Balances"])
    async def get_account_balances(account_id: str):
        """Fetch live balances for a single exchange account."""
        query = """
            SELECT id, exchange, label, encrypted_api_key, encrypted_api_secret
            FROM exchange_accounts
            WHERE id = $1 AND is_active = TRUE
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, account_id)
        if not row:
            return not_found("Exchange account", account_id)

        api_key = credential_store.decrypt(row["encrypted_api_key"])
        api_secret = credential_store.decrypt(row["encrypted_api_secret"])
        balances = await exchange_client.fetch_balances(
            row["exchange"], api_key, api_secret
        )
        total_usd = exchange_client.estimate_usd(balances)

        return success_response(
            AccountBalance(
                account_id=str(row["id"]),
                exchange=row["exchange"],
                label=row["label"],
                balances=balances,
                total_usd=round(total_usd, 2),
            ).model_dump(),
            "account_balance",
            resource_id=account_id,
        )

    # --- Unified portfolio ---

    @app.get("/portfolio", tags=["Portfolio"])
    async def get_unified_portfolio():
        """Aggregate balances across all active exchange accounts."""
        query = """
            SELECT id, exchange, label, encrypted_api_key, encrypted_api_secret
            FROM exchange_accounts
            WHERE is_active = TRUE
            ORDER BY created_at
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        account_balances: list[AccountBalance] = []
        asset_totals: dict[str, float] = {}
        grand_total = 0.0

        for row in rows:
            api_key = credential_store.decrypt(row["encrypted_api_key"])
            api_secret = credential_store.decrypt(row["encrypted_api_secret"])
            balances = await exchange_client.fetch_balances(
                row["exchange"], api_key, api_secret
            )
            total_usd = exchange_client.estimate_usd(balances)
            grand_total += total_usd

            for asset, amount in balances.items():
                asset_totals[asset] = asset_totals.get(asset, 0.0) + amount

            account_balances.append(
                AccountBalance(
                    account_id=str(row["id"]),
                    exchange=row["exchange"],
                    label=row["label"],
                    balances=balances,
                    total_usd=round(total_usd, 2),
                )
            )

        portfolio = UnifiedPortfolio(
            accounts=account_balances,
            total_usd=round(grand_total, 2),
            asset_totals={k: round(v, 8) for k, v in asset_totals.items()},
        )
        return success_response(portfolio.model_dump(), "unified_portfolio")

    return app


async def _fetch_account(db_pool: asyncpg.Pool, account_id: str):
    """Fetch a single active account row by ID."""
    query = """
        SELECT id, exchange, label, permissions, is_active, created_at, updated_at
        FROM exchange_accounts
        WHERE id = $1 AND is_active = TRUE
    """
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(query, account_id)


def _row_to_dict(row) -> dict:
    """Convert an asyncpg Record to a JSON-safe dict."""
    d = dict(row)
    for key in ("id",):
        if key in d:
            d[key] = str(d[key])
    for key in ("created_at", "updated_at"):
        if key in d and d[key] is not None:
            d[key] = d[key].isoformat()
    if "permissions" in d and isinstance(d["permissions"], str):
        d["permissions"] = json.loads(d["permissions"])
    return d
