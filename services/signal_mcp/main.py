"""
Main application for the signal MCP server.
Connects to Redis and PostgreSQL, then serves MCP tools via stdio or SSE.
"""

import asyncio
import signal
import sys

from absl import app
from absl import flags
from absl import logging

from services.signal_mcp.postgres_client import PostgresClient
from services.signal_mcp.redis_client import RedisClient
from services.signal_mcp.server import create_server
from services.shared.config import get_postgres_config, get_redis_config

FLAGS = flags.FLAGS

# MCP Configuration Flags
flags.DEFINE_string("mcp_transport", "stdio", "MCP transport type (stdio or sse).")
flags.DEFINE_integer("mcp_port", 8080, "MCP server port (for SSE transport).")


async def main_async() -> None:
    """Main async function."""
    pg_cfg = get_postgres_config()
    if not pg_cfg["password"]:
        logging.error("PostgreSQL password is required (set POSTGRES_PASSWORD)")
        sys.exit(1)

    # Initialize PostgreSQL client
    postgres_client = PostgresClient(
        host=pg_cfg["host"],
        port=pg_cfg["port"],
        database=pg_cfg["database"],
        username=pg_cfg["user"],
        password=pg_cfg["password"],
    )
    await postgres_client.connect()

    # Initialize Redis client
    redis_cfg = get_redis_config()
    redis_client = RedisClient(
        host=redis_cfg["host"],
        port=redis_cfg["port"],
    )
    redis_client.connect()

    # Create MCP server
    mcp_server = create_server(postgres_client, redis_client)

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
        await postgres_client.close()
        redis_client.close()


def main(argv):
    """Main function."""
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    asyncio.run(main_async())


if __name__ == "__main__":
    app.run(main)
