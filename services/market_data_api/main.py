"""
Market Data API entry point.
"""

import os

import uvicorn

from services.market_data_api.app import create_app
from services.market_mcp.influxdb_client import InfluxDBMarketClient
from services.market_mcp.redis_client import RedisMarketClient


def main():
    influxdb_client = InfluxDBMarketClient(
        url=os.environ.get("INFLUXDB_URL", "http://localhost:8086"),
        token=os.environ.get("INFLUXDB_TOKEN", ""),
        org=os.environ.get("INFLUXDB_ORG", ""),
        bucket=os.environ.get("INFLUXDB_BUCKET", "candles"),
    )
    redis_client = RedisMarketClient(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
    )

    app = create_app(influxdb_client, redis_client)
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
