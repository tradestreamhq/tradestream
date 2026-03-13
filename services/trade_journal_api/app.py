"""
Trade Journal REST API — RMM Level 2.

Provides CRUD endpoints for trade journal entries with emotion tracking,
ratings, lessons learned, tags, screenshots, and analytics.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
from fastapi import FastAPI, Query
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

VALID_EMOTIONS = {"confident", "fearful", "neutral", "greedy"}


# --- Request DTOs ---


class CreateJournalEntry(BaseModel):
    trade_id: Optional[UUID] = Field(None, description="Link to a paper_trades row")
    entry_notes: Optional[str] = Field("", description="Notes at entry time")
    exit_notes: Optional[str] = Field("", description="Notes at exit time")
    emotion_tag: Optional[str] = Field(
        None,
        description="Emotion during trade: confident, fearful, neutral, greedy",
        pattern="^(confident|fearful|neutral|greedy)$",
    )
    lesson_learned: Optional[str] = Field("", description="Lesson from this trade")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Self-rating 1-5")
    tags: Optional[List[str]] = Field(
        default_factory=list, description="Arbitrary tags"
    )
    screenshots_urls: Optional[List[str]] = Field(
        default_factory=list, description="URLs to trade screenshots"
    )


class UpdateJournalEntry(BaseModel):
    entry_notes: Optional[str] = Field(None, description="Update entry notes")
    exit_notes: Optional[str] = Field(None, description="Update exit notes")
    emotion_tag: Optional[str] = Field(
        None,
        description="Update emotion tag",
        pattern="^(confident|fearful|neutral|greedy)$",
    )
    lesson_learned: Optional[str] = Field(None, description="Update lesson")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Update rating")
    tags: Optional[List[str]] = Field(None, description="Replace tags")
    screenshots_urls: Optional[List[str]] = Field(
        None, description="Replace screenshot URLs"
    )


# --- Helpers ---


def _row_to_dict(row: dict) -> Dict[str, Any]:
    """Convert a database row to a JSON-serializable dict."""
    item = dict(row)
    for key in ("id", "trade_id"):
        if key in item and item[key] is not None:
            item[key] = str(item[key])
    for key in ("created_at", "updated_at"):
        if key in item and item[key] is not None:
            item[key] = item[key].isoformat()
    if "screenshots_urls" in item and item["screenshots_urls"] is not None:
        item["screenshots_urls"] = list(item["screenshots_urls"])
    return item


# --- Application Factory ---


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Trade Journal API FastAPI application."""
    app = FastAPI(
        title="Trade Journal API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/journal",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("trade-journal-api", check_deps))

    # --- Create ---

    @app.post("", tags=["Journal"], status_code=201)
    async def create_entry(body: CreateJournalEntry):
        """Create a journal entry for a trade."""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO trade_journal
                        (trade_id, entry_notes, exit_notes, emotion_tag,
                         lesson_learned, rating, screenshots_urls)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING *
                    """,
                    body.trade_id,
                    body.entry_notes or "",
                    body.exit_notes or "",
                    body.emotion_tag,
                    body.lesson_learned or "",
                    body.rating,
                    body.screenshots_urls or [],
                )
                entry = _row_to_dict(row)
                entry_id = entry["id"]

                tags = body.tags or []
                if tags:
                    await conn.executemany(
                        "INSERT INTO journal_tags (journal_id, tag) VALUES ($1, $2)",
                        [(row["id"], t) for t in tags],
                    )
                entry["tags"] = tags

            return success_response(
                entry, "journal_entry", resource_id=entry_id, status_code=201
            )
        except Exception:
            logger.exception("Failed to create journal entry")
            return server_error("Failed to create journal entry")

    # --- List (paginated, filterable) ---

    @app.get("", tags=["Journal"])
    async def list_entries(
        pagination: PaginationParams = Query(),
        emotion: Optional[str] = Query(None, description="Filter by emotion_tag"),
        rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by rating"),
        tag: Optional[str] = Query(None, description="Filter by tag"),
        date_from: Optional[datetime] = Query(
            None, description="Entries created on or after"
        ),
        date_to: Optional[datetime] = Query(
            None, description="Entries created on or before"
        ),
    ):
        """List journal entries with optional filters."""
        conditions = []
        params: list = []
        idx = 1

        if emotion:
            conditions.append(f"tj.emotion_tag = ${idx}")
            params.append(emotion)
            idx += 1
        if rating is not None:
            conditions.append(f"tj.rating = ${idx}")
            params.append(rating)
            idx += 1
        if date_from:
            conditions.append(f"tj.created_at >= ${idx}")
            params.append(date_from)
            idx += 1
        if date_to:
            conditions.append(f"tj.created_at <= ${idx}")
            params.append(date_to)
            idx += 1
        if tag:
            conditions.append(
                f"EXISTS (SELECT 1 FROM journal_tags jt WHERE jt.journal_id = tj.id AND jt.tag = ${idx})"
            )
            params.append(tag)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        count_query = f"SELECT COUNT(*) FROM trade_journal tj {where}"
        data_query = f"""
            SELECT tj.* FROM trade_journal tj
            {where}
            ORDER BY tj.created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([pagination.limit, pagination.offset])

        try:
            async with db_pool.acquire() as conn:
                total = await conn.fetchval(count_query, *params[:-2])
                rows = await conn.fetch(data_query, *params)

                entries = []
                for row in rows:
                    entry = _row_to_dict(row)
                    tag_rows = await conn.fetch(
                        "SELECT tag FROM journal_tags WHERE journal_id = $1",
                        row["id"],
                    )
                    entry["tags"] = [r["tag"] for r in tag_rows]
                    entries.append(entry)

            return collection_response(
                entries,
                "journal_entry",
                total=total,
                limit=pagination.limit,
                offset=pagination.offset,
            )
        except Exception:
            logger.exception("Failed to list journal entries")
            return server_error("Failed to list journal entries")

    # --- Get by ID ---

    @app.get("/tags", tags=["Journal"])
    async def list_tags():
        """List all tags with entry counts."""
        query = """
            SELECT tag, COUNT(*)::int AS entry_count
            FROM journal_tags
            GROUP BY tag
            ORDER BY entry_count DESC, tag ASC
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query)
            items = [dict(row) for row in rows]
            return collection_response(items, "journal_tag", total=len(items))
        except Exception:
            logger.exception("Failed to list tags")
            return server_error("Failed to list tags")

    @app.get("/stats", tags=["Analytics"])
    async def get_stats():
        """Journaling stats: streaks, entries per week, most used tags."""
        streak_query = """
            SELECT DATE(created_at) AS entry_date
            FROM trade_journal
            ORDER BY entry_date DESC
        """
        weekly_query = """
            SELECT
                DATE_TRUNC('week', created_at)::date AS week_start,
                COUNT(*)::int AS entry_count
            FROM trade_journal
            GROUP BY week_start
            ORDER BY week_start DESC
            LIMIT 12
        """
        tags_query = """
            SELECT tag, COUNT(*)::int AS entry_count
            FROM journal_tags
            GROUP BY tag
            ORDER BY entry_count DESC
            LIMIT 10
        """
        emotion_query = """
            SELECT
                tj.emotion_tag,
                COUNT(*)::int AS total_trades,
                SUM(CASE WHEN pt.pnl > 0 THEN 1 ELSE 0 END)::int AS wins,
                SUM(CASE WHEN pt.pnl <= 0 THEN 1 ELSE 0 END)::int AS losses,
                ROUND(AVG(pt.pnl)::numeric, 4) AS avg_pnl
            FROM trade_journal tj
            JOIN paper_trades pt ON pt.id = tj.trade_id
            WHERE tj.emotion_tag IS NOT NULL
              AND pt.status = 'CLOSED'
            GROUP BY tj.emotion_tag
            ORDER BY total_trades DESC
        """
        try:
            async with db_pool.acquire() as conn:
                streak_rows = await conn.fetch(streak_query)
                weekly_rows = await conn.fetch(weekly_query)
                tag_rows = await conn.fetch(tags_query)
                emotion_rows = await conn.fetch(emotion_query)

            # Compute journaling streak (consecutive days)
            current_streak = 0
            longest_streak = 0
            if streak_rows:
                dates = sorted(
                    set(row["entry_date"] for row in streak_rows), reverse=True
                )
                from datetime import date, timedelta

                today = date.today()
                if dates and (today - dates[0]).days <= 1:
                    streak = 1
                    for i in range(1, len(dates)):
                        if (dates[i - 1] - dates[i]).days == 1:
                            streak += 1
                        else:
                            break
                    current_streak = streak

                # Longest streak
                streak = 1
                for i in range(1, len(dates)):
                    if (dates[i - 1] - dates[i]).days == 1:
                        streak += 1
                    else:
                        longest_streak = max(longest_streak, streak)
                        streak = 1
                longest_streak = max(longest_streak, streak)

            entries_per_week = []
            for row in weekly_rows:
                item = dict(row)
                if item.get("week_start"):
                    item["week_start"] = item["week_start"].isoformat()
                entries_per_week.append(item)

            most_used_tags = [dict(row) for row in tag_rows]

            win_rate_by_emotion = []
            for row in emotion_rows:
                item = dict(row)
                total = item["total_trades"]
                item["win_rate"] = round(item["wins"] / total, 4) if total > 0 else 0
                if item["avg_pnl"] is not None:
                    item["avg_pnl"] = float(item["avg_pnl"])
                win_rate_by_emotion.append(item)

            return success_response(
                {
                    "current_streak": current_streak,
                    "longest_streak": longest_streak,
                    "entries_per_week": entries_per_week,
                    "most_used_tags": most_used_tags,
                    "win_rate_by_emotion": win_rate_by_emotion,
                },
                "journal_stats",
            )
        except Exception:
            logger.exception("Failed to get journal stats")
            return server_error("Failed to get journal stats")

    @app.get("/{entry_id}", tags=["Journal"])
    async def get_entry(entry_id: UUID):
        """Get a single journal entry by ID."""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM trade_journal WHERE id = $1", entry_id
                )
                if not row:
                    return not_found("JournalEntry", str(entry_id))
                entry = _row_to_dict(row)
                tag_rows = await conn.fetch(
                    "SELECT tag FROM journal_tags WHERE journal_id = $1", entry_id
                )
                entry["tags"] = [r["tag"] for r in tag_rows]
            return success_response(entry, "journal_entry", resource_id=str(entry_id))
        except Exception:
            logger.exception("Failed to get journal entry")
            return server_error("Failed to get journal entry")

    # --- Update ---

    @app.put("/{entry_id}", tags=["Journal"])
    async def update_entry(entry_id: UUID, body: UpdateJournalEntry):
        """Update a journal entry."""
        try:
            async with db_pool.acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT id FROM trade_journal WHERE id = $1", entry_id
                )
                if not existing:
                    return not_found("JournalEntry", str(entry_id))

                set_clauses = ["updated_at = now()"]
                params: list = []
                idx = 1

                for field in (
                    "entry_notes",
                    "exit_notes",
                    "emotion_tag",
                    "lesson_learned",
                    "rating",
                ):
                    val = getattr(body, field, None)
                    if val is not None:
                        set_clauses.append(f"{field} = ${idx}")
                        params.append(val)
                        idx += 1

                if body.screenshots_urls is not None:
                    set_clauses.append(f"screenshots_urls = ${idx}")
                    params.append(body.screenshots_urls)
                    idx += 1

                params.append(entry_id)
                update_query = f"""
                    UPDATE trade_journal
                    SET {', '.join(set_clauses)}
                    WHERE id = ${idx}
                    RETURNING *
                """
                row = await conn.fetchrow(update_query, *params)
                entry = _row_to_dict(row)

                if body.tags is not None:
                    await conn.execute(
                        "DELETE FROM journal_tags WHERE journal_id = $1", entry_id
                    )
                    if body.tags:
                        await conn.executemany(
                            "INSERT INTO journal_tags (journal_id, tag) VALUES ($1, $2)",
                            [(entry_id, t) for t in body.tags],
                        )
                    entry["tags"] = body.tags
                else:
                    tag_rows = await conn.fetch(
                        "SELECT tag FROM journal_tags WHERE journal_id = $1",
                        entry_id,
                    )
                    entry["tags"] = [r["tag"] for r in tag_rows]

            return success_response(entry, "journal_entry", resource_id=str(entry_id))
        except Exception:
            logger.exception("Failed to update journal entry")
            return server_error("Failed to update journal entry")

    return app
