#!/usr/bin/env python3
"""Risk Dashboard service entry point."""

import asyncio
import os
import sys

import asyncpg
import uvicorn
from absl import app, flags, logging

from services.risk_dashboard.app import create_app

FLAGS = flags.FLAGS

flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string(
    "postgres_database", os.environ.get("POSTGRES_DATABASE", ""), "PostgreSQL database"
)
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "", "PostgreSQL password")
flags.DEFINE_integer("http_port", 8086, "HTTP server port")


def main(argv):
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")

    logging.set_verbosity(logging.INFO)

    if not FLAGS.postgres_password:
        logging.error("--postgres_password is required")
        sys.exit(1)

    async def run():
        pool = await asyncpg.create_pool(
            host=FLAGS.postgres_host,
            port=FLAGS.postgres_port,
            database=FLAGS.postgres_database,
            user=FLAGS.postgres_username,
            password=FLAGS.postgres_password,
            min_size=1,
            max_size=10,
            command_timeout=60,
        )
        logging.info("Connected to PostgreSQL")

        fastapi_app = create_app(pool)
        config = uvicorn.Config(
            fastapi_app, host="0.0.0.0", port=FLAGS.http_port, log_level="info"
        )
        server = uvicorn.Server(config)
        try:
            await server.serve()
        finally:
            await pool.close()

    asyncio.run(run())


if __name__ == "__main__":
    app.run(main)
