"""Entrypoint for the Strategy Versioning API service."""

import asyncio
import logging
import os

import asyncpg
import uvicorn

from services.strategy_versioning_api.app import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    db_url = os.environ.get(
        "DATABASE_URL", "postgresql://localhost:5432/tradestream"
    )
    pool = await asyncpg.create_pool(db_url)
    app = create_app(pool)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8090")),
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
