#!/usr/bin/env python3
"""Entry point for the Beta Onboarding API service."""

import asyncio
import os

import asyncpg
import uvicorn

from services.beta_onboarding.app import create_app


async def _main():
    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DATABASE", "tradestream"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        min_size=2,
        max_size=10,
    )
    app = create_app(pool)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8091")),
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(_main())
