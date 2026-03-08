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
from services.strategy_mcp.server import create_server

FLAGS = flags.FLAGS

# PostgreSQL Configuration Flags
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host.")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port.")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database name.")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username.")
flags.DEFINE_string("postgres_password", "", "PostgreSQL password.")

# MCP Configuration Flags
flags.DEFINE_string("mcp_transport", "stdio", "MCP transport type (stdio or sse).")
flags.DEFINE_integer("mcp_port", 8080, "MCP server port (for SSE transport).")


async def main_async() -> None:
    """Main async function."""
    if not FLAGS.postgres_password:
        logging.error("PostgreSQL password is required")
        sys.exit(1)

    postgres_client = PostgresClient(
        host=FLAGS.postgres_host,
        port=FLAGS.postgres_port,
        database=FLAGS.postgres_database,
        username=FLAGS.postgres_username,
        password=FLAGS.postgres_password,
    )

    try:
        await postgres_client.connect()

        mcp_server = create_server(postgres_client)

        logging.info("Starting MCP server with %s transport", FLAGS.mcp_transport)

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
                        "/messages",
                        endpoint=sse.handle_post_message,
                        methods=["POST"],
                    ),
                ],
            )

            import uvicorn

            config = uvicorn.Config(
                starlette_app,
                host="0.0.0.0",
                port=FLAGS.mcp_port,
            )
            uvicorn_server = uvicorn.Server(config)
            await uvicorn_server.serve()
        else:
            logging.error(f"Unknown transport: {FLAGS.mcp_transport}")
            sys.exit(1)
    finally:
        await postgres_client.close()


def main(argv):
    """Main function."""
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    asyncio.run(main_async())


if __name__ == "__main__":
    app.run(main)
