"""
Strategy Derivation REST API — RMM Level 2.

Provides CRUD endpoints for strategy specs and implementations,
plus action endpoints for evaluation and signal generation.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.circuit_breaker import CircuitBreaker
from services.rest_api_shared.error_middleware import install_error_handlers
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    conflict,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.rest_api_shared.retry import retry_with_backoff
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class StrategySpecCreate(BaseModel):
    name: str = Field(..., description="Unique spec name")
    indicators: Dict[str, Any] = Field(..., description="Indicator configurations")
    entry_conditions: Dict[str, Any] = Field(..., description="Entry rule definitions")
    exit_conditions: Dict[str, Any] = Field(..., description="Exit rule definitions")
    parameters: Dict[str, Any] = Field(
        ..., description="Parameter definitions with ranges"
    )
    description: str = Field(..., description="Human-readable description")


class StrategySpecUpdate(BaseModel):
    indicators: Optional[Dict[str, Any]] = None
    entry_conditions: Optional[Dict[str, Any]] = None
    exit_conditions: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class EvaluateRequest(BaseModel):
    instrument: str = Field(..., description="Trading instrument symbol")
    start_date: str = Field(..., description="Backtest start date (ISO format)")
    end_date: str = Field(..., description="Backtest end date (ISO format)")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Strategy API FastAPI application."""
    app = FastAPI(
        title="Strategy Derivation API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/strategies",
    )
    fastapi_auth_middleware(app)
    install_error_handlers(app)

    db_circuit = CircuitBreaker("postgres", failure_threshold=5, recovery_timeout=30.0)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok", "circuit_breaker": db_circuit.state.value}
        except Exception as e:
            return {"postgres": str(e), "circuit_breaker": db_circuit.state.value}

    app.include_router(create_health_router("strategy-api", check_deps))

    specs_router = APIRouter(prefix="/specs", tags=["Specs"])
    impls_router = APIRouter(prefix="/implementations", tags=["Implementations"])

    # --- Spec endpoints ---

    @specs_router.get("")
    async def list_specs(
        pagination: PaginationParams = Depends(),
        category: Optional[str] = Query(None, description="Filter by category"),
        active: bool = Query(True, description="Filter by active status"),
    ):
        query = """
            SELECT id, name, indicators, entry_conditions, exit_conditions,
                   parameters, description, source, created_at
            FROM strategy_specs
            WHERE ($1::text IS NULL OR source = $1)
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*) FROM strategy_specs
            WHERE ($1::text IS NULL OR source = $1)
        """

        async def _fetch():
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    query, category, pagination.limit, pagination.offset
                )
                total = await conn.fetchval(count_query, category)
            return rows, total

        try:
            rows, total = await db_circuit.call(
                retry_with_backoff, _fetch, operation_name="strategy.list_specs"
            )
        except Exception:
            return server_error("Failed to retrieve strategy specs")

        items = [dict(row) for row in rows]
        for item in items:
            item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
        return collection_response(
            items,
            "strategy_spec",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @specs_router.post("", status_code=201)
    async def create_spec(body: StrategySpecCreate):
        query = """
            INSERT INTO strategy_specs
                (name, indicators, entry_conditions, exit_conditions,
                 parameters, description, source)
            VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, $6, 'LLM_GENERATED')
            RETURNING id, name, created_at
        """

        async def _fetch():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(
                    query,
                    body.name,
                    json.dumps(body.indicators),
                    json.dumps(body.entry_conditions),
                    json.dumps(body.exit_conditions),
                    json.dumps(body.parameters),
                    body.description,
                )

        try:
            row = await db_circuit.call(
                retry_with_backoff, _fetch, operation_name="strategy.create_spec"
            )
        except asyncpg.UniqueViolationError:
            return conflict(f"Spec with name '{body.name}' already exists")
        except Exception as e:
            logger.error("Failed to create spec: %s", e)
            return server_error("Failed to create strategy spec")

        return success_response(
            data={
                "name": row["name"],
                "indicators": body.indicators,
                "entry_conditions": body.entry_conditions,
                "exit_conditions": body.exit_conditions,
                "parameters": body.parameters,
                "description": body.description,
            },
            resource_type="strategy_spec",
            resource_id=str(row["id"]),
            status_code=201,
        )

    @specs_router.get("/{spec_id}")
    async def get_spec(spec_id: str):
        query = """
            SELECT id, name, indicators, entry_conditions, exit_conditions,
                   parameters, description, source, created_at
            FROM strategy_specs
            WHERE id = $1::uuid
        """

        async def _fetch():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(query, spec_id)

        try:
            row = await db_circuit.call(
                retry_with_backoff, _fetch, operation_name="strategy.get_spec"
            )
        except Exception:
            return server_error("Failed to retrieve strategy spec")

        if not row:
            return not_found("Spec", spec_id)
        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(item, "strategy_spec", resource_id=item["id"])

    @specs_router.put("/{spec_id}")
    async def update_spec(spec_id: str, body: StrategySpecUpdate):
        updates = {}
        if body.indicators is not None:
            updates["indicators"] = json.dumps(body.indicators)
        if body.entry_conditions is not None:
            updates["entry_conditions"] = json.dumps(body.entry_conditions)
        if body.exit_conditions is not None:
            updates["exit_conditions"] = json.dumps(body.exit_conditions)
        if body.parameters is not None:
            updates["parameters"] = json.dumps(body.parameters)
        if body.description is not None:
            updates["description"] = body.description

        if not updates:
            return validation_error("No fields to update")

        set_clauses = []
        params = [spec_id]
        for i, (col, val) in enumerate(updates.items(), start=2):
            cast = "::jsonb" if col != "description" else ""
            set_clauses.append(f"{col} = ${i}{cast}")
            params.append(val)

        query = f"""
            UPDATE strategy_specs
            SET {', '.join(set_clauses)}
            WHERE id = $1::uuid
            RETURNING id, name, indicators, entry_conditions, exit_conditions,
                      parameters, description, source, created_at
        """

        async def _fetch():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(query, *params)

        try:
            row = await db_circuit.call(
                retry_with_backoff, _fetch, operation_name="strategy.update_spec"
            )
        except Exception:
            return server_error("Failed to update strategy spec")

        if not row:
            return not_found("Spec", spec_id)
        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(item, "strategy_spec", resource_id=item["id"])

    @specs_router.delete("/{spec_id}", status_code=204)
    async def delete_spec(spec_id: str):
        async def _fetch():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(
                    "DELETE FROM strategy_specs WHERE id = $1::uuid RETURNING id",
                    spec_id,
                )

        try:
            row = await db_circuit.call(
                retry_with_backoff, _fetch, operation_name="strategy.delete_spec"
            )
        except Exception:
            return server_error("Failed to delete strategy spec")

        if not row:
            return not_found("Spec", spec_id)
        return None

    @specs_router.get("/{spec_id}/implementations")
    async def list_spec_implementations(
        spec_id: str,
        pagination: PaginationParams = Depends(),
    ):
        query = """
            SELECT si.id, si.spec_id, si.parameters, si.status,
                   si.optimization_method, si.backtest_metrics,
                   si.paper_metrics, si.live_metrics, si.created_at
            FROM strategy_implementations si
            WHERE si.spec_id = $1::uuid
            ORDER BY si.created_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*) FROM strategy_implementations WHERE spec_id = $1::uuid
        """

        async def _fetch():
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    query, spec_id, pagination.limit, pagination.offset
                )
                total = await conn.fetchval(count_query, spec_id)
            return rows, total

        try:
            rows, total = await db_circuit.call(
                retry_with_backoff,
                _fetch,
                operation_name="strategy.list_spec_implementations",
            )
        except Exception:
            return server_error("Failed to retrieve implementations")

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["spec_id"] = str(item["spec_id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)
        return collection_response(
            items,
            "strategy_implementation",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @specs_router.post("/{spec_id}/implementations", status_code=201)
    async def create_implementation(spec_id: str):
        async def _fetch():
            async with db_pool.acquire() as conn:
                spec = await conn.fetchrow(
                    "SELECT id FROM strategy_specs WHERE id = $1::uuid", spec_id
                )
                if not spec:
                    return None
                return await conn.fetchrow(
                    """
                    INSERT INTO strategy_implementations (spec_id, parameters, status, optimization_method)
                    VALUES ($1::uuid, '{}'::jsonb, 'PENDING', 'LLM')
                    RETURNING id, spec_id, status, optimization_method, created_at
                    """,
                    spec_id,
                )

        try:
            row = await db_circuit.call(
                retry_with_backoff,
                _fetch,
                operation_name="strategy.create_implementation",
            )
        except Exception:
            return server_error("Failed to create implementation")

        if not row:
            return not_found("Spec", spec_id)
        item = dict(row)
        item["id"] = str(item["id"])
        item["spec_id"] = str(item["spec_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(
            item, "strategy_implementation", resource_id=item["id"], status_code=201
        )

    # --- Implementation endpoints ---

    @impls_router.get("")
    async def list_implementations(
        pagination: PaginationParams = Depends(),
        min_sharpe: Optional[float] = Query(None, description="Minimum Sharpe ratio"),
        instrument: Optional[str] = Query(None, description="Filter by instrument"),
        order_by: Optional[str] = Query(
            None, description="Sort field", regex="^(sharpe|win_rate|created_at)$"
        ),
    ):
        conditions = ["1=1"]
        params: list = []
        idx = 0

        if min_sharpe is not None:
            idx += 1
            conditions.append(
                f"COALESCE((si.backtest_metrics->>'sharpe_ratio')::float, 0) >= ${idx}"
            )
            params.append(min_sharpe)

        if instrument is not None:
            idx += 1
            conditions.append(
                f"""EXISTS (
                    SELECT 1 FROM Strategies s
                    JOIN strategy_specs ss2 ON s.strategy_type = ss2.name
                    WHERE ss2.id = si.spec_id AND s.symbol = ${idx}
                )"""
            )
            params.append(instrument)

        order_map = {
            "sharpe": "COALESCE((si.backtest_metrics->>'sharpe_ratio')::float, 0) DESC",
            "win_rate": "COALESCE((si.backtest_metrics->>'win_rate')::float, 0) DESC",
            "created_at": "si.created_at DESC",
        }
        order_clause = order_map.get(order_by, "si.created_at DESC")

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        where = " AND ".join(conditions)
        query = f"""
            SELECT si.id, si.spec_id, si.parameters, si.status,
                   si.optimization_method, si.backtest_metrics,
                   si.paper_metrics, si.live_metrics, si.created_at
            FROM strategy_implementations si
            WHERE {where}
            ORDER BY {order_clause}
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"""
            SELECT COUNT(*) FROM strategy_implementations si WHERE {where}
        """

        async def _fetch():
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                total = await conn.fetchval(count_query, *params[:-2])
            return rows, total

        try:
            rows, total = await db_circuit.call(
                retry_with_backoff,
                _fetch,
                operation_name="strategy.list_implementations",
            )
        except Exception:
            return server_error("Failed to retrieve implementations")

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["spec_id"] = str(item["spec_id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)
        return collection_response(
            items,
            "strategy_implementation",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @impls_router.get("/{impl_id}")
    async def get_implementation(impl_id: str):
        query = """
            SELECT si.id, si.spec_id, si.parameters, si.status,
                   si.optimization_method, si.backtest_metrics,
                   si.paper_metrics, si.live_metrics, si.created_at
            FROM strategy_implementations si
            WHERE si.id = $1::uuid
        """

        async def _fetch():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(query, impl_id)

        try:
            row = await db_circuit.call(
                retry_with_backoff,
                _fetch,
                operation_name="strategy.get_implementation",
            )
        except Exception:
            return server_error("Failed to retrieve implementation")

        if not row:
            return not_found("Implementation", impl_id)
        item = dict(row)
        item["id"] = str(item["id"])
        item["spec_id"] = str(item["spec_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(item, "strategy_implementation", resource_id=item["id"])

    @impls_router.delete("/{impl_id}", status_code=204)
    async def deactivate_implementation(impl_id: str):
        async def _fetch():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(
                    """
                    UPDATE strategy_implementations SET status = 'INACTIVE'
                    WHERE id = $1::uuid RETURNING id
                    """,
                    impl_id,
                )

        try:
            row = await db_circuit.call(
                retry_with_backoff,
                _fetch,
                operation_name="strategy.deactivate_implementation",
            )
        except Exception:
            return server_error("Failed to deactivate implementation")

        if not row:
            return not_found("Implementation", impl_id)
        return None

    @impls_router.post("/{impl_id}/evaluate")
    async def evaluate_implementation(impl_id: str, body: EvaluateRequest):
        async def _fetch():
            async with db_pool.acquire() as conn:
                return await conn.fetchrow(
                    "SELECT id FROM strategy_implementations WHERE id = $1::uuid",
                    impl_id,
                )

        try:
            row = await db_circuit.call(
                retry_with_backoff,
                _fetch,
                operation_name="strategy.evaluate_implementation",
            )
        except Exception:
            return server_error("Failed to evaluate implementation")

        if not row:
            return not_found("Implementation", impl_id)
        # Return a placeholder; actual backtesting is done by the backtesting service
        return success_response(
            {
                "implementation_id": impl_id,
                "instrument": body.instrument,
                "start_date": body.start_date,
                "end_date": body.end_date,
                "status": "SUBMITTED",
            },
            "backtest_result",
        )

    @impls_router.get("/{impl_id}/signal")
    async def get_signal(
        impl_id: str,
        instrument: str = Query(..., description="Trading instrument"),
    ):
        async def _fetch():
            async with db_pool.acquire() as conn:
                impl_row = await conn.fetchrow(
                    "SELECT id FROM strategy_implementations WHERE id = $1::uuid",
                    impl_id,
                )
                if not impl_row:
                    return None, None
                signal_row = await conn.fetchrow(
                    """
                    SELECT signal_id, symbol, action, confidence, created_at
                    FROM signals
                    WHERE symbol = $1
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    instrument,
                )
            return impl_row, signal_row

        try:
            impl_row, signal_row = await db_circuit.call(
                retry_with_backoff, _fetch, operation_name="strategy.get_signal"
            )
        except Exception:
            return server_error("Failed to retrieve signal")

        if not impl_row:
            return not_found("Implementation", impl_id)
        if not signal_row:
            return not_found("Signal", f"{impl_id}/{instrument}")
        item = dict(signal_row)
        item["signal_id"] = str(item["signal_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(item, "signal")

    app.include_router(specs_router)
    app.include_router(impls_router)
    return app
