"""
Strategy Marketplace REST API — RMM Level 2.

Provides endpoints for publishing, browsing, subscribing to,
and rating strategy listings in the marketplace.
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


# --- Request / Response DTOs ---


class PublishRequest(BaseModel):
    strategy_id: str = Field(..., description="UUID of the strategy spec to publish")
    author: str = Field(..., description="Author name or identifier")
    description: str = Field(..., description="Marketplace listing description")
    performance_stats: Dict[str, Any] = Field(
        default_factory=dict, description="Performance statistics"
    )
    price: float = Field(0.0, ge=0, description="Listing price")


class RateRequest(BaseModel):
    user_id: str = Field(..., description="User submitting the rating")
    score: int = Field(..., ge=1, le=5, description="Rating score 1-5")
    review: Optional[str] = Field(None, description="Optional review text")


class SubscribeRequest(BaseModel):
    user_id: str = Field(..., description="User subscribing")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Marketplace API FastAPI application."""
    app = FastAPI(
        title="Strategy Marketplace API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/marketplace",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("marketplace-api", check_deps))

    listings_router = APIRouter(tags=["Listings"])

    # --- Publish a strategy ---

    @listings_router.post("", status_code=201)
    async def publish_listing(body: PublishRequest):
        query = """
            INSERT INTO marketplace_listings
                (strategy_id, author, description, performance_stats, price)
            VALUES ($1::uuid, $2, $3, $4::jsonb, $5)
            RETURNING id, strategy_id, author, description, performance_stats,
                      price, subscribers_count, created_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    body.strategy_id,
                    body.author,
                    body.description,
                    json.dumps(body.performance_stats),
                    body.price,
                )
        except asyncpg.ForeignKeyViolationError:
            return not_found("Strategy", body.strategy_id)
        except asyncpg.UniqueViolationError:
            return conflict(
                f"Listing for strategy '{body.strategy_id}' already exists"
            )
        except Exception as e:
            logger.error("Failed to publish listing: %s", e)
            return server_error(str(e))

        item = _listing_to_dict(row)
        return success_response(
            item, "marketplace_listing", resource_id=item["id"], status_code=201
        )

    # --- Browse listings ---

    @listings_router.get("")
    async def list_listings(
        pagination: PaginationParams = Depends(),
        author: Optional[str] = Query(None, description="Filter by author"),
        min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
        max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
        order_by: Optional[str] = Query(
            None,
            description="Sort field",
            regex="^(price|subscribers_count|created_at)$",
        ),
    ):
        conditions = ["is_active = TRUE"]
        params: list = []
        idx = 0

        if author is not None:
            idx += 1
            conditions.append(f"author = ${idx}")
            params.append(author)

        if min_price is not None:
            idx += 1
            conditions.append(f"price >= ${idx}")
            params.append(min_price)

        if max_price is not None:
            idx += 1
            conditions.append(f"price <= ${idx}")
            params.append(max_price)

        order_map = {
            "price": "price ASC",
            "subscribers_count": "subscribers_count DESC",
            "created_at": "created_at DESC",
        }
        order_clause = order_map.get(order_by, "created_at DESC")

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        where = " AND ".join(conditions)
        query = f"""
            SELECT id, strategy_id, author, description, performance_stats,
                   price, subscribers_count, created_at
            FROM marketplace_listings
            WHERE {where}
            ORDER BY {order_clause}
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"""
            SELECT COUNT(*) FROM marketplace_listings WHERE {where}
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = [_listing_to_dict(row) for row in rows]
        return collection_response(
            items,
            "marketplace_listing",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # --- Get listing detail ---

    @listings_router.get("/{listing_id}")
    async def get_listing(listing_id: str):
        query = """
            SELECT id, strategy_id, author, description, performance_stats,
                   price, subscribers_count, created_at
            FROM marketplace_listings
            WHERE id = $1::uuid
        """
        rating_query = """
            SELECT COALESCE(AVG(score), 0) AS avg_score,
                   COUNT(*) AS rating_count
            FROM marketplace_ratings
            WHERE listing_id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, listing_id)
            if not row:
                return not_found("Listing", listing_id)
            rating_row = await conn.fetchrow(rating_query, listing_id)

        item = _listing_to_dict(row)
        item["avg_rating"] = float(rating_row["avg_score"])
        item["rating_count"] = rating_row["rating_count"]
        return success_response(
            item, "marketplace_listing", resource_id=item["id"]
        )

    # --- Subscribe ---

    @listings_router.post("/{listing_id}/subscribe", status_code=201)
    async def subscribe(listing_id: str, body: SubscribeRequest):
        async with db_pool.acquire() as conn:
            listing = await conn.fetchrow(
                "SELECT id FROM marketplace_listings WHERE id = $1::uuid",
                listing_id,
            )
            if not listing:
                return not_found("Listing", listing_id)

            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO marketplace_subscriptions (listing_id, user_id)
                    VALUES ($1::uuid, $2)
                    RETURNING id, listing_id, user_id, created_at
                    """,
                    listing_id,
                    body.user_id,
                )
                await conn.execute(
                    """
                    UPDATE marketplace_listings
                    SET subscribers_count = subscribers_count + 1
                    WHERE id = $1::uuid
                    """,
                    listing_id,
                )
            except asyncpg.UniqueViolationError:
                return conflict("Already subscribed to this listing")

        item = dict(row)
        item["id"] = str(item["id"])
        item["listing_id"] = str(item["listing_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(
            item, "marketplace_subscription", resource_id=item["id"], status_code=201
        )

    # --- Unsubscribe ---

    @listings_router.delete("/{listing_id}/subscribe", status_code=204)
    async def unsubscribe(listing_id: str, user_id: str = Query(...)):
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                DELETE FROM marketplace_subscriptions
                WHERE listing_id = $1::uuid AND user_id = $2
                RETURNING id
                """,
                listing_id,
                user_id,
            )
            if not row:
                return not_found("Subscription", f"{listing_id}/{user_id}")
            await conn.execute(
                """
                UPDATE marketplace_listings
                SET subscribers_count = GREATEST(subscribers_count - 1, 0)
                WHERE id = $1::uuid
                """,
                listing_id,
            )
        return None

    # --- Rate a listing ---

    @listings_router.post("/{listing_id}/rate", status_code=201)
    async def rate_listing(listing_id: str, body: RateRequest):
        async with db_pool.acquire() as conn:
            listing = await conn.fetchrow(
                "SELECT id FROM marketplace_listings WHERE id = $1::uuid",
                listing_id,
            )
            if not listing:
                return not_found("Listing", listing_id)

            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO marketplace_ratings (listing_id, user_id, score, review)
                    VALUES ($1::uuid, $2, $3, $4)
                    ON CONFLICT (listing_id, user_id)
                    DO UPDATE SET score = EXCLUDED.score,
                                  review = EXCLUDED.review
                    RETURNING id, listing_id, user_id, score, review, created_at
                    """,
                    listing_id,
                    body.user_id,
                    body.score,
                    body.review,
                )
            except Exception as e:
                logger.error("Failed to rate listing: %s", e)
                return server_error(str(e))

        item = dict(row)
        item["id"] = str(item["id"])
        item["listing_id"] = str(item["listing_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(
            item, "marketplace_rating", resource_id=item["id"], status_code=201
        )

    # --- Get ratings ---

    @listings_router.get("/{listing_id}/ratings")
    async def list_ratings(
        listing_id: str,
        pagination: PaginationParams = Depends(),
    ):
        async with db_pool.acquire() as conn:
            listing = await conn.fetchrow(
                "SELECT id FROM marketplace_listings WHERE id = $1::uuid",
                listing_id,
            )
            if not listing:
                return not_found("Listing", listing_id)

            rows = await conn.fetch(
                """
                SELECT id, listing_id, user_id, score, review, created_at
                FROM marketplace_ratings
                WHERE listing_id = $1::uuid
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                listing_id,
                pagination.limit,
                pagination.offset,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM marketplace_ratings WHERE listing_id = $1::uuid",
                listing_id,
            )

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["listing_id"] = str(item["listing_id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)
        return collection_response(
            items,
            "marketplace_rating",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    app.include_router(listings_router)
    return app


def _listing_to_dict(row) -> dict:
    """Convert a listing DB row to a serializable dict."""
    item = dict(row)
    item["id"] = str(item["id"])
    item["strategy_id"] = str(item["strategy_id"])
    if item.get("created_at"):
        item["created_at"] = item["created_at"].isoformat()
    if "price" in item:
        item["price"] = float(item["price"])
    return item
