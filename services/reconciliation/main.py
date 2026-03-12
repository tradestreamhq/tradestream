"""Reconciliation API entry point."""

import asyncio
import os

import asyncpg
import uvicorn

from services.reconciliation.app import create_app
from services.reconciliation.exchange_client import ExchangePositionClient


async def _create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", ""),
        user=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        min_size=2,
        max_size=10,
    )


def _create_exchange_client():
    """Create exchange client if credentials are configured."""
    exchange = os.environ.get("EXCHANGE_NAME")
    api_key = os.environ.get("EXCHANGE_API_KEY")
    secret = os.environ.get("EXCHANGE_SECRET")
    if exchange and api_key and secret:
        return ExchangePositionClient(exchange, api_key, secret)
    return None


def main():
    pool = asyncio.get_event_loop().run_until_complete(_create_pool())
    exchange_client = _create_exchange_client()
    app = create_app(pool, exchange_client)
    host = os.environ.get("API_HOST", "127.0.0.1")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
