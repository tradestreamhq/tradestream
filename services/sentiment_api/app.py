"""
Market Sentiment Analysis REST API — RMM Level 2.

Provides endpoints for sentiment scores, history, divergences, and heatmaps.
Backed by InfluxDB for candle data and Redis for symbol cache.
"""

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, Query

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)
from services.sentiment_api.engine import (
    TIMEFRAMES,
    SentimentResult,
    compute_sentiment,
    detect_divergences,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def _fetch_candles_by_timeframe(
    influxdb_client, symbol: str, limit: int = 100
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch candles for all timeframes from InfluxDB."""
    result = {}
    for tf in TIMEFRAMES:
        try:
            candles = influxdb_client.get_candles(
                symbol=symbol, timeframe=tf, start=None, limit=limit
            )
            if candles:
                result[tf] = candles
        except Exception:
            logger.warning("Failed to fetch %s candles for %s", tf, symbol)
    return result


def _sentiment_to_dict(result: SentimentResult) -> Dict[str, Any]:
    """Convert SentimentResult to API-friendly dict."""
    return {
        "symbol": result.symbol,
        "score": result.score,
        "label": result.label,
        "breakdown": asdict(result.breakdown),
        "timeframe_scores": [
            {
                "timeframe": ts.timeframe,
                "score": ts.score,
                "breakdown": asdict(ts.breakdown),
            }
            for ts in result.timeframe_scores
        ],
    }


def create_app(influxdb_client, redis_client) -> FastAPI:
    """Create the Sentiment Analysis API FastAPI application."""
    app = FastAPI(
        title="Sentiment Analysis API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/sentiment",
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

    app.include_router(create_health_router("sentiment-api", check_deps))

    router = APIRouter(tags=["Sentiment"])

    @router.get("")
    async def get_sentiment(
        symbol: str = Query(..., description="Trading symbol (e.g. BTC/USD)"),
    ):
        """Get current sentiment score for a symbol with breakdown."""
        candles_by_tf = _fetch_candles_by_timeframe(influxdb_client, symbol)
        if not candles_by_tf:
            return not_found("Sentiment data", symbol)

        result = compute_sentiment(symbol, candles_by_tf)
        if not result:
            return not_found("Sentiment data", symbol)

        return success_response(
            _sentiment_to_dict(result), "sentiment", resource_id=symbol
        )

    @router.get("/history")
    async def get_sentiment_history(
        symbol: str = Query(..., description="Trading symbol (e.g. BTC/USD)"),
        timeframe: str = Query(
            "1d",
            description="Timeframe for historical points",
            regex="^(1h|4h|1d|1w)$",
        ),
        limit: int = Query(30, ge=1, le=365, description="Number of historical points"),
    ):
        """Get historical sentiment scores over time.

        Computes sentiment at each candle window by sliding over historical data.
        """
        try:
            candles = influxdb_client.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                start=None,
                limit=limit + 35,  # Extra for indicator warm-up
            )
        except Exception:
            logger.exception("Failed to fetch candles for history")
            candles = []

        if not candles or len(candles) < 35:
            return not_found("Sentiment history", symbol)

        history = []
        window_size = 35  # Minimum for MACD (26+9)
        for i in range(window_size, len(candles)):
            window = candles[i - window_size : i + 1]
            from services.sentiment_api.engine import (
                _sentiment_label,
                compute_timeframe_sentiment,
            )

            tf_result = compute_timeframe_sentiment(window)
            if tf_result:
                history.append(
                    {
                        "timestamp": candles[i].get("time", ""),
                        "score": tf_result.score,
                        "label": _sentiment_label(tf_result.score),
                    }
                )

        return collection_response(history, "sentiment_history")

    @router.get("/divergence")
    async def get_divergences(
        threshold: float = Query(
            0.3, ge=0.0, le=1.0, description="Divergence threshold"
        ),
    ):
        """Find symbols where price and sentiment diverge (contrarian signals)."""
        symbols = redis_client.get_symbols()
        if not symbols:
            return collection_response([], "divergence")

        sentiment_results = []
        price_changes: Dict[str, float] = {}

        for symbol in symbols:
            candles_by_tf = _fetch_candles_by_timeframe(influxdb_client, symbol, limit=50)
            if not candles_by_tf:
                continue

            result = compute_sentiment(symbol, candles_by_tf)
            if not result:
                continue
            sentiment_results.append(result)

            # Calculate recent price change from daily candles
            daily = candles_by_tf.get("1d", [])
            if len(daily) >= 2 and daily[-2]["close"] != 0:
                pct = ((daily[-1]["close"] - daily[-2]["close"]) / daily[-2]["close"]) * 100
                price_changes[symbol] = pct

        divergences = detect_divergences(sentiment_results, price_changes, threshold)
        items = [asdict(d) for d in divergences]
        return collection_response(items, "divergence")

    @router.get("/heatmap")
    async def get_heatmap():
        """Get sentiment heatmap for all tracked symbols."""
        symbols = redis_client.get_symbols()
        if not symbols:
            return collection_response([], "heatmap_entry")

        entries = []
        for symbol in symbols:
            candles_by_tf = _fetch_candles_by_timeframe(influxdb_client, symbol, limit=50)
            if not candles_by_tf:
                continue

            result = compute_sentiment(symbol, candles_by_tf)
            if not result:
                continue

            entries.append(
                {
                    "symbol": result.symbol,
                    "score": result.score,
                    "label": result.label,
                    "color": _score_to_color(result.score),
                }
            )

        entries.sort(key=lambda e: e["score"], reverse=True)
        return collection_response(entries, "heatmap_entry")

    app.include_router(router)
    return app


def _score_to_color(score: float) -> str:
    """Map sentiment score to a display color."""
    if score >= 0.6:
        return "#00C853"  # Strong green
    if score >= 0.2:
        return "#69F0AE"  # Light green
    if score > -0.2:
        return "#FFD600"  # Yellow / neutral
    if score > -0.6:
        return "#FF6D00"  # Orange
    return "#D50000"  # Red
