"""Entry point for the Strategy Health Checker API."""

import asyncio
import os

import asyncpg
import uvicorn

from services.strategy_health.app import create_app


async def _create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "tradestream"),
        password=os.environ.get("POSTGRES_PASSWORD", "tradestream"),
        database=os.environ.get("POSTGRES_DB", "tradestream"),
        min_size=2,
        max_size=10,
    )


def main():
    pool = asyncio.get_event_loop().run_until_complete(_create_pool())
    app = create_app(pool)
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
