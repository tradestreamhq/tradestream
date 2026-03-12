"""Entry point for the Position Management service."""

import asyncio
import os
import threading

from absl import app as absl_app
from absl import logging

from services.position_management.postgres_client import PostgresClient
from services.position_management.service import create_app


def main(argv):
    del argv

    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "5432"))
    database = os.environ.get("DB_NAME", "tradestream")
    username = os.environ.get("DB_USER", "tradestream")
    password = os.environ.get("DB_PASSWORD", "")
    market_mcp_url = os.environ.get("MARKET_MCP_URL", "http://market-mcp:8080")
    service_port = int(os.environ.get("PORT", "8080"))

    pg_client = PostgresClient(host, port, database, username, password)

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    future = asyncio.run_coroutine_threadsafe(pg_client.connect(), loop)
    future.result()

    flask_app = create_app(
        pg_client=pg_client,
        market_mcp_url=market_mcp_url,
        event_loop=loop,
    )

    logging.info(f"Starting Position Management service on port {service_port}")
    flask_app.run(host="0.0.0.0", port=service_port)


if __name__ == "__main__":
    absl_app.run(main)
