"""
Correlation Engine API entry point.

Initializes price data provider and starts the FastAPI server.
"""

import os

import uvicorn

from services.correlation_engine.app import create_app


class InfluxDBPriceProvider:
    """Price provider backed by InfluxDB."""

    def __init__(self, influxdb_client, redis_client):
        self._influxdb = influxdb_client
        self._redis = redis_client

    def get_symbols(self):
        return self._redis.get_symbols()

    def get_prices(self, symbol, limit=200):
        return self._influxdb.get_candles(
            symbol=symbol, timeframe="1d", limit=limit
        )


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))

    # In production, initialize real InfluxDB/Redis clients here
    # For now, create app with a placeholder that will be replaced at deploy
    from services.market_mcp.influxdb_client import InfluxDBClient
    from services.market_mcp.redis_client import RedisClient

    influxdb = InfluxDBClient()
    redis = RedisClient()
    provider = InfluxDBPriceProvider(influxdb, redis)

    app = create_app(provider)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
