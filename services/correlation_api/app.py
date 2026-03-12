"""
Correlation Analysis REST API — RMM Level 2.

Computes and monitors correlations between trading strategies
and across asset pairs. Detects correlation regime changes.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
import numpy as np
from fastapi import APIRouter, FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

VALID_WINDOWS = (30, 60, 90)
REGIME_CHANGE_THRESHOLD = 0.3
REGIME_LOOKBACK_DAYS = 5


def _compute_correlation_matrix(
    returns: Dict[str, List[float]],
) -> Dict[str, Dict[str, float]]:
    """Compute pairwise Pearson correlation matrix from return series.

    Args:
        returns: mapping of name -> list of daily returns (same length).

    Returns:
        nested dict of correlations, e.g. {"A": {"A": 1.0, "B": 0.5}, ...}
    """
    names = sorted(returns.keys())
    if not names:
        return {}

    n = len(names)
    min_len = min(len(returns[k]) for k in names)
    if min_len < 2:
        return {a: {b: 0.0 for b in names} for a in names}

    matrix = np.zeros((n, min_len))
    for i, name in enumerate(names):
        matrix[i] = returns[name][:min_len]

    corr = np.corrcoef(matrix)
    # Handle NaN from constant series
    corr = np.nan_to_num(corr, nan=0.0)

    result = {}
    for i, a in enumerate(names):
        result[a] = {}
        for j, b in enumerate(names):
            result[a][b] = round(float(corr[i, j]), 6)
    return result


def _detect_regime_changes(
    current: Dict[str, Dict[str, float]],
    previous: Dict[str, Dict[str, float]],
    threshold: float = REGIME_CHANGE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Compare two correlation matrices and return pairs with significant shifts."""
    alerts = []
    seen = set()
    for a in current:
        for b in current.get(a, {}):
            if a == b:
                continue
            pair = tuple(sorted([a, b]))
            if pair in seen:
                continue
            seen.add(pair)
            cur_val = current[a][b]
            prev_val = previous.get(a, {}).get(b)
            if prev_val is None:
                continue
            change = abs(cur_val - prev_val)
            if change >= threshold:
                alerts.append(
                    {
                        "pair": list(pair),
                        "previous_correlation": round(prev_val, 6),
                        "current_correlation": round(cur_val, 6),
                        "absolute_change": round(change, 6),
                    }
                )
    return alerts


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Correlation API FastAPI application."""
    app = FastAPI(
        title="Correlation API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/correlations",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("correlation-api", check_deps))

    # --- Strategy correlations ---

    @app.get("/strategies", tags=["Correlations"])
    async def get_strategy_correlations(
        window: int = Query(60, description="Rolling window in days"),
    ):
        """Get current correlation matrix between strategy returns."""
        if window not in VALID_WINDOWS:
            return validation_error(
                f"window must be one of {VALID_WINDOWS}",
            )

        query = """
            SELECT sp.strategy_id,
                   sp.metric_date,
                   sp.daily_return
            FROM strategy_daily_returns sp
            WHERE sp.metric_date >= CURRENT_DATE - $1::int
            ORDER BY sp.strategy_id, sp.metric_date
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, window)
        except Exception as exc:
            logger.exception("Failed to fetch strategy returns")
            return server_error(str(exc))

        returns: Dict[str, List[float]] = {}
        for row in rows:
            sid = str(row["strategy_id"])
            returns.setdefault(sid, []).append(float(row["daily_return"]))

        matrix = _compute_correlation_matrix(returns)

        # Persist snapshot
        await _save_snapshot(db_pool, "strategy", window, matrix)

        return success_response(
            {
                "window": window,
                "matrix": matrix,
                "strategies": sorted(returns.keys()),
            },
            "strategy_correlations",
        )

    # --- Cross-asset correlations ---

    @app.get("/assets", tags=["Correlations"])
    async def get_asset_correlations(
        window: int = Query(60, description="Rolling window in days"),
    ):
        """Get cross-asset correlation matrix for portfolio diversification."""
        if window not in VALID_WINDOWS:
            return validation_error(
                f"window must be one of {VALID_WINDOWS}",
            )

        query = """
            SELECT symbol,
                   metric_date,
                   daily_return
            FROM asset_daily_returns
            WHERE metric_date >= CURRENT_DATE - $1::int
            ORDER BY symbol, metric_date
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, window)
        except Exception as exc:
            logger.exception("Failed to fetch asset returns")
            return server_error(str(exc))

        returns: Dict[str, List[float]] = {}
        for row in rows:
            sym = row["symbol"]
            returns.setdefault(sym, []).append(float(row["daily_return"]))

        matrix = _compute_correlation_matrix(returns)

        await _save_snapshot(db_pool, "asset", window, matrix)

        return success_response(
            {
                "window": window,
                "matrix": matrix,
                "assets": sorted(returns.keys()),
            },
            "asset_correlations",
        )

    # --- Regime change alerts ---

    @app.get("/alerts", tags=["Alerts"])
    async def get_correlation_alerts(
        limit: int = Query(50, ge=1, le=200, description="Max alerts to return"),
    ):
        """Get recent correlation regime change alerts."""
        query = """
            SELECT id, correlation_type, pair_a, pair_b,
                   previous_correlation, current_correlation,
                   absolute_change, detected_at
            FROM correlation_regime_alerts
            ORDER BY detected_at DESC
            LIMIT $1
        """
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(query, limit)
        except Exception as exc:
            logger.exception("Failed to fetch alerts")
            return server_error(str(exc))

        items = []
        for row in rows:
            item = dict(row)
            item["id"] = str(item["id"])
            item["previous_correlation"] = float(item["previous_correlation"])
            item["current_correlation"] = float(item["current_correlation"])
            item["absolute_change"] = float(item["absolute_change"])
            if item.get("detected_at"):
                item["detected_at"] = item["detected_at"].isoformat()
            items.append(item)

        return collection_response(items, "correlation_alert")

    # --- Snapshot helper ---

    async def _save_snapshot(
        pool: asyncpg.Pool,
        correlation_type: str,
        window: int,
        matrix: Dict[str, Dict[str, float]],
    ):
        """Store a correlation snapshot and check for regime changes."""
        now = datetime.now(timezone.utc)
        insert_q = """
            INSERT INTO correlation_snapshots
                (correlation_type, window_days, matrix_json, computed_at)
            VALUES ($1, $2, $3, $4)
        """
        previous_q = """
            SELECT matrix_json FROM correlation_snapshots
            WHERE correlation_type = $1
              AND window_days = $2
              AND computed_at < $3
            ORDER BY computed_at DESC
            LIMIT 1
        """
        alert_q = """
            INSERT INTO correlation_regime_alerts
                (correlation_type, pair_a, pair_b,
                 previous_correlation, current_correlation,
                 absolute_change, detected_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """

        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    insert_q,
                    correlation_type,
                    window,
                    json.dumps(matrix),
                    now,
                )
                prev_row = await conn.fetchrow(
                    previous_q, correlation_type, window, now
                )
                if prev_row:
                    prev_matrix = json.loads(prev_row["matrix_json"])
                    changes = _detect_regime_changes(matrix, prev_matrix)
                    for alert in changes:
                        await conn.execute(
                            alert_q,
                            correlation_type,
                            alert["pair"][0],
                            alert["pair"][1],
                            alert["previous_correlation"],
                            alert["current_correlation"],
                            alert["absolute_change"],
                            now,
                        )
        except Exception:
            logger.exception("Failed to save correlation snapshot")

    return app
