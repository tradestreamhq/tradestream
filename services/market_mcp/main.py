"""
Main application for the market MCP server.
Connects to InfluxDB and Redis, then serves MCP tools via stdio or SSE.
"""

import asyncio
import sys

from absl import app
from absl import flags
from absl import logging

from services.market_mcp.influxdb_client import MarketInfluxDBClient
from services.market_mcp.redis_client import RedisClient
from services.market_mcp.server import create_server

FLAGS = flags.FLAGS

# InfluxDB Configuration Flags
flags.DEFINE_string("influxdb_url", "http://localhost:8086", "InfluxDB URL.")
flags.DEFINE_string("influxdb_token", "", "InfluxDB authentication token.")
flags.DEFINE_string("influxdb_org", "tradestream-org", "InfluxDB organization.")
flags.DEFINE_string("influxdb_bucket", "candles", "InfluxDB bucket name.")

# Redis Configuration Flags
flags.DEFINE_string("redis_host", "localhost", "Redis host.")
flags.DEFINE_integer("redis_port", 6379, "Redis port.")

# MCP Configuration Flags
flags.DEFINE_string("mcp_transport", "stdio", "MCP transport type (stdio or sse).")
flags.DEFINE_integer("mcp_port", 8080, "MCP server port (for SSE transport).")


async def main_async() -> None:
    """Main async function."""
    if not FLAGS.influxdb_token:
        logging.error("InfluxDB token is required")
        sys.exit(1)

    # Initialize InfluxDB client
    influx_client = MarketInfluxDBClient(
        url=FLAGS.influxdb_url,
        token=FLAGS.influxdb_token,
        org=FLAGS.influxdb_org,
        bucket=FLAGS.influxdb_bucket,
    )
    influx_client.connect()

    # Initialize Redis client
    redis_client = RedisClient(
        host=FLAGS.redis_host,
        port=FLAGS.redis_port,
    )
    redis_client.connect()

    # Create MCP server
    mcp_server = create_server(influx_client, redis_client)

    try:
        if FLAGS.mcp_transport == "stdio":
            from mcp.server.stdio import stdio_server

            async with stdio_server() as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        elif FLAGS.mcp_transport == "sse":
            from mcp.server.sse import SseServerTransport
            from starlette.applications import Starlette
            from starlette.routing import Route

            sse = SseServerTransport("/messages")

            async def handle_sse(request):
                async with sse.connect_sse(
                    request.scope, request.receive, request._send
                ) as streams:
                    await mcp_server.run(
                        streams[0],
                        streams[1],
                        mcp_server.create_initialization_options(),
                    )

            starlette_app = Starlette(
                routes=[
                    Route("/sse", endpoint=handle_sse),
                    Route(
                        "/messages", endpoint=sse.handle_post_message, methods=["POST"]
                    ),
                ],
            )

            import uvicorn

            config = uvicorn.Config(
                starlette_app,
                host="0.0.0.0",
                port=FLAGS.mcp_port,
            )
            server = uvicorn.Server(config)
            await server.serve()
        else:
            logging.error(f"Unknown transport: {FLAGS.mcp_transport}")
            sys.exit(1)
    finally:
        influx_client.close()
        redis_client.close()


def main(argv):
    """Main function."""
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    asyncio.run(main_async())


if __name__ == "__main__":
    app.run(main)
