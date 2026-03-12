"""
Sentiment Analysis REST API.

Provides endpoints for querying sentiment scores per symbol,
ingesting text for analysis, and retrieving aggregated sentiment.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, FastAPI, Query
from pydantic import BaseModel, Field

from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)
from services.sentiment_api.feed_processor import SentimentStore

logger = logging.getLogger(__name__)


class IngestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    symbol: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)
    timestamp: Optional[datetime] = None


def create_app(store: Optional[SentimentStore] = None) -> FastAPI:
    """Create the Sentiment API FastAPI application."""
    if store is None:
        store = SentimentStore()

    app = FastAPI(
        title="Sentiment Analysis API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/sentiment",
    )

    app.include_router(create_health_router("sentiment-api"))

    router = APIRouter(tags=["Sentiment"])

    @router.get("/{symbol}")
    async def get_sentiment(
        symbol: str,
        from_time: Optional[str] = Query(
            None, alias="from", description="Start time (ISO 8601)"
        ),
        to_time: Optional[str] = Query(
            None, alias="to", description="End time (ISO 8601)"
        ),
    ):
        """Get aggregated sentiment for a symbol."""
        ft = _parse_time(from_time)
        tt = _parse_time(to_time)

        agg = store.get_aggregated(symbol, from_time=ft, to_time=tt)
        if agg is None:
            return not_found("Sentiment", symbol)

        return success_response(agg.to_dict(), "sentiment", resource_id=symbol)

    @router.get("/{symbol}/records")
    async def get_records(
        symbol: str,
        from_time: Optional[str] = Query(
            None, alias="from", description="Start time (ISO 8601)"
        ),
        to_time: Optional[str] = Query(
            None, alias="to", description="End time (ISO 8601)"
        ),
        limit: int = Query(50, ge=1, le=500),
    ):
        """Get individual sentiment records for a symbol."""
        ft = _parse_time(from_time)
        tt = _parse_time(to_time)

        records = store.get_records(symbol, from_time=ft, to_time=tt)
        items = [r.to_dict() for r in records[:limit]]
        return collection_response(items, "sentiment_record", limit=limit)

    @router.post("/ingest")
    async def ingest(request: IngestRequest):
        """Ingest text for sentiment analysis."""
        record = store.ingest_text(
            text=request.text,
            symbol=request.symbol,
            source=request.source,
            timestamp=request.timestamp,
        )
        return success_response(
            record.to_dict(), "sentiment_record", resource_id=record.symbol
        )

    app.include_router(router)
    return app


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromisoformat(value)
