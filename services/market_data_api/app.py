"""
Market Data REST API — RMM Level 2.

Provides endpoints for instruments, OHLCV candles, prices, and order books.
Backed by InfluxDB for candle data and Redis for symbol cache.
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
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(influxdb_client, redis_client) -> FastAPI:
    """Create the Market Data API FastAPI application.

    Args:
        influxdb_client: InfluxDB client for candle/price queries.
        redis_client: Redis client for symbol cache.
    """
    app = FastAPI(
        title="Market Data API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/market",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        deps = {}
        try:
            redis_client.get_symbols()
            deps["redis"] = "ok"
        except Exception as e:
            deps["redis"] = str(e)
        return deps

    app.include_router(create_health_router("market-data-api", check_deps))

    instruments_router = APIRouter(prefix="/instruments", tags=["Instruments"])

    # --- Instrument endpoints ---

    @instruments_router.get("")
    async def list_instruments():
        """List available instruments."""
        symbols = redis_client.get_symbols()
        items = [{"symbol": s} for s in symbols]
        return collection_response(items, "instrument")

    @instruments_router.get("/{symbol}/candles")
    async def get_candles(
        symbol: str,
        interval: str = Query(
            ...,
            description="Candle interval",
            regex="^(1m|5m|15m|1h|4h|1d)$",
        ),
        limit: int = Query(100, ge=1, le=1000, description="Max candles to return"),
        start: Optional[str] = Query(
            None, alias="from", description="Start time (RFC3339 or relative e.g. -1h)"
        ),
    ):
        """Get OHLCV candles for an instrument."""
        result = influxdb_client.get_candles(
            symbol=symbol,
            timeframe=interval,
            start=start,
            limit=limit,
        )
        if not result:
            return collection_response([], "candle")
        return collection_response(result, "candle")

    @instruments_router.get("/{symbol}/price")
    async def get_price(symbol: str):
        """Get current price for an instrument."""
        result = influxdb_client.get_latest_price(symbol=symbol)
        if not result:
            return not_found("Price", symbol)
        return success_response(result, "price", resource_id=symbol)

    @instruments_router.get("/{symbol}/orderbook")
    async def get_orderbook(
        symbol: str,
        depth: int = Query(10, ge=1, le=100, description="Order book depth"),
    ):
        """Get order book for an instrument.

        Note: Order book data is currently a placeholder.
        Full order book support requires a live exchange connection.
        """
        return success_response(
            {
                "symbol": symbol,
                "depth": depth,
                "bids": [],
                "asks": [],
                "message": "Order book requires live exchange connection",
            },
            "orderbook",
            resource_id=symbol,
        )

    app.include_router(instruments_router)

    # --- Candle aggregation endpoints ---
    candles_router = APIRouter(prefix="/candles", tags=["Candles"])

    @candles_router.get("/{pair}")
    async def get_candles_by_pair(
        pair: str,
        timeframe: str = Query(
            "1m",
            description="Candle timeframe",
            regex="^(1m|5m|15m|1h|4h|1d)$",
        ),
        start: Optional[str] = Query(
            None, alias="from", description="Start time (RFC3339 or relative e.g. -1h)"
        ),
        end: Optional[str] = Query(
            None, alias="to", description="End time (RFC3339 or relative)"
        ),
        limit: int = Query(100, ge=1, le=1000, description="Max candles to return"),
    ):
        """Get historical OHLCV candles for a trading pair."""
        result = influxdb_client.get_candles(
            symbol=pair,
            timeframe=timeframe,
            start=start,
            limit=limit,
        )
        if not result:
            return collection_response([], "candle")
        return collection_response(result, "candle")

    @candles_router.get("/{pair}/latest")
    async def get_latest_candles(
        pair: str,
        timeframe: str = Query(
            "1m",
            description="Candle timeframe",
            regex="^(1m|5m|15m|1h|4h|1d)$",
        ),
        count: int = Query(10, ge=1, le=100, description="Number of latest candles"),
    ):
        """Get latest N candles for a trading pair."""
        result = influxdb_client.get_candles(
            symbol=pair,
            timeframe=timeframe,
            start=f"-{count * _timeframe_minutes(timeframe)}m",
            limit=count,
        )
        if not result:
            return collection_response([], "candle")
        return collection_response(result, "candle")

    app.include_router(candles_router)
    return app


def _timeframe_minutes(timeframe: str) -> int:
    """Convert a timeframe label to minutes for relative time calculation."""
    mapping = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
    return mapping.get(timeframe, 1)
