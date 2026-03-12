"""
Correlation Matrix REST API — RMM Level 2.

Provides endpoints for computing and monitoring pairwise asset correlations
for portfolio diversification analysis.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, FastAPI, Query

from services.correlation_matrix.calculator import (
    build_correlation_matrix,
    detect_breakdowns,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.pagination import PaginationParams
from services.rest_api_shared.responses import (
    collection_response,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)

# Window sizes in calendar days
WINDOW_DAYS = {"30d": 30, "90d": 90}


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Correlation Matrix API FastAPI application."""
    app = FastAPI(
        title="Correlation Matrix API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/analytics",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(create_health_router("correlation-matrix", check_deps))

    router = APIRouter(prefix="/correlations", tags=["Correlations"])

    async def _fetch_prices(
        conn: asyncpg.Connection,
        symbols: List[str],
        window_days: int,
    ) -> Dict[str, List[float]]:
        """Fetch daily closing prices for symbols over the given window."""
        query = """
            SELECT symbol, close, bucket
            FROM (
                SELECT symbol,
                       close,
                       time_bucket('1 day', time) AS bucket
                FROM candles
                WHERE symbol = ANY($1)
                  AND time >= NOW() - ($2 || ' days')::interval
                ORDER BY symbol, bucket
            ) sub
        """
        rows = await conn.fetch(query, symbols, str(window_days))
        prices: Dict[str, List[float]] = {s: [] for s in symbols}
        for row in rows:
            sym = row["symbol"]
            if sym in prices:
                prices[sym].append(float(row["close"]))
        return prices

    @router.get("")
    async def get_correlations(
        symbols: Optional[str] = Query(
            None,
            description="Comma-separated list of symbols (e.g. BTC,ETH,SOL)",
        ),
        symbol_a: Optional[str] = Query(
            None, description="Filter by first symbol in pair"
        ),
        symbol_b: Optional[str] = Query(
            None, description="Filter by second symbol in pair"
        ),
        window: str = Query(
            "30d",
            description="Rolling window",
            pattern="^(30d|90d)$",
        ),
    ):
        """Get correlation matrix or pairwise correlations.

        If `symbols` is provided, returns the full matrix.
        If `symbol_a` and `symbol_b` are provided, returns a single pair.
        """
        window_days = WINDOW_DAYS.get(window)
        if window_days is None:
            return validation_error(f"Invalid window: {window}. Use 30d or 90d.")

        # Determine symbol list
        if symbols:
            sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        elif symbol_a and symbol_b:
            sym_list = [symbol_a.upper(), symbol_b.upper()]
        else:
            # Default: fetch all tracked symbols from recent candles
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT symbol FROM candles
                    WHERE time >= NOW() - INTERVAL '7 days'
                    ORDER BY symbol
                    LIMIT 50
                    """
                )
            sym_list = [row["symbol"] for row in rows]

        if len(sym_list) < 2:
            return validation_error(
                "At least 2 symbols are required to compute correlations."
            )

        try:
            async with db_pool.acquire() as conn:
                prices = await _fetch_prices(conn, sym_list, window_days)

            matrix = build_correlation_matrix(sym_list, prices, window_days)

            # If specific pair requested, return just that pair
            if symbol_a and symbol_b:
                a, b = symbol_a.upper(), symbol_b.upper()
                corr_value = matrix.get(a, {}).get(b)
                return success_response(
                    {
                        "symbol_a": a,
                        "symbol_b": b,
                        "correlation": corr_value,
                        "window": window,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    resource_type="correlation_pair",
                    resource_id=f"{a}_{b}_{window}",
                )

            return success_response(
                {
                    "symbols": sym_list,
                    "window": window,
                    "matrix": matrix,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                resource_type="correlation_matrix",
            )
        except Exception as e:
            logger.error("Failed to compute correlations: %s", e)
            return server_error(str(e))

    @router.get("/breakdowns")
    async def get_breakdowns(
        symbols: Optional[str] = Query(
            None,
            description="Comma-separated list of symbols",
        ),
        window: str = Query(
            "30d",
            description="Rolling window",
            pattern="^(30d|90d)$",
        ),
        threshold: float = Query(
            0.3,
            ge=0.0,
            le=1.0,
            description="Minimum absolute change to flag as breakdown",
        ),
        pagination: PaginationParams = Depends(),
    ):
        """Detect correlation regime changes.

        Compares the current short-window correlations against a longer
        historical baseline to find significant shifts.
        """
        window_days = WINDOW_DAYS.get(window)
        if window_days is None:
            return validation_error(f"Invalid window: {window}. Use 30d or 90d.")

        # Use 2x window as the historical baseline
        historical_days = window_days * 2

        if symbols:
            sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        else:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT symbol FROM candles
                    WHERE time >= NOW() - INTERVAL '7 days'
                    ORDER BY symbol
                    LIMIT 50
                    """
                )
            sym_list = [row["symbol"] for row in rows]

        if len(sym_list) < 2:
            return validation_error(
                "At least 2 symbols are required to detect breakdowns."
            )

        try:
            async with db_pool.acquire() as conn:
                current_prices = await _fetch_prices(conn, sym_list, window_days)
                historical_prices = await _fetch_prices(
                    conn, sym_list, historical_days
                )

            current_matrix = build_correlation_matrix(
                sym_list, current_prices, window_days
            )
            historical_matrix = build_correlation_matrix(
                sym_list, historical_prices, historical_days
            )

            all_breakdowns = detect_breakdowns(
                current_matrix,
                historical_matrix,
                sym_list,
                window,
                threshold=threshold,
            )

            # Apply pagination
            total = len(all_breakdowns)
            page = all_breakdowns[
                pagination.offset : pagination.offset + pagination.limit
            ]

            return collection_response(
                page,
                "correlation_breakdown",
                total=total,
                limit=pagination.limit,
                offset=pagination.offset,
            )
        except Exception as e:
            logger.error("Failed to detect breakdowns: %s", e)
            return server_error(str(e))

    app.include_router(router)
    return app
