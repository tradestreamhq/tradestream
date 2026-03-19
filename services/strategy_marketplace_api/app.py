"""
Strategy Marketplace & Leaderboard REST API.

Unified service for browsing, ranking, subscribing to, comparing,
and rating trading strategies.  Covers both the marketplace catalog
and the performance leaderboard with category filtering.
"""

import json
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Header, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    conflict,
    error_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

VALID_CATEGORIES = frozenset(
    {
        "trend_following",
        "mean_reversion",
        "momentum",
        "breakout",
        "multi_indicator",
        "volatility",
        "statistical",
    }
)


class Period(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALL_TIME = "all_time"


class LeaderboardSort(str, Enum):
    TOTAL_RETURN = "total_return_pct"
    SHARPE = "sharpe_ratio"
    WIN_RATE = "win_rate"
    CONSISTENCY = "consistency_score"


# ---------------------------------------------------------------------------
# Request / Response DTOs
# ---------------------------------------------------------------------------


class PublishRequest(BaseModel):
    strategy_id: str = Field(..., description="UUID of the strategy to publish")
    name: str = Field(..., description="Display name for the listing")
    author: str = Field(..., description="Author name or identifier")
    description: str = Field("", description="Marketplace listing description")
    category: str = Field("multi_indicator", description="Strategy category")
    tags: List[str] = Field(default_factory=list, description="Strategy tags")
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _listing_to_dict(row) -> dict:
    """Convert a listing DB row to a serialisable dict."""
    item = dict(row)
    for key in ("id", "strategy_id"):
        if key in item:
            item[key] = str(item[key])
    for key in ("price", "avg_rating"):
        if key in item and item[key] is not None:
            item[key] = float(item[key])
    if "tags" in item and item["tags"] is not None:
        item["tags"] = list(item["tags"])
    for ts_key in ("created_at", "updated_at"):
        if item.get(ts_key):
            item[ts_key] = item[ts_key].isoformat()
    return item


def _snapshot_to_dict(row) -> dict:
    """Convert a leaderboard snapshot row to a serialisable dict."""
    result: Dict[str, Any] = {}
    result["strategy_id"] = str(row["strategy_id"])
    result["period"] = row["period"]
    for key in (
        "total_return_pct",
        "sharpe_ratio",
        "win_rate",
        "max_drawdown_pct",
        "consistency_score",
    ):
        val = row.get(key)
        result[key] = float(val) if val is not None else None
    for key in ("trade_count", "rank"):
        val = row.get(key)
        result[key] = int(val) if val is not None else None
    sd = row.get("snapshot_date")
    result["snapshot_date"] = str(sd) if sd is not None else None
    # Include listing name if joined
    if row.get("name") is not None:
        result["name"] = row["name"]
    if row.get("category") is not None:
        result["category"] = row["category"]
    if row.get("author") is not None:
        result["author"] = row["author"]
    return result


# ---------------------------------------------------------------------------
# Application Factory
# ---------------------------------------------------------------------------


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Strategy Marketplace & Leaderboard API."""
    app = FastAPI(
        title="Strategy Marketplace & Leaderboard API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/marketplace",
    )
    fastapi_auth_middleware(app)

    # Simple in-memory cache
    _cache: Dict[str, tuple] = {}

    def _get_cached(key: str) -> Optional[Any]:
        if key in _cache:
            ts, data = _cache[key]
            if time.monotonic() - ts < CACHE_TTL_SECONDS:
                return data
            del _cache[key]
        return None

    def _set_cached(key: str, data: Any) -> None:
        _cache[key] = (time.monotonic(), data)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("strategy-marketplace-api", check_deps))

    # ===================================================================
    # MARKETPLACE — Strategy Catalog
    # ===================================================================
    catalog_router = APIRouter(prefix="/strategies", tags=["Marketplace"])

    @catalog_router.post("", status_code=201)
    async def publish_strategy(body: PublishRequest):
        """Publish a strategy to the marketplace."""
        if body.category not in VALID_CATEGORIES:
            return validation_error(
                f"Invalid category '{body.category}'. "
                f"Valid: {', '.join(sorted(VALID_CATEGORIES))}"
            )
        query = """
            INSERT INTO marketplace_listings
                (strategy_id, name, author, description, category, tags,
                 performance_stats, price)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8)
            RETURNING id, strategy_id, name, author, description, category,
                      tags, performance_stats, price, subscribers_count,
                      avg_rating, rating_count, created_at
        """
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    body.strategy_id,
                    body.name,
                    body.author,
                    body.description,
                    body.tags,
                    json.dumps(body.performance_stats),
                    body.price,
                )
        except asyncpg.UniqueViolationError:
            return conflict(f"Listing for strategy '{body.strategy_id}' already exists")
        except Exception as e:
            logger.error("Failed to publish listing: %s", e)
            return server_error(str(e))

        item = _listing_to_dict(row)
        return success_response(
            item, "marketplace_listing", resource_id=item["id"], status_code=201
        )

    @catalog_router.get("")
    async def list_strategies(
        pagination: PaginationParams = Depends(),
        category: Optional[str] = Query(None, description="Filter by category"),
        author: Optional[str] = Query(None, description="Filter by author"),
        tags: Optional[str] = Query(None, description="Comma-separated tags"),
        min_price: Optional[float] = Query(None, ge=0),
        max_price: Optional[float] = Query(None, ge=0),
        search: Optional[str] = Query(None, description="Search name/description"),
        order_by: Optional[str] = Query(
            None,
            description="Sort field",
            regex="^(price|subscribers_count|avg_rating|created_at)$",
        ),
    ):
        """Browse marketplace strategies with filtering and sorting."""
        conditions = ["is_active = TRUE"]
        params: list = []
        idx = 0

        if category is not None:
            idx += 1
            conditions.append(f"category = ${idx}")
            params.append(category)
        if author is not None:
            idx += 1
            conditions.append(f"author = ${idx}")
            params.append(author)
        if tags is not None:
            idx += 1
            conditions.append(f"tags && ${idx}::text[]")
            params.append(tags.split(","))
        if min_price is not None:
            idx += 1
            conditions.append(f"price >= ${idx}")
            params.append(min_price)
        if max_price is not None:
            idx += 1
            conditions.append(f"price <= ${idx}")
            params.append(max_price)
        if search is not None:
            idx += 1
            conditions.append(f"(name ILIKE ${idx} OR description ILIKE ${idx})")
            params.append(f"%{search}%")

        order_map = {
            "price": "price ASC",
            "subscribers_count": "subscribers_count DESC",
            "avg_rating": "avg_rating DESC",
            "created_at": "created_at DESC",
        }
        order_clause = order_map.get(order_by, "subscribers_count DESC")

        idx += 1
        limit_idx = idx
        idx += 1
        offset_idx = idx
        params.extend([pagination.limit, pagination.offset])

        where = " AND ".join(conditions)
        query = f"""
            SELECT id, strategy_id, name, author, description, category,
                   tags, performance_stats, price, subscribers_count,
                   avg_rating, rating_count, created_at
            FROM marketplace_listings
            WHERE {where}
            ORDER BY {order_clause}
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        count_query = f"SELECT COUNT(*) FROM marketplace_listings WHERE {where}"

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

    @catalog_router.get("/categories")
    async def list_categories():
        """List available strategy categories."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, label, description FROM strategy_categories ORDER BY label"
            )
        items = [dict(r) for r in rows]
        return collection_response(items, "strategy_category", total=len(items))

    @catalog_router.get("/{listing_id}")
    async def get_strategy(listing_id: str):
        """Get strategy detail with full performance metrics."""
        query = """
            SELECT id, strategy_id, name, author, description, category,
                   tags, performance_stats, price, subscribers_count,
                   avg_rating, rating_count, created_at, updated_at
            FROM marketplace_listings
            WHERE id = $1::uuid
        """
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, listing_id)
            if not row:
                return not_found("Listing", listing_id)

            # Fetch latest leaderboard snapshot for this strategy
            perf_row = await conn.fetchrow(
                """
                SELECT total_return_pct, sharpe_ratio, win_rate,
                       max_drawdown_pct, trade_count, consistency_score,
                       snapshot_date
                FROM leaderboard_snapshots
                WHERE strategy_id = $1::uuid
                  AND period = 'all_time'
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                str(row["strategy_id"]),
            )

        item = _listing_to_dict(row)
        if perf_row:
            item["live_metrics"] = {
                "total_return_pct": float(perf_row["total_return_pct"]),
                "sharpe_ratio": float(perf_row["sharpe_ratio"]),
                "win_rate": float(perf_row["win_rate"]),
                "max_drawdown_pct": float(perf_row["max_drawdown_pct"]),
                "trade_count": int(perf_row["trade_count"]),
                "consistency_score": float(perf_row["consistency_score"]),
                "snapshot_date": str(perf_row["snapshot_date"]),
            }
        return success_response(item, "marketplace_listing", resource_id=item["id"])

    # --- Subscribe / Unsubscribe ---

    @catalog_router.post("/{listing_id}/subscribe", status_code=201)
    async def subscribe(listing_id: str, body: SubscribeRequest):
        """Subscribe to a strategy for signal notifications."""
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

    @catalog_router.delete("/{listing_id}/subscribe", status_code=204)
    async def unsubscribe(listing_id: str, user_id: str = Query(...)):
        """Unsubscribe from a strategy."""
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

    # --- Ratings ---

    @catalog_router.post("/{listing_id}/rate", status_code=201)
    async def rate_strategy(listing_id: str, body: RateRequest):
        """Rate a marketplace strategy."""
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
                    DO UPDATE SET score = EXCLUDED.score, review = EXCLUDED.review
                    RETURNING id, listing_id, user_id, score, review, created_at
                    """,
                    listing_id,
                    body.user_id,
                    body.score,
                    body.review,
                )
                # Update denormalised avg_rating
                await conn.execute(
                    """
                    UPDATE marketplace_listings
                    SET avg_rating = sub.avg_score,
                        rating_count = sub.cnt
                    FROM (
                        SELECT AVG(score) AS avg_score, COUNT(*) AS cnt
                        FROM marketplace_ratings
                        WHERE listing_id = $1::uuid
                    ) sub
                    WHERE id = $1::uuid
                    """,
                    listing_id,
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

    @catalog_router.get("/{listing_id}/ratings")
    async def list_ratings(
        listing_id: str,
        pagination: PaginationParams = Depends(),
    ):
        """Get ratings for a strategy listing."""
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

    app.include_router(catalog_router)

    # ===================================================================
    # LEADERBOARD — Strategy Rankings
    # ===================================================================
    leaderboard_router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])

    @leaderboard_router.get("")
    async def get_leaderboard(
        period: Period = Query(Period.MONTHLY, description="Time period"),
        sort_by: LeaderboardSort = Query(
            LeaderboardSort.TOTAL_RETURN, description="Metric to rank by"
        ),
        category: Optional[str] = Query(
            None, description="Filter by strategy category"
        ),
        pagination: PaginationParams = Depends(),
    ):
        """Get ranked list of strategies by performance metrics."""
        cache_key = (
            f"lb:{period.value}:{sort_by.value}:{category}"
            f":{pagination.limit}:{pagination.offset}"
        )
        cached = _get_cached(cache_key)
        if cached is not None:
            return cached

        sort_col = sort_by.value
        conditions = [
            "ls.period = $1",
            "ls.snapshot_date = (SELECT MAX(snapshot_date) FROM leaderboard_snapshots WHERE period = $1)",
        ]
        params: list = [period.value]
        idx = 2

        if category is not None:
            conditions.append(f"ml.category = ${idx}")
            params.append(category)
            idx += 1

        where = " AND ".join(conditions)
        params.append(pagination.limit)
        params.append(pagination.offset)

        query = f"""
            SELECT ls.strategy_id, ls.period, ls.rank,
                   ls.total_return_pct, ls.sharpe_ratio, ls.win_rate,
                   ls.max_drawdown_pct, ls.trade_count, ls.consistency_score,
                   ls.snapshot_date,
                   ml.name, ml.category, ml.author
            FROM leaderboard_snapshots ls
            LEFT JOIN marketplace_listings ml ON ml.strategy_id = ls.strategy_id
            WHERE {where}
            ORDER BY {sort_col} DESC NULLS LAST
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        count_query = f"""
            SELECT COUNT(*)
            FROM leaderboard_snapshots ls
            LEFT JOIN marketplace_listings ml ON ml.strategy_id = ls.strategy_id
            WHERE {where}
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(count_query, *params[:-2])

        items = [_snapshot_to_dict(row) for row in rows]
        response = collection_response(
            items,
            "strategy_ranking",
            total=total or 0,
            limit=pagination.limit,
            offset=pagination.offset,
        )
        _set_cached(cache_key, response)
        return response

    @leaderboard_router.get("/periods")
    async def get_available_periods():
        """List available leaderboard periods with latest snapshot dates."""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT period, MAX(snapshot_date) AS latest_snapshot,
                       COUNT(DISTINCT strategy_id) AS strategy_count
                FROM leaderboard_snapshots
                GROUP BY period
                ORDER BY period
                """
            )
        items = [
            {
                "period": r["period"],
                "latest_snapshot": str(r["latest_snapshot"]),
                "strategy_count": r["strategy_count"],
            }
            for r in rows
        ]
        return collection_response(items, "leaderboard_period", total=len(items))

    app.include_router(leaderboard_router)

    # ===================================================================
    # COMPARISON — Side-by-side strategy comparison
    # ===================================================================
    compare_router = APIRouter(prefix="/compare", tags=["Comparison"])

    @compare_router.get("")
    async def compare_strategies(
        ids: str = Query(..., description="Comma-separated listing IDs (2-5)"),
        period: Period = Query(Period.ALL_TIME, description="Performance period"),
    ):
        """Compare 2-5 strategies side by side."""
        id_list = [x.strip() for x in ids.split(",") if x.strip()]
        if len(id_list) < 2 or len(id_list) > 5:
            return validation_error("Provide 2-5 strategy IDs for comparison")

        placeholders = ", ".join(f"${i + 1}::uuid" for i in range(len(id_list)))
        listing_query = f"""
            SELECT id, strategy_id, name, author, description, category,
                   tags, performance_stats, price, subscribers_count,
                   avg_rating, rating_count, created_at
            FROM marketplace_listings
            WHERE id IN ({placeholders})
        """

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(listing_query, *id_list)
            if not rows:
                return not_found("Listings", ids)

            # Fetch leaderboard data for each strategy
            strategy_ids = [str(r["strategy_id"]) for r in rows]
            s_placeholders = ", ".join(
                f"${i + 2}::uuid" for i in range(len(strategy_ids))
            )
            perf_query = f"""
                SELECT strategy_id, total_return_pct, sharpe_ratio, win_rate,
                       max_drawdown_pct, trade_count, consistency_score,
                       snapshot_date
                FROM leaderboard_snapshots
                WHERE strategy_id IN ({s_placeholders})
                  AND period = $1
                  AND snapshot_date = (
                      SELECT MAX(snapshot_date) FROM leaderboard_snapshots WHERE period = $1
                  )
            """
            perf_rows = await conn.fetch(perf_query, period.value, *strategy_ids)

        perf_map = {str(r["strategy_id"]): r for r in perf_rows}

        comparisons = []
        for row in rows:
            item = _listing_to_dict(row)
            sid = item["strategy_id"]
            perf = perf_map.get(sid)
            if perf:
                item["metrics"] = {
                    "total_return_pct": float(perf["total_return_pct"]),
                    "sharpe_ratio": float(perf["sharpe_ratio"]),
                    "win_rate": float(perf["win_rate"]),
                    "max_drawdown_pct": float(perf["max_drawdown_pct"]),
                    "trade_count": int(perf["trade_count"]),
                    "consistency_score": float(perf["consistency_score"]),
                }
            comparisons.append(item)

        return collection_response(
            comparisons, "strategy_comparison", total=len(comparisons)
        )

    app.include_router(compare_router)

    return app
