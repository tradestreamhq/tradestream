"""
Trade Journal REST API — RMM Level 2.

Provides CRUD endpoints for trade journal entries with emotion tracking,
ratings, lessons learned, and analytics (stats, streaks, calendar heatmap).
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

    @app.post("/entries", tags=["Journal"])
    async def create_entry(body: CreateJournalEntry):
        """Create a journal entry for a trade."""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO trade_journal
                        (trade_id, entry_notes, exit_notes, emotion_tag,
                         lesson_learned, rating)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING *
                    """,
                    body.trade_id,
                    body.entry_notes or "",
                    body.exit_notes or "",
                    body.emotion_tag,
                    body.lesson_learned or "",
                    body.rating,
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

            return success_response(entry, "journal_entry", resource_id=entry_id)
        except Exception:
            logger.exception("Failed to create journal entry")
            return server_error("Failed to create journal entry")

    # --- List (paginated, filterable) ---

    @app.get("/entries", tags=["Journal"])
    async def list_entries(
        pagination: PaginationParams = Query(),
        emotion: Optional[str] = Query(None, description="Filter by emotion_tag"),
        rating: Optional[int] = Query(
            None, ge=1, le=5, description="Filter by rating"
        ),
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

    @app.get("/entries/{entry_id}", tags=["Journal"])
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
            return success_response(
                entry, "journal_entry", resource_id=str(entry_id)
            )
        except Exception:
            logger.exception("Failed to get journal entry")
            return server_error("Failed to get journal entry")

    # --- Update ---

    @app.put("/entries/{entry_id}", tags=["Journal"])
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

            return success_response(
                entry, "journal_entry", resource_id=str(entry_id)
            )
        except Exception:
            logger.exception("Failed to update journal entry")
            return server_error("Failed to update journal entry")

    # --- Stats: win rate by emotion, avg PnL by rating, common mistakes ---

    @app.get("/stats", tags=["Analytics"])
    async def get_stats():
        """Analytics: win rate by emotion, avg PnL by rating, most common mistakes."""
        emotion_query = """
            SELECT
                tj.emotion_tag,
                COUNT(*)::int AS total_trades,
                SUM(CASE WHEN pt.pnl > 0 THEN 1 ELSE 0 END)::int AS wins,
                SUM(CASE WHEN pt.pnl <= 0 THEN 1 ELSE 0 END)::int AS losses,
                ROUND(AVG(pt.pnl)::numeric, 4) AS avg_pnl,
                ROUND(SUM(pt.pnl)::numeric, 4) AS total_pnl
            FROM trade_journal tj
            JOIN paper_trades pt ON pt.id = tj.trade_id
            WHERE tj.emotion_tag IS NOT NULL
              AND pt.status = 'CLOSED'
            GROUP BY tj.emotion_tag
            ORDER BY total_trades DESC
        """
        rating_query = """
            SELECT
                tj.rating,
                COUNT(*)::int AS total_trades,
                ROUND(AVG(pt.pnl)::numeric, 4) AS avg_pnl,
                ROUND(SUM(pt.pnl)::numeric, 4) AS total_pnl
            FROM trade_journal tj
            JOIN paper_trades pt ON pt.id = tj.trade_id
            WHERE tj.rating IS NOT NULL
              AND pt.status = 'CLOSED'
            GROUP BY tj.rating
            ORDER BY tj.rating
        """
        mistakes_query = """
            SELECT
                jt.tag,
                COUNT(*)::int AS occurrences,
                ROUND(AVG(pt.pnl)::numeric, 4) AS avg_pnl
            FROM journal_tags jt
            JOIN trade_journal tj ON tj.id = jt.journal_id
            JOIN paper_trades pt ON pt.id = tj.trade_id
            WHERE pt.pnl < 0 AND pt.status = 'CLOSED'
            GROUP BY jt.tag
            ORDER BY occurrences DESC
            LIMIT 10
        """
        try:
            async with db_pool.acquire() as conn:
                emotion_rows = await conn.fetch(emotion_query)
                rating_rows = await conn.fetch(rating_query)
                mistake_rows = await conn.fetch(mistakes_query)

            win_rate_by_emotion = []
            for row in emotion_rows:
                item = dict(row)
                total = item["total_trades"]
                item["win_rate"] = (
                    round(item["wins"] / total, 4) if total > 0 else 0
                )
                for key in ("avg_pnl", "total_pnl"):
                    if item[key] is not None:
                        item[key] = float(item[key])
                win_rate_by_emotion.append(item)

            avg_pnl_by_rating = []
            for row in rating_rows:
                item = dict(row)
                for key in ("avg_pnl", "total_pnl"):
                    if item[key] is not None:
                        item[key] = float(item[key])
                avg_pnl_by_rating.append(item)

            common_mistakes = []
            for row in mistake_rows:
                item = dict(row)
                if item["avg_pnl"] is not None:
                    item["avg_pnl"] = float(item["avg_pnl"])
                common_mistakes.append(item)

            return success_response(
                {
                    "win_rate_by_emotion": win_rate_by_emotion,
                    "avg_pnl_by_rating": avg_pnl_by_rating,
                    "common_mistakes": common_mistakes,
                },
                "journal_stats",
            )
        except Exception:
            logger.exception("Failed to get journal stats")
            return server_error("Failed to get journal stats")

    # --- Streaks: winning/losing streaks with context ---

    @app.get("/streaks", tags=["Analytics"])
    async def get_streaks():
        """Get winning/losing streaks with context."""
        query = """
            SELECT
                pt.id AS trade_id,
                pt.symbol,
                pt.pnl,
                pt.closed_at,
                tj.emotion_tag,
                tj.rating
            FROM paper_trades pt
            LEFT JOIN trade_journal tj ON tj.trade_id = pt.id
            WHERE pt.status = 'CLOSED'
            ORDER BY pt.closed_at ASC
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query)

            trades = []
            for row in rows:
                item = dict(row)
                if item.get("trade_id"):
                    item["trade_id"] = str(item["trade_id"])
                if item.get("pnl") is not None:
                    item["pnl"] = float(item["pnl"])
                if item.get("closed_at"):
                    item["closed_at"] = item["closed_at"].isoformat()
                trades.append(item)

            empty_streak = {"type": "none", "length": 0, "trades": []}
            if not trades:
                return success_response(
                    {
                        "current_streak": empty_streak,
                        "longest_winning_streak": {"length": 0, "trades": []},
                        "longest_losing_streak": {"length": 0, "trades": []},
                    },
                    "journal_streaks",
                )

            streaks = []
            current_type = None
            current_trades: list = []

            for trade in trades:
                pnl = trade.get("pnl", 0) or 0
                trade_type = "winning" if pnl > 0 else "losing"

                if trade_type == current_type:
                    current_trades.append(trade)
                else:
                    if current_trades:
                        streaks.append(
                            {
                                "type": current_type,
                                "length": len(current_trades),
                                "trades": current_trades,
                            }
                        )
                    current_type = trade_type
                    current_trades = [trade]

            if current_trades:
                streaks.append(
                    {
                        "type": current_type,
                        "length": len(current_trades),
                        "trades": current_trades,
                    }
                )

            current_streak = streaks[-1] if streaks else empty_streak

            winning_streaks = [s for s in streaks if s["type"] == "winning"]
            losing_streaks = [s for s in streaks if s["type"] == "losing"]

            longest_win = (
                max(winning_streaks, key=lambda s: s["length"])
                if winning_streaks
                else {"length": 0, "trades": []}
            )
            longest_loss = (
                max(losing_streaks, key=lambda s: s["length"])
                if losing_streaks
                else {"length": 0, "trades": []}
            )

            return success_response(
                {
                    "current_streak": current_streak,
                    "longest_winning_streak": longest_win,
                    "longest_losing_streak": longest_loss,
                },
                "journal_streaks",
            )
        except Exception:
            logger.exception("Failed to get streaks")
            return server_error("Failed to get streaks")

    # --- Calendar: PnL by day heatmap data ---

    @app.get("/calendar", tags=["Analytics"])
    async def get_calendar(
        date_from: Optional[datetime] = Query(None, description="Start date"),
        date_to: Optional[datetime] = Query(None, description="End date"),
    ):
        """Calendar heatmap data — PnL aggregated by day."""
        conditions = ["pt.status = 'CLOSED'", "pt.closed_at IS NOT NULL"]
        params: list = []
        idx = 1

        if date_from:
            conditions.append(f"pt.closed_at >= ${idx}")
            params.append(date_from)
            idx += 1
        if date_to:
            conditions.append(f"pt.closed_at <= ${idx}")
            params.append(date_to)
            idx += 1

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT
                DATE(pt.closed_at) AS date,
                COUNT(*)::int AS trade_count,
                SUM(CASE WHEN pt.pnl > 0 THEN 1 ELSE 0 END)::int AS wins,
                SUM(CASE WHEN pt.pnl <= 0 THEN 1 ELSE 0 END)::int AS losses,
                ROUND(SUM(pt.pnl)::numeric, 4) AS daily_pnl
            FROM paper_trades pt
            {where}
            GROUP BY DATE(pt.closed_at)
            ORDER BY date
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

            days = []
            for row in rows:
                item = dict(row)
                if item.get("date"):
                    item["date"] = item["date"].isoformat()
                if item.get("daily_pnl") is not None:
                    item["daily_pnl"] = float(item["daily_pnl"])
                days.append(item)

            return collection_response(days, "calendar_day")
        except Exception:
            logger.exception("Failed to get calendar data")
            return server_error("Failed to get calendar data")

    return app
