"""Entry point for the Volatility Regime API service."""

import os

import uvicorn

from services.market_mcp.influxdb_client import InfluxDBClient
from services.volatility_regime.app import create_app


def main():
    influxdb = InfluxDBClient(
        url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
        token=os.getenv("INFLUXDB_TOKEN", ""),
        org=os.getenv("INFLUXDB_ORG", "tradestream"),
        bucket=os.getenv("INFLUXDB_BUCKET", "candles"),
    )
    app = create_app(influxdb)
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
