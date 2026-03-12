"""
Market Regime Detection REST API.

Provides endpoints for classifying current market conditions into regimes
(trending_up, trending_down, range_bound, high_volatility, low_volatility, crisis)
to inform strategy selection.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, FastAPI, Query

from services.market_regime.regime_detector import RegimeDetector
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(influxdb_client, regime_detector: Optional[RegimeDetector] = None) -> FastAPI:
    """Create the Market Regime API FastAPI application.

    Args:
        influxdb_client: InfluxDB client for fetching candle data.
        regime_detector: Optional pre-configured RegimeDetector instance.
    """
    app = FastAPI(
        title="Market Regime API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/market",
    )
    fastapi_auth_middleware(app)

    detector = regime_detector or RegimeDetector()

    async def check_deps():
        deps = {}
        try:
            influxdb_client.get_candles(symbol="BTC/USD", timeframe="1d", limit=1)
            deps["influxdb"] = "ok"
        except Exception as e:
            deps["influxdb"] = str(e)
        return deps

    app.include_router(create_health_router("market-regime-api", check_deps))

    regime_router = APIRouter(prefix="/regime", tags=["Regime"])

    @regime_router.get("")
    async def get_regime(
        symbol: str = Query("BTC/USD", description="Symbol to classify"),
    ):
        """Get current market regime classification for a symbol."""
        candles = influxdb_client.get_candles(
            symbol=symbol, timeframe="1d", limit=300
        )
        if not candles:
            return not_found("Candle data", symbol)

        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        timestamps = []
        for c in candles:
            ts = c.get("time")
            if isinstance(ts, str):
                timestamps.append(
                    datetime.fromisoformat(ts.replace("Z", "+00:00"))
                )
            elif isinstance(ts, datetime):
                timestamps.append(ts)
            else:
                timestamps.append(datetime.now(timezone.utc))

        result = detector.classify(symbol, closes, highs, lows, timestamps)
        if result is None:
            return validation_error(
                f"Insufficient data for regime detection on {symbol}"
            )

        return success_response(
            {
                "symbol": result.symbol,
                "regime": result.regime.value,
                "confidence": result.confidence,
                "timestamp": result.timestamp.isoformat(),
                "indicators": result.indicators,
            },
            "regime",
            resource_id=symbol,
        )

    @regime_router.get("/history")
    async def get_regime_history(
        symbol: str = Query("BTC/USD", description="Symbol to query"),
        days: int = Query(90, ge=1, le=365, description="Number of days"),
    ):
        """Get historical regime timeline for a symbol."""
        history = detector.get_history(symbol, days)
        items = [
            {
                "regime": h.regime.value,
                "confidence": h.confidence,
                "timestamp": h.timestamp.isoformat(),
                "indicators": h.indicators,
            }
            for h in history
        ]
        return collection_response(items, "regime_history")

    @regime_router.get("/transitions")
    async def get_regime_transitions(
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
    ):
        """Get regime transition events."""
        transitions = detector.get_transitions(symbol)
        items = [
            {
                "symbol": t.symbol,
                "previous_regime": t.previous_regime.value,
                "new_regime": t.new_regime.value,
                "timestamp": t.timestamp.isoformat(),
                "confidence": t.confidence,
            }
            for t in transitions
        ]
        return collection_response(items, "regime_transition")

    app.include_router(regime_router)
    return app
