"""
Exchange Account Manager entry point.
"""

import asyncio
import os

import asyncpg
import uvicorn

from services.exchange_account_manager.app import create_app


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


def main():
    pool = asyncio.get_event_loop().run_until_complete(_create_pool())
    app = create_app(pool)
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8084"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
