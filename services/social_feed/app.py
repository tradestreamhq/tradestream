"""
Strategy Sharing & Social Feed REST API — RMM Level 2.

Provides endpoints for sharing strategies to a community feed,
liking/commenting on shared strategies, and following other users.
"""

import logging
from typing import Optional

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
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


# --- Request DTOs ---


class ShareStrategyRequest(BaseModel):
    author_id: str = Field(..., description="ID of the user sharing the strategy")
    author_name: str = Field("anonymous", description="Display name of the author")
    caption: str = Field("", description="Optional caption for the share")


class LikeRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user liking the strategy")


class CommentRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user commenting")
    user_name: str = Field("anonymous", description="Display name of the commenter")
    body: str = Field(..., min_length=1, description="Comment text")


class FollowRequest(BaseModel):
    follower_id: str = Field(..., description="ID of the user following")


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Social Feed FastAPI application."""
    app = FastAPI(
        title="Social Feed API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("social-feed-api", check_deps))

    strategies_router = APIRouter(prefix="/strategies", tags=["Share"])
    feed_router = APIRouter(prefix="/feed", tags=["Feed"])
    users_router = APIRouter(prefix="/users", tags=["Users"])

    # --- Share a strategy ---

    @strategies_router.post("/{strategy_id}/share", status_code=201)
    async def share_strategy(strategy_id: str, body: ShareStrategyRequest):
        # Verify the strategy spec exists
        async with db_pool.acquire() as conn:
            spec = await conn.fetchrow(
                "SELECT id FROM strategy_specs WHERE id = $1::uuid", strategy_id
            )
            if not spec:
                return not_found("Strategy", strategy_id)

            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO shared_strategies
                        (strategy_id, author_id, author_name, caption)
                    VALUES ($1::uuid, $2, $3, $4)
                    RETURNING id, strategy_id, author_id, author_name, caption,
                              like_count, comment_count, shared_at
                    """,
                    strategy_id,
                    body.author_id,
                    body.author_name,
                    body.caption,
                )
            except asyncpg.UniqueViolationError:
                return conflict(
                    f"Strategy '{strategy_id}' is already shared"
                )
            except Exception as e:
                logger.error("Failed to share strategy: %s", e)
                return server_error(str(e))

        item = dict(row)
        item["id"] = str(item["id"])
        item["strategy_id"] = str(item["strategy_id"])
        if item.get("shared_at"):
            item["shared_at"] = item["shared_at"].isoformat()
        return success_response(
            item, "shared_strategy", resource_id=item["id"], status_code=201
        )

    # --- Community feed ---

    @feed_router.get("")
    async def list_feed(
        pagination: PaginationParams = Depends(),
        author_id: Optional[str] = Query(None, description="Filter by author"),
    ):
        query = """
            SELECT ss.id, ss.strategy_id, ss.author_id, ss.author_name,
                   ss.caption, ss.like_count, ss.comment_count, ss.shared_at,
                   sp.name AS strategy_name, sp.description AS strategy_description
            FROM shared_strategies ss
            JOIN strategy_specs sp ON sp.id = ss.strategy_id
            WHERE ($1::text IS NULL OR ss.author_id = $1)
            ORDER BY ss.shared_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*) FROM shared_strategies ss
            WHERE ($1::text IS NULL OR ss.author_id = $1)
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                query, author_id, pagination.limit, pagination.offset
            )
            total = await conn.fetchval(count_query, author_id)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["strategy_id"] = str(item["strategy_id"])
            if item.get("shared_at"):
                item["shared_at"] = item["shared_at"].isoformat()
            items.append(item)
        return collection_response(
            items,
            "shared_strategy",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # --- Like / unlike ---

    @feed_router.post("/{shared_id}/like")
    async def toggle_like(shared_id: str, body: LikeRequest):
        async with db_pool.acquire() as conn:
            shared = await conn.fetchrow(
                "SELECT id FROM shared_strategies WHERE id = $1::uuid", shared_id
            )
            if not shared:
                return not_found("SharedStrategy", shared_id)

            existing = await conn.fetchrow(
                """
                SELECT id FROM feed_likes
                WHERE shared_strategy_id = $1::uuid AND user_id = $2
                """,
                shared_id,
                body.user_id,
            )

            if existing:
                # Unlike
                await conn.execute(
                    "DELETE FROM feed_likes WHERE id = $1::uuid",
                    str(existing["id"]),
                )
                await conn.execute(
                    """
                    UPDATE shared_strategies
                    SET like_count = GREATEST(like_count - 1, 0)
                    WHERE id = $1::uuid
                    """,
                    shared_id,
                )
                return success_response(
                    {"shared_strategy_id": shared_id, "liked": False},
                    "like_toggle",
                )
            else:
                # Like
                await conn.execute(
                    """
                    INSERT INTO feed_likes (shared_strategy_id, user_id)
                    VALUES ($1::uuid, $2)
                    """,
                    shared_id,
                    body.user_id,
                )
                await conn.execute(
                    """
                    UPDATE shared_strategies SET like_count = like_count + 1
                    WHERE id = $1::uuid
                    """,
                    shared_id,
                )
                return success_response(
                    {"shared_strategy_id": shared_id, "liked": True},
                    "like_toggle",
                )

    # --- Comments ---

    @feed_router.post("/{shared_id}/comment", status_code=201)
    async def add_comment(shared_id: str, body: CommentRequest):
        async with db_pool.acquire() as conn:
            shared = await conn.fetchrow(
                "SELECT id FROM shared_strategies WHERE id = $1::uuid", shared_id
            )
            if not shared:
                return not_found("SharedStrategy", shared_id)

            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO feed_comments
                        (shared_strategy_id, user_id, user_name, body)
                    VALUES ($1::uuid, $2, $3, $4)
                    RETURNING id, shared_strategy_id, user_id, user_name, body, created_at
                    """,
                    shared_id,
                    body.user_id,
                    body.user_name,
                    body.body,
                )
                await conn.execute(
                    """
                    UPDATE shared_strategies SET comment_count = comment_count + 1
                    WHERE id = $1::uuid
                    """,
                    shared_id,
                )
            except Exception as e:
                logger.error("Failed to add comment: %s", e)
                return server_error(str(e))

        item = dict(row)
        item["id"] = str(item["id"])
        item["shared_strategy_id"] = str(item["shared_strategy_id"])
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return success_response(
            item, "comment", resource_id=item["id"], status_code=201
        )

    @feed_router.get("/{shared_id}/comments")
    async def list_comments(
        shared_id: str,
        pagination: PaginationParams = Depends(),
    ):
        async with db_pool.acquire() as conn:
            shared = await conn.fetchrow(
                "SELECT id FROM shared_strategies WHERE id = $1::uuid", shared_id
            )
            if not shared:
                return not_found("SharedStrategy", shared_id)

            rows = await conn.fetch(
                """
                SELECT id, shared_strategy_id, user_id, user_name, body, created_at
                FROM feed_comments
                WHERE shared_strategy_id = $1::uuid
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                shared_id,
                pagination.limit,
                pagination.offset,
            )
            total = await conn.fetchval(
                """
                SELECT COUNT(*) FROM feed_comments
                WHERE shared_strategy_id = $1::uuid
                """,
                shared_id,
            )

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["shared_strategy_id"] = str(item["shared_strategy_id"])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)
        return collection_response(
            items,
            "comment",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    # --- Follow system ---

    @users_router.post("/{user_id}/follow")
    async def toggle_follow(user_id: str, body: FollowRequest):
        if body.follower_id == user_id:
            from services.rest_api_shared.responses import validation_error

            return validation_error("Cannot follow yourself")

        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT id FROM user_follows
                WHERE follower_id = $1 AND followed_id = $2
                """,
                body.follower_id,
                user_id,
            )

            if existing:
                # Unfollow
                await conn.execute(
                    "DELETE FROM user_follows WHERE id = $1::uuid",
                    str(existing["id"]),
                )
                return success_response(
                    {"follower_id": body.follower_id, "followed_id": user_id, "following": False},
                    "follow_toggle",
                )
            else:
                # Follow
                await conn.execute(
                    """
                    INSERT INTO user_follows (follower_id, followed_id)
                    VALUES ($1, $2)
                    """,
                    body.follower_id,
                    user_id,
                )
                return success_response(
                    {"follower_id": body.follower_id, "followed_id": user_id, "following": True},
                    "follow_toggle",
                )

    # --- Following feed (filtered by who user follows) ---

    @feed_router.get("/following")
    async def following_feed(
        user_id: str = Query(..., description="ID of the user viewing their feed"),
        pagination: PaginationParams = Depends(),
    ):
        query = """
            SELECT ss.id, ss.strategy_id, ss.author_id, ss.author_name,
                   ss.caption, ss.like_count, ss.comment_count, ss.shared_at,
                   sp.name AS strategy_name, sp.description AS strategy_description
            FROM shared_strategies ss
            JOIN strategy_specs sp ON sp.id = ss.strategy_id
            WHERE ss.author_id IN (
                SELECT followed_id FROM user_follows WHERE follower_id = $1
            )
            ORDER BY ss.shared_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*) FROM shared_strategies ss
            WHERE ss.author_id IN (
                SELECT followed_id FROM user_follows WHERE follower_id = $1
            )
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                query, user_id, pagination.limit, pagination.offset
            )
            total = await conn.fetchval(count_query, user_id)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["strategy_id"] = str(item["strategy_id"])
            if item.get("shared_at"):
                item["shared_at"] = item["shared_at"].isoformat()
            items.append(item)
        return collection_response(
            items,
            "shared_strategy",
            total=total,
            limit=pagination.limit,
            offset=pagination.offset,
        )

    app.include_router(strategies_router)
    app.include_router(feed_router)
    app.include_router(users_router)
    return app
