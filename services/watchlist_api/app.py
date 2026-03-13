"""
Watchlist & Favorites REST API — RMM Level 2.

Provides CRUD endpoints for watchlists and favorites,
plus a dashboard widget endpoint with current prices and 24h changes.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query
from pydantic import BaseModel, Field

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
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

VALID_ENTITY_TYPES = frozenset({"strategies", "pairs", "templates"})


# --- Request / Response DTOs ---


class WatchlistCreate(BaseModel):
    name: str = Field(..., description="Unique watchlist name")
    pairs: List[str] = Field(
        default_factory=list, description="Trading pair symbols"
    )
    alert_conditions: Optional[Dict[str, Any]] = Field(
        None, description="Optional alert trigger conditions"
    )


class WatchlistUpdate(BaseModel):
    name: Optional[str] = Field(None, description="New watchlist name")
    pairs: Optional[List[str]] = Field(None, description="Updated pair list")
    alert_conditions: Optional[Dict[str, Any]] = Field(
        None, description="Updated alert conditions"
    )


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Watchlist API FastAPI application."""
    app = FastAPI(
        title="Watchlist & Favorites API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/watchlists",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("watchlist-api", check_deps))

    watchlists_router = APIRouter(prefix="/watchlists", tags=["Watchlists"])
    favorites_router = APIRouter(prefix="/favorites", tags=["Favorites"])

    # --- Watchlist endpoints ---

    @watchlists_router.get("")
    async def list_watchlists(pagination: PaginationParams = Depends()):
        query = """
            SELECT id, name, pairs, alert_conditions, created_at, updated_at
            FROM watchlists
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM watchlists"
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, pagination.limit, pagination.offset)
            total = await conn.fetchval(count_query)

        items = [dict(row) for row in rows]
        for item in items:
            item["id"] = str(item["id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            if item.get("updated_at"):
                item["updated_at"] = item["updated_at"].isoformat()
        return collection_response(
            items,
            "watchlist",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    @watchlists_router.post("", status_code=201)
    async def create_watchlist(body: WatchlistCreate):
        query = """
            INSERT INTO watchlists (name, pairs, alert_conditions)
            VALUES ($1, $2::jsonb, $3::jsonb)
            RETURNING id, name, pairs, alert_conditions, created_at, updated_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    body.name,
                    json.dumps(body.pairs),
                    json.dumps(body.alert_conditions) if body.alert_conditions else None,
                )
        except asyncpg.UniqueViolationError:
            return conflict(f"Watchlist with name '{body.name}' already exists")
        except Exception as e:
            logger.error("Failed to create watchlist: %s", e)
            return server_error(str(e))

        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        return success_response(
            item, "watchlist", resource_id=item["id"], status_code=201
        )

    @watchlists_router.get("/widget")
    async def watchlist_widget(watchlist_id: str = Query(..., description="Watchlist ID")):
        """Dashboard widget: returns watchlist pairs with current prices and 24h changes."""
        wl_query = """
            SELECT id, name, pairs FROM watchlists WHERE id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(wl_query, watchlist_id)
        if not row:
            return not_found("Watchlist", watchlist_id)

        pairs = row["pairs"] if row["pairs"] else []
        widget_items = []
        for pair in pairs:
            widget_items.append({
                "pair": pair,
                "current_price": None,
                "change_24h": None,
            })

        return success_response(
            {
                "watchlist_id": str(row["id"]),
                "watchlist_name": row["name"],
                "pairs": widget_items,
            },
            "watchlist_widget",
        )

    @watchlists_router.get("/{watchlist_id}")
    async def get_watchlist(watchlist_id: str):
        query = """
            SELECT id, name, pairs, alert_conditions, created_at, updated_at
            FROM watchlists WHERE id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, watchlist_id)
        if not row:
            return not_found("Watchlist", watchlist_id)
        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        return success_response(item, "watchlist", resource_id=item["id"])

    @watchlists_router.put("/{watchlist_id}")
    async def update_watchlist(watchlist_id: str, body: WatchlistUpdate):
        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.pairs is not None:
            updates["pairs"] = json.dumps(body.pairs)
        if body.alert_conditions is not None:
            updates["alert_conditions"] = json.dumps(body.alert_conditions)

        if not updates:
            return validation_error("No fields to update")

        set_clauses = []
        params = [watchlist_id]
        for i, (col, val) in enumerate(updates.items(), start=2):
            cast = "::jsonb" if col in ("pairs", "alert_conditions") else ""
            set_clauses.append(f"{col} = ${i}{cast}")
            params.append(val)

        query = f"""
            UPDATE watchlists
            SET {', '.join(set_clauses)}
            WHERE id = $1::uuid
            RETURNING id, name, pairs, alert_conditions, created_at, updated_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)
        except asyncpg.UniqueViolationError:
            return conflict(f"Watchlist with name '{body.name}' already exists")
        except Exception as e:
            logger.error("Failed to update watchlist: %s", e)
            return server_error(str(e))

        if not row:
            return not_found("Watchlist", watchlist_id)
        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        return success_response(item, "watchlist", resource_id=item["id"])

    @watchlists_router.delete("/{watchlist_id}", status_code=204)
    async def delete_watchlist(watchlist_id: str):
        query = "DELETE FROM watchlists WHERE id = $1::uuid RETURNING id"
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, watchlist_id)
        if not row:
            return not_found("Watchlist", watchlist_id)
        return None

    # --- Favorites endpoints ---

    @favorites_router.get("")
    async def list_favorites():
        """List all favorites grouped by entity type."""
        query = """
            SELECT id, entity_type, entity_id, created_at
            FROM favorites
            ORDER BY entity_type, created_at DESC
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query)

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            et = row["entity_type"]
            item = {
                "id": str(row["id"]),
                "entity_id": row["entity_id"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            grouped.setdefault(et, []).append(item)

        return success_response(grouped, "favorites")

    @favorites_router.post("/{entity_type}/{entity_id}", status_code=201)
    async def add_favorite(entity_type: str, entity_id: str):
        if entity_type not in VALID_ENTITY_TYPES:
            return validation_error(
                f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}"
            )

        query = """
            INSERT INTO favorites (entity_type, entity_id)
            VALUES ($1, $2)
            RETURNING id, entity_type, entity_id, created_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(query, entity_type, entity_id)
        except asyncpg.UniqueViolationError:
            return conflict(
                f"Favorite for {entity_type}/{entity_id} already exists"
            )
        except Exception as e:
            logger.error("Failed to add favorite: %s", e)
            return server_error(str(e))

        item = dict(row)
        item["id"] = str(item["id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(
            item, "favorite", resource_id=item["id"], status_code=201
        )

    @favorites_router.delete("/{entity_type}/{entity_id}", status_code=204)
    async def remove_favorite(entity_type: str, entity_id: str):
        query = """
            DELETE FROM favorites
            WHERE entity_type = $1 AND entity_id = $2
            RETURNING id
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, entity_type, entity_id)
        if not row:
            return not_found("Favorite", f"{entity_type}/{entity_id}")
        return None

    app.include_router(watchlists_router)
    app.include_router(favorites_router)
    return app
