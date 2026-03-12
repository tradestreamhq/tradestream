"""
Rebalance REST API — RMM Level 2.

Provides endpoints for portfolio rebalancing: drift analysis,
trade calculation, allocation management, and rebalance history.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

TRANSACTION_COST_BPS = 10  # 10 basis points default


# --- DTOs ---


class RebalanceMethod(str, Enum):
    THRESHOLD = "THRESHOLD"
    CALENDAR = "CALENDAR"
    HYBRID = "HYBRID"
    MANUAL = "MANUAL"


class AllocationCreate(BaseModel):
    symbol: str = Field(..., description="Trading instrument symbol")
    strategy: Optional[str] = Field(None, description="Strategy name")
    target_weight: float = Field(..., ge=0, le=1, description="Target weight 0-1")
    min_weight: float = Field(0, ge=0, le=1, description="Minimum allowed weight")
    max_weight: float = Field(1, ge=0, le=1, description="Maximum allowed weight")
    rebalance_threshold: float = Field(
        0.05, ge=0, le=1, description="Drift threshold triggering rebalance"
    )


class CalculateRequest(BaseModel):
    method: RebalanceMethod = Field(
        RebalanceMethod.THRESHOLD, description="Rebalancing method"
    )
    total_equity: Optional[float] = Field(
        None, description="Override total equity for calculation"
    )


# --- Pure functions for drift and order calculation ---


def compute_drift(
    positions: List[Dict[str, Any]],
    allocations: List[Dict[str, Any]],
    total_equity: float,
) -> List[Dict[str, Any]]:
    """Compute drift between current and target weights for each allocation."""
    position_map: Dict[str, float] = {}
    for p in positions:
        value = float(p["quantity"]) * float(p["avg_entry_price"])
        position_map[p["symbol"]] = value

    drift_items = []
    for alloc in allocations:
        symbol = alloc["symbol"]
        current_value = position_map.get(symbol, 0.0)
        current_weight = current_value / total_equity if total_equity > 0 else 0.0
        target_weight = float(alloc["target_weight"])
        drift = current_weight - target_weight
        drift_pct = abs(drift)
        threshold = float(alloc["rebalance_threshold"])

        drift_items.append(
            {
                "symbol": symbol,
                "strategy": alloc.get("strategy"),
                "target_weight": target_weight,
                "current_weight": round(current_weight, 6),
                "drift": round(drift, 6),
                "drift_pct": round(drift_pct, 6),
                "needs_rebalance": drift_pct > threshold,
                "current_value": round(current_value, 2),
                "target_value": round(target_weight * total_equity, 2),
            }
        )

    return drift_items


def generate_orders(
    drift_items: List[Dict[str, Any]],
    total_equity: float,
    method: str,
    prices: Dict[str, float],
) -> List[Dict[str, Any]]:
    """Generate rebalance orders from drift analysis.

    Returns list of proposed orders with estimated transaction costs.
    """
    orders = []
    for item in drift_items:
        if method == "THRESHOLD" and not item["needs_rebalance"]:
            continue
        # For CALENDAR and HYBRID, generate orders for all drifted assets
        if method in ("CALENDAR", "HYBRID") and abs(item["drift"]) < 0.0001:
            continue

        symbol = item["symbol"]
        trade_value = item["target_value"] - item["current_value"]

        if abs(trade_value) < 0.01:
            continue

        price = prices.get(symbol, 0.0)
        if price <= 0:
            continue

        quantity = abs(trade_value) / price
        side = "BUY" if trade_value > 0 else "SELL"
        estimated_cost = abs(trade_value) * TRANSACTION_COST_BPS / 10000

        reason = (
            f"Drift {item['drift_pct']:.2%} exceeds threshold"
            if item["needs_rebalance"]
            else f"Calendar rebalance, drift {item['drift_pct']:.2%}"
        )

        orders.append(
            {
                "symbol": symbol,
                "side": side,
                "quantity": round(quantity, 8),
                "notional_value": round(abs(trade_value), 2),
                "reason": reason,
                "estimated_cost": round(estimated_cost, 2),
            }
        )

    return orders


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Rebalance API FastAPI application."""
    app = FastAPI(
        title="Rebalance API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/rebalance",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("rebalance-api", check_deps))

    # --- Allocations CRUD ---

    allocations_router = APIRouter(prefix="/allocations", tags=["Allocations"])

    @allocations_router.get("")
    async def list_allocations():
        """List all active target allocations."""
        query = """
            SELECT id, symbol, strategy, target_weight, min_weight, max_weight,
                   rebalance_threshold, is_active, created_at, updated_at
            FROM rebalance_allocations
            WHERE is_active = TRUE
            ORDER BY symbol
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            for f in ("target_weight", "min_weight", "max_weight", "rebalance_threshold"):
                item[f] = float(item[f])
            for f in ("created_at", "updated_at"):
                if item.get(f):
                    item[f] = item[f].isoformat()
            items.append(item)
        return collection_response(items, "allocation")

    @allocations_router.post("", status_code=201)
    async def create_allocation(body: AllocationCreate):
        """Create or update a target allocation."""
        if body.min_weight > body.max_weight:
            return validation_error("min_weight must be <= max_weight")
        if body.target_weight < body.min_weight or body.target_weight > body.max_weight:
            return validation_error("target_weight must be between min_weight and max_weight")

        query = """
            INSERT INTO rebalance_allocations
                (symbol, strategy, target_weight, min_weight, max_weight, rebalance_threshold)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (symbol, strategy) DO UPDATE SET
                target_weight = EXCLUDED.target_weight,
                min_weight = EXCLUDED.min_weight,
                max_weight = EXCLUDED.max_weight,
                rebalance_threshold = EXCLUDED.rebalance_threshold,
                is_active = TRUE,
                updated_at = NOW()
            RETURNING id
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                body.symbol,
                body.strategy,
                body.target_weight,
                body.min_weight,
                body.max_weight,
                body.rebalance_threshold,
            )
        return success_response(
            {"id": str(row["id"]), **body.model_dump()},
            "allocation",
            resource_id=str(row["id"]),
            status_code=201,
        )

    @allocations_router.delete("/{allocation_id}")
    async def delete_allocation(allocation_id: str):
        """Deactivate a target allocation."""
        query = """
            UPDATE rebalance_allocations SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1 AND is_active = TRUE
            RETURNING id
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, uuid.UUID(allocation_id))
        if not row:
            return not_found("Allocation", allocation_id)
        return success_response({"id": allocation_id, "is_active": False}, "allocation")

    app.include_router(allocations_router)

    # --- Drift ---

    @app.get("/drift", tags=["Rebalance"])
    async def get_drift():
        """Get current portfolio vs target weights with drift percentage per asset."""
        alloc_query = """
            SELECT symbol, strategy, target_weight, min_weight, max_weight,
                   rebalance_threshold
            FROM rebalance_allocations
            WHERE is_active = TRUE
        """
        pos_query = """
            SELECT symbol, quantity, avg_entry_price
            FROM paper_portfolio
            WHERE quantity != 0
        """
        equity_query = """
            SELECT COALESCE(SUM(quantity * avg_entry_price), 0) as total_equity
            FROM paper_portfolio
            WHERE quantity != 0
        """
        async with db_pool.acquire() as conn:
            alloc_rows = await conn.fetch(alloc_query)
            pos_rows = await conn.fetch(pos_query)
            equity_row = await conn.fetchrow(equity_query)

        allocations = [dict(r) for r in alloc_rows]
        positions = [dict(r) for r in pos_rows]
        total_equity = float(equity_row["total_equity"])

        drift_items = compute_drift(positions, allocations, total_equity)
        any_needs_rebalance = any(d["needs_rebalance"] for d in drift_items)

        return success_response(
            {
                "total_equity": round(total_equity, 2),
                "assets": drift_items,
                "needs_rebalance": any_needs_rebalance,
            },
            "drift_analysis",
        )

    # --- Calculate ---

    @app.post("/calculate", tags=["Rebalance"])
    async def calculate_rebalance(body: CalculateRequest):
        """Compute required trades to return to target allocations."""
        alloc_query = """
            SELECT symbol, strategy, target_weight, min_weight, max_weight,
                   rebalance_threshold
            FROM rebalance_allocations
            WHERE is_active = TRUE
        """
        pos_query = """
            SELECT symbol, quantity, avg_entry_price
            FROM paper_portfolio
            WHERE quantity != 0
        """
        equity_query = """
            SELECT COALESCE(SUM(quantity * avg_entry_price), 0) as total_equity
            FROM paper_portfolio
            WHERE quantity != 0
        """
        async with db_pool.acquire() as conn:
            alloc_rows = await conn.fetch(alloc_query)
            pos_rows = await conn.fetch(pos_query)
            equity_row = await conn.fetchrow(equity_query)

        allocations = [dict(r) for r in alloc_rows]
        positions = [dict(r) for r in pos_rows]
        total_equity = body.total_equity or float(equity_row["total_equity"])

        if total_equity <= 0:
            return validation_error("Total equity must be positive")

        drift_items = compute_drift(positions, allocations, total_equity)

        # Build price map from positions
        prices: Dict[str, float] = {}
        for p in positions:
            prices[p["symbol"]] = float(p["avg_entry_price"])
        # For symbols in allocations but not in positions, we need a price
        # Use avg_entry_price=0 which will skip order generation (no price available)

        orders = generate_orders(drift_items, total_equity, body.method.value, prices)

        total_estimated_cost = sum(o["estimated_cost"] for o in orders)

        # Persist the rebalance event
        weights_before = {
            d["symbol"]: d["current_weight"] for d in drift_items
        }
        event_id = str(uuid.uuid4())
        event_query = """
            INSERT INTO rebalance_events (id, method, status, weights_before, proposed_orders, estimated_cost)
            VALUES ($1, $2, 'PROPOSED', $3, $4, $5)
        """
        order_query = """
            INSERT INTO rebalance_orders (event_id, symbol, side, quantity, reason, estimated_cost)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        async with db_pool.acquire() as conn:
            await conn.execute(
                event_query,
                uuid.UUID(event_id),
                body.method.value,
                json.dumps(weights_before),
                json.dumps(orders),
                total_estimated_cost,
            )
            for order in orders:
                await conn.execute(
                    order_query,
                    uuid.UUID(event_id),
                    order["symbol"],
                    order["side"],
                    order["quantity"],
                    order["reason"],
                    order["estimated_cost"],
                )

        return success_response(
            {
                "event_id": event_id,
                "method": body.method.value,
                "total_equity": round(total_equity, 2),
                "orders": orders,
                "total_estimated_cost": round(total_estimated_cost, 2),
                "drift_summary": drift_items,
            },
            "rebalance_calculation",
            resource_id=event_id,
        )

    # --- History ---

    @app.get("/history", tags=["Rebalance"])
    async def get_history(pagination: PaginationParams = Depends()):
        """Get past rebalance events with before/after weights."""
        count_query = "SELECT COUNT(*) FROM rebalance_events"
        query = """
            SELECT id, method, status, weights_before, weights_after,
                   proposed_orders, estimated_cost, triggered_at, executed_at
            FROM rebalance_events
            ORDER BY triggered_at DESC
            LIMIT $1 OFFSET $2
        """
        async with db_pool.acquire() as conn:
            total = await conn.fetchval(count_query)
            rows = await conn.fetch(query, pagination.limit, pagination.offset)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["estimated_cost"] = float(item["estimated_cost"]) if item["estimated_cost"] else 0
            for f in ("triggered_at", "executed_at"):
                if item.get(f):
                    item[f] = item[f].isoformat()
            # JSONB fields are already dicts from asyncpg
            items.append(item)

        return collection_response(
            items, "rebalance_event", total=total,
            limit=pagination.limit, offset=pagination.offset,
        )

    return app
