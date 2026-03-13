"""Entry point for the Market Data WebSocket Gateway."""

import logging
import os

import uvicorn

from services.market_data_ws.app import create_app
from services.market_data_ws.broadcaster import MarketDataBroadcaster

logging.basicConfig(level=logging.INFO)


def main():
    broadcaster = MarketDataBroadcaster()
    max_conn = int(os.environ.get("MAX_CONNECTIONS_PER_CLIENT", "5"))
    app = create_app(broadcaster=broadcaster, max_connections_per_client=max_conn)

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
