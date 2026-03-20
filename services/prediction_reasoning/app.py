"""
Prediction Reasoning REST API.

Provides endpoints for:
- GET /signals/{signal_id}/reasoning — reasoning for a specific signal
- GET /reasoning/{id} — reasoning by its own ID
- GET /reasoning — list reasoning records with filters
"""

import logging
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query

from services.prediction_reasoning.store import (
    get_reasoning_by_id,
    get_reasoning_by_signal_id,
    list_reasoning,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    app = FastAPI(
        title="Prediction Reasoning API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/prediction-reasoning",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("prediction-reasoning-api", check_deps))

    # ------------------------------------------------------------------
    # Reasoning for a specific signal
    # ------------------------------------------------------------------

    @app.get("/signals/{signal_id}/reasoning", tags=["Reasoning"])
    async def get_signal_reasoning(signal_id: str):
        """Get the reasoning explanation for a specific signal."""
        result = await get_reasoning_by_signal_id(db_pool, signal_id)
        if not result:
            return not_found("Signal reasoning", signal_id)
        return success_response(result, "signal_reasoning", resource_id=result["id"])

    # ------------------------------------------------------------------
    # Reasoning by its own ID
    # ------------------------------------------------------------------

    @app.get("/reasoning/{reasoning_id}", tags=["Reasoning"])
    async def get_reasoning(reasoning_id: str):
        """Get reasoning by its own ID."""
        result = await get_reasoning_by_id(db_pool, reasoning_id)
        if not result:
            return not_found("Reasoning", reasoning_id)
        return success_response(result, "signal_reasoning", resource_id=result["id"])

    # ------------------------------------------------------------------
    # List reasoning records
    # ------------------------------------------------------------------

    @app.get("/reasoning", tags=["Reasoning"])
    async def list_reasoning_records(
        strategy: Optional[str] = Query(None),
        symbol: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        """List reasoning records with optional filters."""
        items = await list_reasoning(
            db_pool,
            strategy_name=strategy,
            symbol=symbol,
            limit=limit,
            offset=offset,
        )
        return collection_response(items, "signal_reasoning")

    return app
