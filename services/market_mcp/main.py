"""Main entry point for market-mcp MCP server."""

from absl import app, flags, logging

from services.market_mcp.influxdb_client import InfluxDBQueryClient
from services.market_mcp.redis_client import RedisMarketClient
from services.market_mcp.server import init_server, mcp

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "influxdb_url",
    "http://localhost:8086",
    "InfluxDB URL.",
)
flags.DEFINE_string(
    "influxdb_token",
    None,
    "InfluxDB authentication token.",
)
flags.DEFINE_string(
    "influxdb_org",
    "tradestream-org",
    "InfluxDB organization.",
)
flags.DEFINE_string(
    "influxdb_bucket",
    "candles",
    "InfluxDB bucket for candle data.",
)
flags.DEFINE_string(
    "redis_host",
    "localhost",
    "Redis host.",
)
flags.DEFINE_integer(
    "redis_port",
    6379,
    "Redis port.",
)
flags.DEFINE_string(
    "redis_password",
    None,
    "Redis password.",
)
flags.DEFINE_string(
    "mcp_transport",
    "stdio",
    "MCP transport type: 'stdio' or 'sse'.",
)
flags.DEFINE_integer(
    "mcp_port",
    8080,
    "Port for SSE transport.",
)


def main(argv):
    del argv  # Unused.

    logging.info("Starting market-mcp server...")

    influx_client = InfluxDBQueryClient(
        url=FLAGS.influxdb_url,
        token=FLAGS.influxdb_token,
        org=FLAGS.influxdb_org,
        bucket=FLAGS.influxdb_bucket,
    )

    redis_client = RedisMarketClient(
        host=FLAGS.redis_host,
        port=FLAGS.redis_port,
        password=FLAGS.redis_password,
    )

    init_server(influx_client, redis_client)

    transport = FLAGS.mcp_transport
    if transport == "sse":
        logging.info(f"Running MCP server with SSE transport on port {FLAGS.mcp_port}")
        mcp.run(transport="sse")
    else:
        logging.info("Running MCP server with stdio transport")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    app.run(main)
