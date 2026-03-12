"""
Trade Journal REST API — RMM Level 2.

Provides CRUD endpoints for trade journal entries with tagging,
full-text search, and aggregate statistics by tag.
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


# --- Request DTOs ---


class CreateJournalEntry(BaseModel):
    instrument: str = Field(..., description="Trading instrument symbol")
    side: str = Field(..., description="BUY or SELL", pattern="^(BUY|SELL)$")
    entry_price: float = Field(..., gt=0, description="Entry price")
    exit_price: Optional[float] = Field(None, gt=0, description="Exit price")
    size: float = Field(..., gt=0, description="Position size")
    pnl: Optional[float] = Field(None, description="Realized P&L")
    outcome: Optional[str] = Field(
        None, description="WIN, LOSS, or OPEN", pattern="^(WIN|LOSS|OPEN)$"
    )
    strategy_name: Optional[str] = Field(None, description="Strategy that generated the trade")
    signal_trigger: Optional[str] = Field(None, description="Signal that triggered the trade")
    notes: Optional[str] = Field("", description="User notes")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for the entry")
    opened_at: Optional[datetime] = Field(None, description="When the position was opened")
    closed_at: Optional[datetime] = Field(None, description="When the position was closed")


class UpdateJournalEntry(BaseModel):
    notes: Optional[str] = Field(None, description="Updated notes")
    tags: Optional[List[str]] = Field(None, description="Replace tags")
    exit_price: Optional[float] = Field(None, gt=0, description="Exit price")
    pnl: Optional[float] = Field(None, description="Realized P&L")
    outcome: Optional[str] = Field(
        None, description="WIN, LOSS, or OPEN", pattern="^(WIN|LOSS|OPEN)$"
    )
    closed_at: Optional[datetime] = Field(None, description="When the position was closed")


# --- Helpers ---


def _row_to_dict(row: dict) -> Dict[str, Any]:
    """Convert a database row to a JSON-serializable dict."""
    item = dict(row)
    for key in ("id", "entry_id"):
        if key in item and item[key] is not None:
            item[key] = str(item[key])
    for key in ("entry_price", "exit_price", "size", "pnl"):
        if key in item and item[key] is not None:
            item[key] = float(item[key])
    for key in ("opened_at", "closed_at", "created_at", "updated_at"):
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
        """Create a new journal entry (auto-called on position open/close)."""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO journal_entries
                        (instrument, side, entry_price, exit_price, size, pnl,
                         outcome, strategy_name, signal_trigger, notes, opened_at, closed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            COALESCE($11, now()), $12)
                    RETURNING *
                    """,
                    body.instrument,
                    body.side,
                    body.entry_price,
                    body.exit_price,
                    body.size,
                    body.pnl,
                    body.outcome or "OPEN",
                    body.strategy_name,
                    body.signal_trigger,
                    body.notes or "",
                    body.opened_at,
                    body.closed_at,
                )
                entry = _row_to_dict(row)
                entry_id = entry["id"]

                # Insert tags
                tags = body.tags or []
                if tags:
                    await conn.executemany(
                        "INSERT INTO journal_tags (entry_id, tag) VALUES ($1, $2)",
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
        strategy: Optional[str] = Query(None, description="Filter by strategy name"),
        outcome: Optional[str] = Query(None, description="Filter by outcome"),
        date_from: Optional[datetime] = Query(None, description="Entries opened on or after"),
        date_to: Optional[datetime] = Query(None, description="Entries opened on or before"),
        tag: Optional[str] = Query(None, description="Filter by tag"),
        search: Optional[str] = Query(None, description="Search notes text"),
    ):
        """List journal entries with optional filters."""
        conditions = []
        params: list = []
        idx = 1

        if strategy:
            conditions.append(f"je.strategy_name = ${idx}")
            params.append(strategy)
            idx += 1
        if outcome:
            conditions.append(f"je.outcome = ${idx}")
            params.append(outcome)
            idx += 1
        if date_from:
            conditions.append(f"je.opened_at >= ${idx}")
            params.append(date_from)
            idx += 1
        if date_to:
            conditions.append(f"je.opened_at <= ${idx}")
            params.append(date_to)
            idx += 1
        if tag:
            conditions.append(
                f"EXISTS (SELECT 1 FROM journal_tags jt WHERE jt.entry_id = je.id AND jt.tag = ${idx})"
            )
            params.append(tag)
            idx += 1
        if search:
            conditions.append(f"je.notes ILIKE ${idx}")
            params.append(f"%{search}%")
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        count_query = f"SELECT COUNT(*) FROM journal_entries je {where}"
        data_query = f"""
            SELECT je.* FROM journal_entries je
            {where}
            ORDER BY je.opened_at DESC
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
                        "SELECT tag FROM journal_tags WHERE entry_id = $1", row["id"]
                    )
                    entry["tags"] = [r["tag"] for r in tag_rows]
                    entries.append(entry)

            return collection_response(
                entries, "journal_entry", total=total,
                limit=pagination.limit, offset=pagination.offset,
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
                    "SELECT * FROM journal_entries WHERE id = $1", entry_id
                )
                if not row:
                    return not_found("JournalEntry", str(entry_id))
                entry = _row_to_dict(row)
                tag_rows = await conn.fetch(
                    "SELECT tag FROM journal_tags WHERE entry_id = $1", entry_id
                )
                entry["tags"] = [r["tag"] for r in tag_rows]
            return success_response(entry, "journal_entry", resource_id=str(entry_id))
        except Exception:
            logger.exception("Failed to get journal entry")
            return server_error("Failed to get journal entry")

    # --- Update (add notes/tags) ---

    @app.patch("/entries/{entry_id}", tags=["Journal"])
    async def update_entry(entry_id: UUID, body: UpdateJournalEntry):
        """Update a journal entry — add notes, tags, or close with exit price/P&L."""
        try:
            async with db_pool.acquire() as conn:
                existing = await conn.fetchrow(
                    "SELECT id FROM journal_entries WHERE id = $1", entry_id
                )
                if not existing:
                    return not_found("JournalEntry", str(entry_id))

                set_clauses = ["updated_at = now()"]
                params: list = []
                idx = 1

                for field in ("notes", "exit_price", "pnl", "outcome", "closed_at"):
                    val = getattr(body, field, None)
                    if val is not None:
                        set_clauses.append(f"{field} = ${idx}")
                        params.append(val)
                        idx += 1

                params.append(entry_id)
                update_query = f"""
                    UPDATE journal_entries
                    SET {', '.join(set_clauses)}
                    WHERE id = ${idx}
                    RETURNING *
                """
                row = await conn.fetchrow(update_query, *params)
                entry = _row_to_dict(row)

                # Replace tags if provided
                if body.tags is not None:
                    await conn.execute(
                        "DELETE FROM journal_tags WHERE entry_id = $1", entry_id
                    )
                    if body.tags:
                        await conn.executemany(
                            "INSERT INTO journal_tags (entry_id, tag) VALUES ($1, $2)",
                            [(entry_id, t) for t in body.tags],
                        )
                    entry["tags"] = body.tags
                else:
                    tag_rows = await conn.fetch(
                        "SELECT tag FROM journal_tags WHERE entry_id = $1", entry_id
                    )
                    entry["tags"] = [r["tag"] for r in tag_rows]

            return success_response(entry, "journal_entry", resource_id=str(entry_id))
        except Exception:
            logger.exception("Failed to update journal entry")
            return server_error("Failed to update journal entry")

    # --- Stats by tag ---

    @app.get("/stats", tags=["Journal"])
    async def get_stats():
        """Aggregate stats grouped by tag: win rate, avg P&L."""
        query = """
            SELECT
                jt.tag,
                COUNT(*)::int                                                AS total_trades,
                SUM(CASE WHEN je.outcome = 'WIN' THEN 1 ELSE 0 END)::int   AS wins,
                SUM(CASE WHEN je.outcome = 'LOSS' THEN 1 ELSE 0 END)::int  AS losses,
                ROUND(AVG(je.pnl)::numeric, 4)                              AS avg_pnl,
                ROUND(SUM(je.pnl)::numeric, 4)                              AS total_pnl
            FROM journal_tags jt
            JOIN journal_entries je ON je.id = jt.entry_id
            WHERE je.outcome IN ('WIN', 'LOSS')
            GROUP BY jt.tag
            ORDER BY total_trades DESC
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query)

            stats = []
            for row in rows:
                item = dict(row)
                total = item["total_trades"]
                item["win_rate"] = round(item["wins"] / total, 4) if total > 0 else 0
                for key in ("avg_pnl", "total_pnl"):
                    if item[key] is not None:
                        item[key] = float(item[key])
                stats.append(item)

            return collection_response(stats, "journal_stats")
        except Exception:
            logger.exception("Failed to get journal stats")
            return server_error("Failed to get journal stats")

    return app
