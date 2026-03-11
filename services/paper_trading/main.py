"""Entry point for the Paper Trading evaluation service."""

import asyncio
import os
import signal
import sys
import threading

from absl import app, flags, logging

from services.paper_trading.postgres_client import PostgresClient
from services.paper_trading.service import create_app

FLAGS = flags.FLAGS

flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string(
    "postgres_database",
    os.environ.get("POSTGRES_DATABASE", ""),
    "PostgreSQL database name",
)
flags.DEFINE_string(
    "postgres_username",
    os.environ.get("POSTGRES_USERNAME", "postgres"),
    "PostgreSQL username",
)
flags.DEFINE_string("postgres_password", "", "PostgreSQL password")
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL")
flags.DEFINE_integer("port", 8090, "HTTP server port")


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    if not FLAGS.postgres_password:
        logging.error("--postgres_password is required")
        sys.exit(1)

    # Create a dedicated event loop for async work (asyncpg pool).
    # This loop runs in a daemon thread; Flask handler threads dispatch
    # coroutines to it via asyncio.run_coroutine_threadsafe().
    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(
        target=loop.run_forever, daemon=True, name="paper-trading-loop"
    )
    loop_thread.start()

    pg_client = PostgresClient(
        host=FLAGS.postgres_host,
        port=FLAGS.postgres_port,
        database=FLAGS.postgres_database,
        username=FLAGS.postgres_username,
        password=FLAGS.postgres_password,
    )

    try:
        future = asyncio.run_coroutine_threadsafe(pg_client.connect(), loop)
        future.result()
    except Exception as e:
        logging.error("Failed to connect to PostgreSQL: %s", e)
        sys.exit(1)

    flask_app = create_app(
        pg_client=pg_client,
        market_mcp_url=FLAGS.mcp_market_url,
        signal_mcp_url=FLAGS.mcp_signal_url,
        event_loop=loop,
    )

    def shutdown_handler(signum, frame):
        logging.info("Received signal %d, shutting down...", signum)
        future = asyncio.run_coroutine_threadsafe(pg_client.close(), loop)
        future.result(timeout=5)
        loop.call_soon_threadsafe(loop.stop)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logging.info("Paper Trading service starting on port %d", FLAGS.port)
    flask_app.run(host="0.0.0.0", port=FLAGS.port)


if __name__ == "__main__":
    app.run(main)
