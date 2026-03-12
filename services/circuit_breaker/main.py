"""Circuit Breaker API entry point."""

import asyncio
import os

import asyncpg
import uvicorn

from services.circuit_breaker.app import create_app
from services.circuit_breaker.models import ThresholdConfig


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

    thresholds = ThresholdConfig(
        warning=float(os.environ.get("CB_WARNING_THRESHOLD", "0.05")),
        halt=float(os.environ.get("CB_HALT_THRESHOLD", "0.10")),
        emergency=float(os.environ.get("CB_EMERGENCY_THRESHOLD", "0.20")),
    )
    poll_interval = float(os.environ.get("CB_POLL_INTERVAL", "10.0"))

    app = create_app(pool, thresholds=thresholds, poll_interval=poll_interval)

    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8081"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
