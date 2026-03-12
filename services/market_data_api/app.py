"""
Market Data REST API — RMM Level 2.

Provides endpoints for instruments, OHLCV candles, prices, and order books.
Backed by InfluxDB for candle data and Redis for symbol cache.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, Query

from services.rest_api_shared.circuit_breaker import CircuitBreaker
from services.rest_api_shared.error_middleware import install_error_handlers
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    server_error,
    success_response,
    validation_error,
)
from services.rest_api_shared.retry import retry_with_backoff
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
    install_error_handlers(app)

    redis_circuit = CircuitBreaker("redis", failure_threshold=5, recovery_timeout=15.0)
    influx_circuit = CircuitBreaker(
        "influxdb", failure_threshold=5, recovery_timeout=30.0
    )

    async def check_deps():
        deps = {}
        try:
            redis_client.get_symbols()
            deps["redis"] = "ok"
        except Exception as e:
            deps["redis"] = str(e)
        deps["redis_circuit"] = redis_circuit.state.value
        deps["influxdb_circuit"] = influx_circuit.state.value
        return deps

    app.include_router(create_health_router("market-data-api", check_deps))

    instruments_router = APIRouter(prefix="/instruments", tags=["Instruments"])

    # --- Instrument endpoints ---

    @instruments_router.get("")
    async def list_instruments():
        """List available instruments."""

        async def _fetch():
            return redis_client.get_symbols()

        try:
            symbols = await redis_circuit.call(
                retry_with_backoff, _fetch, operation_name="market.list_instruments"
            )
        except Exception:
            return server_error("Failed to retrieve instruments")

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

        async def _fetch():
            return influxdb_client.get_candles(
                symbol=symbol,
                timeframe=interval,
                start=start,
                limit=limit,
            )

        try:
            result = await influx_circuit.call(
                retry_with_backoff, _fetch, operation_name="market.get_candles"
            )
        except Exception:
            return server_error("Failed to retrieve candle data")

        if not result:
            return collection_response([], "candle")
        return collection_response(result, "candle")

    @instruments_router.get("/{symbol}/price")
    async def get_price(symbol: str):
        """Get current price for an instrument."""

        async def _fetch():
            return influxdb_client.get_latest_price(symbol=symbol)

        try:
            result = await influx_circuit.call(
                retry_with_backoff, _fetch, operation_name="market.get_price"
            )
        except Exception:
            return server_error("Failed to retrieve price data")

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
    return app
