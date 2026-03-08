"""
Main entry point for the strategy MCP server.
Configurable via absl flags for PostgreSQL and MCP transport settings.
"""

import asyncio
import sys

from absl import app
from absl import flags
from absl import logging

from services.strategy_mcp.postgres_client import PostgresClient
from services.strategy_mcp.server import run_stdio

FLAGS = flags.FLAGS

# PostgreSQL Configuration Flags
flags.DEFINE_string(
    "postgres_host",
    "localhost",
    "PostgreSQL host.",
)
flags.DEFINE_integer(
    "postgres_port",
    5432,
    "PostgreSQL port.",
)
flags.DEFINE_string(
    "postgres_database",
    "tradestream",
    "PostgreSQL database name.",
)
flags.DEFINE_string(
    "postgres_username",
    "postgres",
    "PostgreSQL username.",
)
flags.DEFINE_string(
    "postgres_password",
    "",
    "PostgreSQL password.",
)

# MCP Configuration Flags
flags.DEFINE_string(
    "mcp_transport",
    "stdio",
    "MCP transport type (stdio).",
)
flags.DEFINE_integer(
    "mcp_port",
    8080,
    "MCP server port (for future HTTP/SSE transport).",
)


async def main_async() -> None:
    """Main async function."""
    if not FLAGS.postgres_password:
        logging.error("PostgreSQL password is required")
        sys.exit(1)

    pg_client = PostgresClient(
        host=FLAGS.postgres_host,
        port=FLAGS.postgres_port,
        database=FLAGS.postgres_database,
        username=FLAGS.postgres_username,
        password=FLAGS.postgres_password,
    )

    try:
        await pg_client.connect()
        logging.info("Starting MCP server with %s transport", FLAGS.mcp_transport)
        await run_stdio(pg_client)
    finally:
        await pg_client.close()


def main(argv):
    """Main function."""
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    asyncio.run(main_async())


if __name__ == "__main__":
    app.run(main)
