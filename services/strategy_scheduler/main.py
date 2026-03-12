"""Entry point for the Strategy Scheduler API service."""

import asyncio
import os

import asyncpg
import uvicorn

from services.strategy_scheduler.app import create_app

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8090


async def _create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "tradestream"),
        user=os.environ.get("POSTGRES_USERNAME", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
    )


def main():
    pool = asyncio.get_event_loop().run_until_complete(_create_pool())
    app = create_app(pool)
    uvicorn.run(
        app,
        host=os.environ.get("API_HOST", _DEFAULT_HOST),
        port=int(os.environ.get("API_PORT", str(_DEFAULT_PORT))),
    )


if __name__ == "__main__":
    main()
