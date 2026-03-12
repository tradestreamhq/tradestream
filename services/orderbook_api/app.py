"""
Order Book REST API — RMM Level 2.

Provides endpoints for Level 2 order book snapshots, spread data,
bid/ask imbalance, and historical spread/imbalance time series.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import FastAPI, Query

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


def _parse_levels(raw):
    """Parse bids/asks from JSON string or native list."""
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def create_app(db_pool: asyncpg.Pool) -> FastAPI:
    """Create the Order Book API FastAPI application."""
    app = FastAPI(
        title="Order Book API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/orderbook",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"postgres": "ok"}
        except Exception as e:
            return {"postgres": str(e)}

    app.include_router(
        create_health_router("orderbook-api", check_deps)
    )

    # --- Current snapshot ---

    @app.get("/orderbook/{symbol}", tags=["Order Book"])
    async def get_orderbook(
        symbol: str,
        depth: int = Query(
            default=10,
            ge=1,
            le=100,
            description="Number of price levels",
        ),
        exchange: Optional[str] = Query(
            default=None, description="Filter by exchange"
        ),
    ):
        """Get current order book snapshot (top N levels)."""
        query = """
            SELECT id, symbol, exchange, bids, asks,
                   timestamp, sequence_number
            FROM orderbook_snapshots
            WHERE symbol = $1
        """
        params: list = [symbol]
        if exchange:
            query += " AND exchange = $2"
            params.append(exchange)
        query += " ORDER BY timestamp DESC LIMIT 1"

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return not_found("Order book", symbol)

        bids = _parse_levels(row["bids"])
        asks = _parse_levels(row["asks"])

        # Trim to requested depth
        bids = bids[:depth]
        asks = asks[:depth]

        return success_response(
            {
                "symbol": row["symbol"],
                "exchange": row["exchange"],
                "bids": bids,
                "asks": asks,
                "depth": len(bids),
                "timestamp": row["timestamp"].isoformat(),
                "sequence_number": row["sequence_number"],
            },
            "orderbook",
            resource_id=symbol,
        )

    # --- Spread ---

    @app.get("/orderbook/{symbol}/spread", tags=["Order Book"])
    async def get_spread(
        symbol: str,
        exchange: Optional[str] = Query(
            default=None, description="Filter by exchange"
        ),
    ):
        """Get bid-ask spread, mid price, and spread percentage."""
        query = """
            SELECT symbol, exchange, bids, asks, timestamp
            FROM orderbook_snapshots
            WHERE symbol = $1
        """
        params: list = [symbol]
        if exchange:
            query += " AND exchange = $2"
            params.append(exchange)
        query += " ORDER BY timestamp DESC LIMIT 1"

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return not_found("Order book", symbol)

        bids = _parse_levels(row["bids"])
        asks = _parse_levels(row["asks"])

        if not bids or not asks:
            return success_response(
                {
                    "symbol": row["symbol"],
                    "exchange": row["exchange"],
                    "best_bid": None,
                    "best_ask": None,
                    "spread": None,
                    "mid_price": None,
                    "spread_percentage": None,
                    "timestamp": row["timestamp"].isoformat(),
                },
                "spread",
                resource_id=symbol,
            )

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        spread_pct = (
            (spread / mid_price * 100) if mid_price > 0 else 0
        )

        return success_response(
            {
                "symbol": row["symbol"],
                "exchange": row["exchange"],
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": round(spread, 8),
                "mid_price": round(mid_price, 8),
                "spread_percentage": round(spread_pct, 6),
                "timestamp": row["timestamp"].isoformat(),
            },
            "spread",
            resource_id=symbol,
        )

    # --- Imbalance ---

    @app.get("/orderbook/{symbol}/imbalance", tags=["Order Book"])
    async def get_imbalance(
        symbol: str,
        depth: int = Query(
            default=10,
            ge=1,
            le=100,
            description="Levels to include",
        ),
        exchange: Optional[str] = Query(
            default=None, description="Filter by exchange"
        ),
    ):
        """Get bid/ask volume imbalance ratio.

        Imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol).
        Range: -1 (all ask) to +1 (all bid). 0 = balanced.
        """
        query = """
            SELECT symbol, exchange, bids, asks, timestamp
            FROM orderbook_snapshots
            WHERE symbol = $1
        """
        params: list = [symbol]
        if exchange:
            query += " AND exchange = $2"
            params.append(exchange)
        query += " ORDER BY timestamp DESC LIMIT 1"

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)

        if not row:
            return not_found("Order book", symbol)

        bids = _parse_levels(row["bids"])
        asks = _parse_levels(row["asks"])

        bids = bids[:depth]
        asks = asks[:depth]

        bid_volume = sum(level[1] for level in bids)
        ask_volume = sum(level[1] for level in asks)
        total_volume = bid_volume + ask_volume

        imbalance = (
            (bid_volume - ask_volume) / total_volume
            if total_volume > 0
            else 0
        )

        return success_response(
            {
                "symbol": row["symbol"],
                "exchange": row["exchange"],
                "bid_volume": bid_volume,
                "ask_volume": ask_volume,
                "total_volume": total_volume,
                "imbalance": round(imbalance, 6),
                "depth": depth,
                "timestamp": row["timestamp"].isoformat(),
            },
            "imbalance",
            resource_id=symbol,
        )

    # --- Historical spread & imbalance ---

    @app.get("/orderbook/{symbol}/history", tags=["Order Book"])
    async def get_history(
        symbol: str,
        interval: str = Query(
            default="1m",
            description="Aggregation interval: 1m, 5m, 15m, 1h",
        ),
        limit: int = Query(
            default=60,
            ge=1,
            le=1000,
            description="Max data points",
        ),
        exchange: Optional[str] = Query(
            default=None, description="Filter by exchange"
        ),
    ):
        """Historical spread/imbalance time series."""
        interval_map = {
            "1m": "1 minute",
            "5m": "5 minutes",
            "15m": "15 minutes",
            "1h": "1 hour",
        }
        pg_interval = interval_map.get(interval)
        if not pg_interval:
            supported = ", ".join(interval_map.keys())
            return validation_error(
                f"Invalid interval '{interval}'."
                f" Supported: {supported}"
            )

        query = f"""
            SELECT
                date_trunc('minute', timestamp)
                - (
                    EXTRACT(MINUTE FROM timestamp)::int
                    % EXTRACT(
                        MINUTE FROM INTERVAL '{pg_interval}'
                    )::int
                ) * INTERVAL '1 minute' AS bucket,
                AVG(spread) AS avg_spread,
                AVG(mid_price) AS avg_mid_price,
                AVG(spread_percentage)
                    AS avg_spread_percentage,
                AVG(imbalance) AS avg_imbalance,
                COUNT(*) AS sample_count
            FROM orderbook_history
            WHERE symbol = $1
        """
        params: list = [symbol]
        if exchange:
            query += " AND exchange = $2"
            params.append(exchange)

        query += f"""
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT ${len(params) + 1}
        """
        params.append(limit)

        async with db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        items = []
        for row in rows:
            avg_spread = row["avg_spread"]
            avg_mid = row["avg_mid_price"]
            avg_spct = row["avg_spread_percentage"]
            avg_imb = row["avg_imbalance"]
            items.append(
                {
                    "timestamp": row["bucket"].isoformat(),
                    "avg_spread": (
                        float(avg_spread)
                        if avg_spread
                        else None
                    ),
                    "avg_mid_price": (
                        float(avg_mid) if avg_mid else None
                    ),
                    "avg_spread_percentage": (
                        float(avg_spct) if avg_spct else None
                    ),
                    "avg_imbalance": (
                        float(avg_imb) if avg_imb else None
                    ),
                    "sample_count": row["sample_count"],
                }
            )

        # Return in chronological order
        items.reverse()
        return collection_response(
            items, "orderbook_history", limit=limit
        )

    return app
