"""
Exchange Connector REST API.

Provides endpoints for listing exchanges, trading pairs, and ticker data
through the ExchangeRegistry.
"""

import logging
from typing import Optional

from fastapi import APIRouter, FastAPI

from services.exchange_connector.base import ExchangeConnector
from services.exchange_connector.registry import ExchangeRegistry
from services.rest_api_shared.health import create_health_router
from services.rest_api_shared.responses import (
    collection_response,
    not_found,
    success_response,
)
from services.shared.auth import fastapi_auth_middleware

logger = logging.getLogger(__name__)


def create_app(registry: ExchangeRegistry) -> FastAPI:
    """Create the Exchange Connector API application."""
    app = FastAPI(
        title="Exchange Connector API",
        version="1.0.0",
        docs_url="/docs",
        root_path="/api/v1/exchanges",
    )
    fastapi_auth_middleware(app)

    async def check_deps():
        return {"exchanges": f"{len(registry)} registered"}

    app.include_router(create_health_router("exchange-connector", check_deps))

    router = APIRouter(tags=["Exchanges"])

    @router.get("")
    async def list_exchanges():
        """List configured exchanges."""
        items = [{"name": name} for name in registry.list_exchanges()]
        return collection_response(items, "exchange")

    @router.get("/{exchange_id}/pairs")
    async def get_pairs(exchange_id: str):
        """Get available trading pairs for an exchange."""
        connector = registry.get(exchange_id)
        if connector is None:
            return not_found("Exchange", exchange_id)
        pairs = connector.get_pairs()
        items = [{"pair": p} for p in pairs]
        return collection_response(items, "pair")

    @router.get("/{exchange_id}/ticker/{pair:path}")
    async def get_ticker(exchange_id: str, pair: str):
        """Get current ticker for a trading pair on an exchange."""
        connector = registry.get(exchange_id)
        if connector is None:
            return not_found("Exchange", exchange_id)
        try:
            ticker = connector.get_ticker(pair)
            return success_response(
                {
                    "pair": ticker.pair,
                    "last": ticker.last,
                    "bid": ticker.bid,
                    "ask": ticker.ask,
                    "volume_24h": ticker.volume_24h,
                    "timestamp_ms": ticker.timestamp_ms,
                },
                "ticker",
                resource_id=f"{exchange_id}:{pair}",
            )
        except ValueError as e:
            return not_found("Pair", pair)

    app.include_router(router)
    return app
