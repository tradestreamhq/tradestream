"""
Correlation and Pair Analysis REST API — RMM Level 2.

Provides endpoints for correlation matrices, pairwise correlation,
and cointegrated pair identification for pair trading strategies.
"""

import logging
from dataclasses import asdict
from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, FastAPI, Query

from services.correlation_engine.engine import (
    analyze_pair,
    correlation_matrix,
    find_cointegrated_pairs,
    rolling_correlation,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(price_provider) -> FastAPI:
    """Create the Correlation Engine FastAPI application.

    Args:
        price_provider: Object providing price data with methods:
            - get_symbols() -> List[str]
            - get_prices(symbol, limit) -> List[dict] with 'close' and 'time' keys
    """
    app = FastAPI(
        title="Correlation Engine API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/correlation",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        deps = {}
        try:
            price_provider.get_symbols()
            deps["price_provider"] = "ok"
        except Exception as e:
            deps["price_provider"] = str(e)
        return deps

    app.include_router(create_health_router("correlation-engine", check_deps))

    correlation_router = APIRouter(tags=["Correlation"])
    pairs_router = APIRouter(prefix="/pairs", tags=["Pairs"])

    def _build_price_df(
        symbols: List[str], limit: int = 200
    ) -> Optional[pd.DataFrame]:
        """Build a DataFrame of close prices for the given symbols."""
        frames = {}
        for sym in symbols:
            prices = price_provider.get_prices(sym, limit=limit)
            if prices:
                frames[sym] = pd.Series(
                    [p["close"] for p in prices],
                    index=[p["time"] for p in prices],
                    dtype=float,
                )
        if not frames:
            return None
        return pd.DataFrame(frames).dropna()

    @correlation_router.get("/matrix")
    async def get_correlation_matrix(
        symbols: Optional[str] = Query(
            None,
            description="Comma-separated symbols (default: all available)",
        ),
        limit: int = Query(
            200, ge=30, le=1000, description="Number of price points to use"
        ),
    ):
        """Compute NxN correlation matrix for all or specified asset pairs."""
        syms = (
            [s.strip() for s in symbols.split(",")]
            if symbols
            else price_provider.get_symbols()
        )

        if len(syms) < 2:
            return validation_error("At least 2 symbols are required")

        df = _build_price_df(syms, limit=limit)
        if df is None or len(df.columns) < 2:
            return validation_error("Insufficient price data for correlation")

        matrix = correlation_matrix(df)
        result = {
            "symbols": list(matrix.columns),
            "matrix": matrix.values.tolist(),
        }
        return success_response(result, "correlation_matrix")

    @correlation_router.get("/{pair1}/{pair2}")
    async def get_pairwise_correlation(
        pair1: str,
        pair2: str,
        window: int = Query(
            30, ge=5, le=200, description="Rolling window size"
        ),
        limit: int = Query(
            200, ge=30, le=1000, description="Number of price points"
        ),
    ):
        """Get pairwise correlation with rolling window and pair analysis."""
        df = _build_price_df([pair1, pair2], limit=limit)
        if df is None or pair1 not in df.columns or pair2 not in df.columns:
            return not_found("Price data", f"{pair1}/{pair2}")

        if len(df) < window:
            return validation_error(
                f"Need at least {window} data points, got {len(df)}"
            )

        rolling = rolling_correlation(df[pair1], df[pair2], window=window)
        analysis = analyze_pair(
            pair1,
            pair2,
            df[pair1].values,
            df[pair2].values,
            zscore_window=window,
        )

        result = {
            **asdict(analysis),
            "rolling_correlation": [
                round(v, 6) if not np.isnan(v) else None
                for v in rolling.values.tolist()
            ],
            "window": window,
            "data_points": len(df),
        }
        return success_response(result, "pair_correlation", resource_id=f"{pair1}/{pair2}")

    @pairs_router.get("/cointegrated")
    async def get_cointegrated_pairs(
        symbols: Optional[str] = Query(
            None,
            description="Comma-separated symbols (default: all available)",
        ),
        significance: float = Query(
            0.05, ge=0.001, le=0.5, description="P-value threshold"
        ),
        limit: int = Query(
            200, ge=30, le=1000, description="Number of price points"
        ),
    ):
        """List cointegrated pairs suitable for pair trading."""
        syms = (
            [s.strip() for s in symbols.split(",")]
            if symbols
            else price_provider.get_symbols()
        )

        if len(syms) < 2:
            return validation_error("At least 2 symbols are required")

        df = _build_price_df(syms, limit=limit)
        if df is None or len(df.columns) < 2:
            return validation_error("Insufficient price data")

        pairs = find_cointegrated_pairs(df, significance=significance)
        items = [asdict(p) for p in pairs]
        return collection_response(items, "cointegrated_pair")

    app.include_router(correlation_router)
    app.include_router(pairs_router)
    return app
