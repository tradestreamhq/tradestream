"""
Stock Screener REST API — RMM Level 2.

Provides endpoints for running stock scans with custom filters,
managing built-in presets, and saving/loading user presets.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.screener_api.screener import (
    BUILT_IN_PRESETS,
    FilterCriterion,
    FilterOperator,
    MarketSnapshot,
    ScanRequest,
    run_scan,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request / Response DTOs ---


class FilterDTO(BaseModel):
    field: str = Field(
        ...,
        description="Field to filter on (price, volume, rsi, sma_20, sma_50, sma_200, ema_12, ema_26, change_pct)",
    )
    operator: str = Field(
        ..., description="Comparison operator (gt, gte, lt, lte, eq, between)"
    )
    value: float = Field(..., description="Filter value (or min for between)")
    value_max: Optional[float] = Field(
        None, description="Max value (only for between operator)"
    )


class ScanRequestDTO(BaseModel):
    filters: List[FilterDTO] = Field(..., description="List of filter criteria")
    sector: Optional[str] = Field(None, description="Filter by sector")
    limit: int = Field(50, ge=1, le=500, description="Max results to return")


class PresetCreateDTO(BaseModel):
    name: str = Field(..., description="Preset name")
    description: str = Field("", description="Preset description")
    filters: List[FilterDTO] = Field(..., description="Filter criteria")
    sector: Optional[str] = Field(None, description="Sector filter")


# --- Helpers ---


def _dto_to_criteria(filters: List[FilterDTO]) -> List[FilterCriterion]:
    """Convert DTOs to internal filter criteria."""
    criteria = []
    for f in filters:
        criteria.append(
            FilterCriterion(
                field=f.field,
                operator=FilterOperator(f.operator),
                value=f.value,
                value_max=f.value_max,
            )
        )
    return criteria


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool, market_data_fn=None) -> FastAPI:
    """Create the Screener API FastAPI application.

    Args:
        db_pool: asyncpg connection pool for preset storage.
        market_data_fn: Optional async callable returning List[MarketSnapshot].
                        If None, an empty list is used (useful for testing).
    """
    app = FastAPI(
        title="Stock Screener API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/screener",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("screener-api", check_deps))

    scan_router = APIRouter(tags=["Scan"])
    presets_router = APIRouter(prefix="/presets", tags=["Presets"])

    # --- Scan endpoint ---

    @scan_router.post("/scan")
    async def run_scan_endpoint(body: ScanRequestDTO):
        """Run a stock scan with the provided filter criteria."""
        try:
            criteria = _dto_to_criteria(body.filters)
        except ValueError as e:
            return validation_error(f"Invalid filter: {e}")

        snapshots: List[MarketSnapshot] = []
        if market_data_fn:
            snapshots = await market_data_fn()

        request = ScanRequest(
            filters=criteria,
            sector=body.sector,
            limit=body.limit,
        )
        results = run_scan(snapshots, request)

        items = [
            {
                "symbol": r.symbol,
                "current_price": r.current_price,
                "volume": r.volume,
                "matched_criteria": r.matched_criteria,
                "score": r.score,
            }
            for r in results
        ]
        return collection_response(items, "scan_result", total=len(items))

    # --- Presets endpoints ---

    @presets_router.get("")
    async def list_presets():
        """List built-in and user-saved presets."""
        built_in = [
            {**preset, "type": "built_in", "id": key}
            for key, preset in BUILT_IN_PRESETS.items()
        ]

        user_presets = []
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, name, description, filters, sector, created_at
                    FROM screener_presets
                    ORDER BY created_at DESC
                    """
                )
            for row in rows:
                item = dict(row)
                item["id"] = str(item["id"])
                item["type"] = "user"
                if item.get("created_at"):
                    item["created_at"] = item["created_at"].isoformat()
                user_presets.append(item)
        except Exception:
            logger.warning("Could not load user presets from database")

        all_presets = built_in + user_presets
        return collection_response(
            all_presets, "screener_preset", total=len(all_presets)
        )

    @presets_router.post("", status_code=201)
    async def create_preset(body: PresetCreateDTO):
        """Save a custom scan as a user preset."""
        try:
            _dto_to_criteria(body.filters)
        except ValueError as e:
            return validation_error(f"Invalid filter: {e}")

        filters_json = json.dumps([f.model_dump() for f in body.filters])

        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO screener_presets (name, description, filters, sector)
                    VALUES ($1, $2, $3::jsonb, $4)
                    RETURNING id, name, description, filters, sector, created_at
                    """,
                    body.name,
                    body.description,
                    filters_json,
                    body.sector,
                )
        except Exception as e:
            logger.error("Failed to create preset: %s", e)
            return server_error(str(e))

        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(
            item, "screener_preset", resource_id=item["id"], status_code=201
        )

    @presets_router.get("/{preset_id}")
    async def get_preset(preset_id: str):
        """Load a preset by ID (built-in or user-saved)."""
        # Check built-in presets first
        if preset_id in BUILT_IN_PRESETS:
            preset = {**BUILT_IN_PRESETS[preset_id], "type": "built_in"}
            return success_response(preset, "screener_preset", resource_id=preset_id)

        # Check user presets
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, name, description, filters, sector, created_at
                    FROM screener_presets
                    WHERE id = $1::uuid
                    """,
                    preset_id,
                )
        except Exception:
            return not_found("Preset", preset_id)

        if not row:
            return not_found("Preset", preset_id)

        item = dict(row)
        item["id"] = str(item["id"])
        item["type"] = "user"
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(item, "screener_preset", resource_id=item["id"])

    @presets_router.delete("/{preset_id}", status_code=204)
    async def delete_preset(preset_id: str):
        """Delete a user-saved preset. Built-in presets cannot be deleted."""
        if preset_id in BUILT_IN_PRESETS:
            return validation_error("Cannot delete built-in presets")

        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "DELETE FROM screener_presets WHERE id = $1::uuid RETURNING id",
                    preset_id,
                )
        except Exception:
            return not_found("Preset", preset_id)

        if not row:
            return not_found("Preset", preset_id)
        return None

    app.include_router(scan_router)
    app.include_router(presets_router)
    return app
