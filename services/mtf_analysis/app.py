"""
Multi-Timeframe Analysis REST API — RMM Level 2.

Endpoints:
  GET /mtf/{pair}             — multi-timeframe snapshot
  GET /mtf/{pair}/confluence  — confluence score
"""

import logging
from typing import Optional

from fastapi import APIRouter, FastAPI, Query

from services.mtf_analysis.analyzer import (
    TIMEFRAMES,
    MultiTimeframeAnalyzer,
    Signal,
)
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
    validation_error,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(influxdb_client) -> FastAPI:
    """Create the Multi-Timeframe Analysis API application."""
    app = FastAPI(
        title="Multi-Timeframe Analysis API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/mtf",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        return {}

    app.include_router(create_health_router("mtf-analysis-api", check_deps))

    analyzer = MultiTimeframeAnalyzer(influxdb_client)
    mtf_router = APIRouter(tags=["Multi-Timeframe Analysis"])

    @mtf_router.get("/{pair}")
    async def get_snapshot(
        pair: str,
        timeframes: Optional[str] = Query(
            None,
            description="Comma-separated timeframes (e.g. 1m,5m,1h). Defaults to all.",
        ),
    ):
        """Get multi-timeframe analysis snapshot for a trading pair."""
        tf_list = None
        if timeframes:
            tf_list = [t.strip() for t in timeframes.split(",")]
            invalid = [t for t in tf_list if t not in TIMEFRAMES]
            if invalid:
                return validation_error(
                    f"Invalid timeframes: {', '.join(invalid)}. "
                    f"Valid options: {', '.join(TIMEFRAMES)}"
                )

        try:
            snapshot = analyzer.get_snapshot(pair, tf_list)
        except Exception:
            logger.exception("Failed to get snapshot for %s", pair)
            return not_found("Pair", pair)

        items = []
        for tf, analysis in snapshot.items():
            items.append(
                {
                    "timeframe": analysis.timeframe,
                    "signal": analysis.signal.value,
                    "strength": analysis.strength,
                    "indicators": analysis.indicators,
                    "candle_count": analysis.candle_count,
                }
            )

        return collection_response(items, "timeframe_analysis")

    @mtf_router.get("/{pair}/confluence")
    async def get_confluence(
        pair: str,
        timeframes: Optional[str] = Query(
            None,
            description="Comma-separated timeframes. Defaults to all.",
        ),
    ):
        """Get confluence score across multiple timeframes."""
        tf_list = None
        if timeframes:
            tf_list = [t.strip() for t in timeframes.split(",")]
            invalid = [t for t in tf_list if t not in TIMEFRAMES]
            if invalid:
                return validation_error(
                    f"Invalid timeframes: {', '.join(invalid)}. "
                    f"Valid options: {', '.join(TIMEFRAMES)}"
                )

        try:
            result = analyzer.get_confluence(pair, tf_list)
        except Exception:
            logger.exception("Failed to compute confluence for %s", pair)
            return not_found("Pair", pair)

        data = {
            "pair": result.pair,
            "score": result.score,
            "signal": result.signal.value,
            "agreeing_timeframes": result.agreeing_timeframes,
            "total_timeframes": result.total_timeframes,
        }

        return success_response(data, "confluence", resource_id=pair)

    app.include_router(mtf_router)
    return app
