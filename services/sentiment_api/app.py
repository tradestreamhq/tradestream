"""
Sentiment Analysis REST API — RMM Level 2.

Provides endpoints for market sentiment based on order book imbalance,
trade flow, whale detection, and funding rate data.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)
from services.sentiment_api.analyzer import SentimentAnalyzer
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(data_provider, analyzer: Optional[SentimentAnalyzer] = None) -> FastAPI:
    """Create the Sentiment API FastAPI application.

    Args:
        data_provider: Object providing market data methods:
            - get_order_book(pair, levels) -> dict with "bids" and "asks"
            - get_recent_trades(pair, window_seconds) -> list of trade dicts
            - get_funding_rate(pair) -> float or None
            - get_sentiment_history(pair, limit) -> list of snapshot dicts
            - get_whale_trades(pair, limit, threshold) -> list of trade dicts
        analyzer: Optional SentimentAnalyzer instance. Creates default if None.
    """
    app = FastAPI(
        title="Sentiment Analysis API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/sentiment",
    )
    fastapi_auth_middleware(app)

    if analyzer is None:
        analyzer = SentimentAnalyzer()

    async def check_deps():
        deps = {}
        try:
            data_provider.health_check()
            deps["data_provider"] = "ok"
        except Exception as e:
            deps["data_provider"] = str(e)
        return deps

    app.include_router(create_health_router("sentiment-api", check_deps))

    sentiment_router = APIRouter(tags=["Sentiment"])

    @sentiment_router.get("/{pair}")
    async def get_sentiment(
        pair: str,
        levels: int = Query(10, ge=1, le=100, description="Order book depth levels"),
        window: int = Query(
            300, ge=10, le=3600, description="Trade flow window in seconds"
        ),
    ):
        """Get current sentiment snapshot for a trading pair."""
        order_book = data_provider.get_order_book(pair, levels)
        if order_book is None:
            return not_found("Pair", pair)

        bids = [
            (float(b["price"]), float(b["size"])) for b in order_book.get("bids", [])
        ]
        asks = [
            (float(a["price"]), float(a["size"])) for a in order_book.get("asks", [])
        ]

        trades = data_provider.get_recent_trades(pair, window)
        funding_rate = data_provider.get_funding_rate(pair)

        snapshot = analyzer.compute_snapshot(
            pair=pair,
            bids=bids,
            asks=asks,
            trades=trades,
            funding_rate=funding_rate,
            levels=levels,
            window_seconds=window,
        )

        return success_response(
            snapshot.to_dict(), "sentiment_snapshot", resource_id=pair
        )

    @sentiment_router.get("/{pair}/history")
    async def get_sentiment_history(
        pair: str,
        limit: int = Query(50, ge=1, le=500, description="Max snapshots to return"),
        offset: int = Query(0, ge=0, description="Pagination offset"),
    ):
        """Get historical sentiment snapshots for a trading pair."""
        history = data_provider.get_sentiment_history(pair, limit=limit, offset=offset)
        if history is None:
            return not_found("Pair", pair)

        return collection_response(
            history,
            "sentiment_snapshot",
            limit=limit,
            offset=offset,
        )

    @sentiment_router.get("/{pair}/whale-trades")
    async def get_whale_trades(
        pair: str,
        limit: int = Query(50, ge=1, le=500, description="Max trades to return"),
        threshold: Optional[float] = Query(
            None, ge=0, description="Min notional value (defaults to analyzer config)"
        ),
    ):
        """Get recent large (whale) trades for a trading pair."""
        whale_trades = data_provider.get_whale_trades(
            pair, limit=limit, threshold=threshold
        )
        if whale_trades is None:
            return not_found("Pair", pair)

        return collection_response(whale_trades, "whale_trade")

    app.include_router(sentiment_router)
    return app
