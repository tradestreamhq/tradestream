"""Volatility Regime REST API — RMM Level 2.

Provides an endpoint to classify current market volatility regime
based on realized volatility of daily close prices.
"""

import logging
from typing import Optional

from fastapi import APIRouter, FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    error_response,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware
from services.volatility_regime.classifier import VolatilityRegimeClassifier

logger = logging.getLogger(__name__)


def create_app(
    influxdb_client, classifier: Optional[VolatilityRegimeClassifier] = None
) -> FastAPI:
    """Create the Volatility Regime API FastAPI application.

    Args:
        influxdb_client: InfluxDB client for fetching candle data.
        classifier: Optional pre-configured classifier instance.
    """
    app = FastAPI(
        title="Volatility Regime API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/market",
    )
    fastapi_auth_middleware(app)

    _classifier = classifier or VolatilityRegimeClassifier()

    async def check_deps():
        return {"influxdb": "ok"}

    app.include_router(create_health_router("volatility-regime-api", check_deps))

    regime_router = APIRouter(prefix="/volatility-regime", tags=["Volatility Regime"])

    @regime_router.get("")
    async def get_volatility_regime(
        symbol: str = Query(..., description="Instrument symbol (e.g. BTC/USD)"),
    ):
        """Classify the current volatility regime for a symbol.

        Returns regime (low/medium/high), realized volatility metrics,
        and recent regime transitions.
        """
        try:
            candles = influxdb_client.get_candles(
                symbol=symbol,
                timeframe="1d",
                start="-90d",
                limit=90,
            )
        except Exception as e:
            logger.exception("Failed to fetch candles for %s", symbol)
            return error_response(
                code="DATA_FETCH_ERROR",
                message=f"Failed to fetch market data for {symbol}",
                status_code=502,
            )

        if not candles:
            return error_response(
                code="INSUFFICIENT_DATA",
                message=f"No candle data available for {symbol}",
                status_code=404,
            )

        daily_closes = [c["close"] for c in candles if "close" in c]

        if len(daily_closes) < 3:
            return error_response(
                code="INSUFFICIENT_DATA",
                message=f"Not enough price data for {symbol} to compute volatility",
                status_code=422,
            )

        result = _classifier.classify(symbol, daily_closes)
        return success_response(
            result.model_dump(),
            "volatility-regime",
            resource_id=symbol,
        )

    app.include_router(regime_router)
    return app
