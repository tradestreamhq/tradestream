"""
Signal Quality REST API — Phase 4.

Provides endpoints for:
- Retrieving signal quality scores
- Signal performance dashboard data (win rates, recent outcomes, strategy rankings)
"""

import logging
from typing import Optional

import asyncpg
from fastapi import FastAPI, Query

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
        title="Signal Quality API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/signal-quality",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("signal-quality-api", check_deps))

    # ------------------------------------------------------------------
    # Quality scores
    # ------------------------------------------------------------------

    @app.get("/scores", tags=["Quality"])
    async def get_quality_scores(
        strategy: Optional[str] = Query(None),
        grade: Optional[str] = Query(None, pattern="^[A-F]$"),
        limit: int = Query(50, ge=1, le=200),
    ):
        """Get recent signal quality scores, optionally filtered."""
        conditions = []
        params = []
        idx = 1

        if strategy:
            conditions.append(f"strategy_name = ${idx}")
            params.append(strategy)
            idx += 1
        if grade:
            conditions.append(f"quality_grade = ${idx}")
            params.append(grade)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)

        query = f"""
            SELECT id, signal_id, strategy_name, symbol, confidence,
                   indicator_agreement, volume_confirmation,
                   trend_alignment, volatility_context,
                   quality_grade, created_at
            FROM signal_quality_scores
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx}
        """
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["signal_id"] = str(item["signal_id"])
            for k in (
                "confidence",
                "indicator_agreement",
                "volume_confirmation",
                "trend_alignment",
                "volatility_context",
            ):
                if item.get(k) is not None:
                    item[k] = float(item[k])
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            items.append(item)
        return collection_response(items, "quality_score")

    # ------------------------------------------------------------------
    # Performance dashboard
    # ------------------------------------------------------------------

    @app.get("/dashboard", tags=["Dashboard"])
    async def get_dashboard():
        """Get signal performance dashboard data: win rates, rankings, recent outcomes."""
        async with db_pool.acquire() as conn:
            # Strategy rankings by win rate
            rankings = await conn.fetch(
                """
                SELECT strategy_name, total_signals, wins, losses, pending,
                       win_rate, avg_pnl_percent, avg_confidence, last_signal_at
                FROM strategy_performance_summary
                WHERE total_signals >= 5
                ORDER BY win_rate DESC, avg_pnl_percent DESC
                LIMIT 20
            """
            )

            # Recent signal outcomes
            recent = await conn.fetch(
                """
                SELECT id, signal_id, strategy_name, symbol, direction,
                       entry_price, exit_price, pnl_percent, outcome,
                       quality_grade, opened_at, closed_at
                FROM signal_outcomes
                ORDER BY opened_at DESC
                LIMIT 20
            """
            )

            # Overall stats
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) AS total_signals,
                    COUNT(*) FILTER (WHERE outcome = 'WIN') AS total_wins,
                    COUNT(*) FILTER (WHERE outcome = 'LOSS') AS total_losses,
                    ROUND(
                        COUNT(*) FILTER (WHERE outcome = 'WIN')::numeric
                        / NULLIF(COUNT(*) FILTER (WHERE outcome IN ('WIN', 'LOSS')), 0)
                        * 100, 2
                    ) AS overall_win_rate,
                    ROUND(COALESCE(AVG(pnl_percent) FILTER (
                        WHERE outcome IN ('WIN', 'LOSS')), 0), 4) AS avg_return
                FROM signal_outcomes
            """
            )

            # Grade distribution
            grades = await conn.fetch(
                """
                SELECT quality_grade, COUNT(*) AS count
                FROM signal_quality_scores
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY quality_grade
                ORDER BY quality_grade
            """
            )

        def fmt_ranking(r):
            d = dict(r)
            for k in ("win_rate", "avg_pnl_percent", "avg_confidence"):
                if d.get(k) is not None:
                    d[k] = float(d[k])
            if d.get("last_signal_at"):
                d["last_signal_at"] = d["last_signal_at"].isoformat()
            return d

        def fmt_outcome(r):
            d = dict(r)
            d["id"] = str(d["id"])
            d["signal_id"] = str(d["signal_id"])
            for k in ("entry_price", "exit_price", "pnl_percent"):
                if d.get(k) is not None:
                    d[k] = float(d[k])
            for k in ("opened_at", "closed_at"):
                if d.get(k):
                    d[k] = d[k].isoformat()
            return d

        dashboard = {
            "overall": {
                "total_signals": stats["total_signals"] if stats else 0,
                "total_wins": stats["total_wins"] if stats else 0,
                "total_losses": stats["total_losses"] if stats else 0,
                "win_rate": (
                    float(stats["overall_win_rate"])
                    if stats and stats["overall_win_rate"]
                    else 0.0
                ),
                "avg_return": (
                    float(stats["avg_return"]) if stats and stats["avg_return"] else 0.0
                ),
            },
            "strategy_rankings": [fmt_ranking(r) for r in rankings],
            "recent_outcomes": [fmt_outcome(r) for r in recent],
            "grade_distribution": {r["quality_grade"]: r["count"] for r in grades},
        }

        return success_response(dashboard, "dashboard")

    # ------------------------------------------------------------------
    # Per-strategy detail
    # ------------------------------------------------------------------

    @app.get("/strategy/{strategy_name}", tags=["Dashboard"])
    async def get_strategy_detail(strategy_name: str):
        """Get detailed performance for a specific strategy."""
        async with db_pool.acquire() as conn:
            summary = await conn.fetchrow(
                "SELECT * FROM strategy_performance_summary WHERE strategy_name = $1",
                strategy_name,
            )
            if not summary:
                return not_found("Strategy", strategy_name)

            recent_outcomes = await conn.fetch(
                """
                SELECT id, signal_id, symbol, direction, entry_price, exit_price,
                       pnl_percent, outcome, quality_grade, opened_at, closed_at
                FROM signal_outcomes
                WHERE strategy_name = $1
                ORDER BY opened_at DESC LIMIT 20
            """,
                strategy_name,
            )

            quality_dist = await conn.fetch(
                """
                SELECT quality_grade, COUNT(*) AS count,
                       ROUND(AVG(confidence)::numeric, 4) AS avg_confidence
                FROM signal_quality_scores
                WHERE strategy_name = $1
                GROUP BY quality_grade
                ORDER BY quality_grade
            """,
                strategy_name,
            )

        s = dict(summary)
        for k in ("win_rate", "avg_pnl_percent", "avg_confidence"):
            if s.get(k) is not None:
                s[k] = float(s[k])
        if s.get("last_signal_at"):
            s["last_signal_at"] = s["last_signal_at"].isoformat()
        if s.get("updated_at"):
            s["updated_at"] = s["updated_at"].isoformat()

        detail = {
            "summary": s,
            "recent_outcomes": [
                {
                    "id": str(r["id"]),
                    "signal_id": str(r["signal_id"]),
                    "symbol": r["symbol"],
                    "direction": r["direction"],
                    "entry_price": (
                        float(r["entry_price"]) if r["entry_price"] else None
                    ),
                    "exit_price": float(r["exit_price"]) if r["exit_price"] else None,
                    "pnl_percent": (
                        float(r["pnl_percent"]) if r["pnl_percent"] else None
                    ),
                    "outcome": r["outcome"],
                    "quality_grade": r["quality_grade"],
                    "opened_at": r["opened_at"].isoformat() if r["opened_at"] else None,
                    "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
                }
                for r in recent_outcomes
            ],
            "quality_distribution": [
                {
                    "grade": r["quality_grade"],
                    "count": r["count"],
                    "avg_confidence": (
                        float(r["avg_confidence"]) if r["avg_confidence"] else 0.0
                    ),
                }
                for r in quality_dist
            ],
        }

        return success_response(detail, "strategy_detail")

    return app
