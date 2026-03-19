"""Market Sentiment Signal Source — REST API.

Provides endpoints for:
- Current aggregated sentiment and signals
- Sentiment history for charts
- Divergence detection
- Sentiment momentum
- Dashboard data (gauges, overlays)
"""

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, FastAPI, Query

from services.market_sentiment.aggregator import (
    AggregatedSentiment,
    SentimentDataFetcher,
    SentimentDataPoint,
    aggregate_sentiment,
)
from services.market_sentiment.signal_generator import (
    SentimentMomentumTracker,
    detect_divergence,
    generate_composite_signal,
    generate_contrarian_signal,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
)

logger = logging.getLogger(__name__)


def create_app(
    fetcher: Optional[SentimentDataFetcher] = None,
    momentum_tracker: Optional[SentimentMomentumTracker] = None,
) -> FastAPI:
    """Create the Market Sentiment Signal Source FastAPI application."""

    app = FastAPI(
        title="Market Sentiment Signal Source",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/market-sentiment",
    )

    _fetcher = fetcher or SentimentDataFetcher()
    _momentum = momentum_tracker or SentimentMomentumTracker()

    async def check_deps():
        return {"fetcher": "ok", "momentum_tracker": "ok"}

    app.include_router(create_health_router("market-sentiment", check_deps))

    router = APIRouter(tags=["Market Sentiment"])

    @router.get("/sentiment")
    async def get_sentiment(
        symbol: str = Query(..., description="Trading symbol (e.g. BTC-USD)"),
        funding_rate: Optional[float] = Query(None, description="Current funding rate"),
        long_short_ratio: Optional[float] = Query(
            None, description="Current long/short ratio"
        ),
        social_mentions: Optional[float] = Query(
            None, description="Social mention count"
        ),
        social_avg_mentions: Optional[float] = Query(
            None, description="Average social mentions"
        ),
        news_score: Optional[float] = Query(
            None, description="News sentiment score [-1,+1]"
        ),
        news_headline_count: Optional[int] = Query(
            None, description="Number of news headlines"
        ),
    ):
        """Get aggregated sentiment for a symbol with source breakdown."""
        data_points: List[SentimentDataPoint] = []

        # Fear & Greed Index (auto-fetched)
        fg = _fetcher.fetch_fear_greed()
        if fg:
            data_points.append(fg)

        # Crypto-specific sources (passed in or from exchange data)
        if funding_rate is not None:
            data_points.append(_fetcher.fetch_funding_rate(symbol, funding_rate))

        if long_short_ratio is not None:
            data_points.append(
                _fetcher.fetch_long_short_ratio(symbol, long_short_ratio)
            )

        if social_mentions is not None and social_avg_mentions is not None:
            data_points.append(
                _fetcher.fetch_social_sentiment(social_mentions, social_avg_mentions)
            )

        if news_score is not None:
            data_points.append(
                _fetcher.fetch_news_sentiment(news_score, news_headline_count or 0)
            )

        if not data_points:
            return not_found("Sentiment data", symbol)

        result = aggregate_sentiment(symbol, data_points)

        # Record for momentum tracking
        _momentum.record(symbol, result.composite_score)

        return success_response(
            _sentiment_to_dict(result), "sentiment", resource_id=symbol
        )

    @router.get("/signal")
    async def get_signal(
        symbol: str = Query(..., description="Trading symbol"),
        sentiment_score: float = Query(
            ..., description="Current sentiment score [-1,+1]"
        ),
        price_change_pct: float = Query(0.0, description="Recent price change %"),
    ):
        """Generate a composite sentiment trading signal."""
        agg = AggregatedSentiment(
            symbol=symbol,
            composite_score=sentiment_score,
            label=_label_from_score(sentiment_score),
            source_scores=[],
        )

        signal = generate_composite_signal(agg, price_change_pct, _momentum)
        return success_response(asdict(signal), "signal", resource_id=symbol)

    @router.get("/divergence")
    async def get_divergence(
        symbol: str = Query(..., description="Trading symbol"),
        sentiment_score: float = Query(
            ..., description="Current sentiment score [-1,+1]"
        ),
        price_change_pct: float = Query(..., description="Recent price change %"),
        threshold: float = Query(
            0.3, ge=0.0, le=1.0, description="Detection threshold"
        ),
    ):
        """Detect price-vs-sentiment divergence for a symbol."""
        result = detect_divergence(symbol, sentiment_score, price_change_pct, threshold)
        return success_response(asdict(result), "divergence", resource_id=symbol)

    @router.get("/momentum")
    async def get_momentum(
        symbol: str = Query(..., description="Trading symbol"),
    ):
        """Get sentiment momentum (velocity & acceleration) for a symbol."""
        mom = _momentum.compute_momentum(symbol)
        if not mom:
            return not_found("Momentum data", symbol)
        return success_response(asdict(mom), "momentum", resource_id=symbol)

    @router.get("/dashboard")
    async def get_dashboard(
        symbol: str = Query(..., description="Trading symbol"),
        sentiment_score: float = Query(..., description="Current sentiment [-1,+1]"),
        price_change_pct: float = Query(0.0, description="Recent price change %"),
    ):
        """Get dashboard data: gauge, momentum, divergence, signal."""
        from services.market_sentiment.aggregator import sentiment_label

        # Gauge data
        gauge = {
            "score": round(sentiment_score, 4),
            "label": sentiment_label(sentiment_score),
            "gauge_pct": round((sentiment_score + 1.0) / 2.0 * 100.0, 1),
        }

        # Momentum
        mom = _momentum.compute_momentum(symbol)
        momentum_data = asdict(mom) if mom else None

        # Divergence
        div = detect_divergence(symbol, sentiment_score, price_change_pct)
        divergence_data = asdict(div)

        # History for chart
        history = _momentum.get_history(symbol)
        history_data = [{"timestamp": ts, "score": round(s, 4)} for ts, s in history]

        return success_response(
            {
                "symbol": symbol,
                "gauge": gauge,
                "momentum": momentum_data,
                "divergence": divergence_data,
                "history": history_data,
            },
            "dashboard",
            resource_id=symbol,
        )

    app.include_router(router)
    return app


def _sentiment_to_dict(result: AggregatedSentiment) -> Dict[str, Any]:
    """Convert AggregatedSentiment to API-friendly dict."""
    return {
        "symbol": result.symbol,
        "composite_score": result.composite_score,
        "label": result.label,
        "timestamp": result.timestamp,
        "sources": [
            {
                "source": dp.source.value,
                "raw_value": dp.raw_value,
                "normalised_score": dp.normalised_score,
                "metadata": dp.metadata,
            }
            for dp in result.source_scores
        ],
    }


def _label_from_score(score: float) -> str:
    from services.market_sentiment.aggregator import sentiment_label

    return sentiment_label(score)
