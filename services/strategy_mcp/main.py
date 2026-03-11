"""
Main entry point for the strategy MCP server.
Configurable via absl flags for PostgreSQL and MCP transport settings.
"""

import asyncio
import os
import sys

from absl import app
from absl import flags
from absl import logging

from services.strategy_mcp.postgres_client import PostgresClient
from services.strategy_mcp.server import server, _set_postgres_client

FLAGS = flags.FLAGS

# PostgreSQL Configuration Flags
flags.DEFINE_string(
    "postgres_host",
    "localhost",
    "PostgreSQL host.",
)
flags.DEFINE_integer(
    "postgres_port",
    5432,
    "PostgreSQL port.",
)
flags.DEFINE_string(
    "postgres_database",
    os.environ.get("POSTGRES_DATABASE", ""),
    "PostgreSQL database name.",
)
flags.DEFINE_string(
    "postgres_username",
    "postgres",
    "PostgreSQL username.",
)
flags.DEFINE_string(
    "postgres_password",
    "",
    "PostgreSQL password.",
)

# MCP Configuration Flags
flags.DEFINE_string(
    "mcp_transport",
    "stdio",
    "MCP transport type (stdio).",
)
flags.DEFINE_integer(
    "mcp_port",
    8080,
    "MCP server port (for future HTTP/SSE transport).",
)


async def main_async() -> None:
    """Main async function."""
    if not FLAGS.postgres_password:
        logging.error("PostgreSQL password is required")
        sys.exit(1)

    pg_client = PostgresClient(
        host=FLAGS.postgres_host,
        port=FLAGS.postgres_port,
        database=FLAGS.postgres_database,
        username=FLAGS.postgres_username,
        password=FLAGS.postgres_password,
    )

    try:
        await pg_client.connect()
        _set_postgres_client(pg_client)
        logging.info("Starting MCP server with %s transport", FLAGS.mcp_transport)

        if FLAGS.mcp_transport == "stdio":
            from mcp.server.stdio import stdio_server

            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
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
                    await server.run(
                        streams[0],
                        streams[1],
                        server.create_initialization_options(),
                    )

            from services.shared.auth import starlette_auth_middleware

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
            starlette_auth_middleware(starlette_app)

            import uvicorn

            config = uvicorn.Config(
                starlette_app,
                host=os.environ.get("HOST", "127.0.0.1"),
                port=FLAGS.mcp_port,
            )
            uvicorn_server = uvicorn.Server(config)
            await uvicorn_server.serve()
        else:
            logging.error(f"Unknown transport: {FLAGS.mcp_transport}")
            sys.exit(1)
    finally:
        await pg_client.close()


def main(argv):
    """Main function."""
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    asyncio.run(main_async())


if __name__ == "__main__":
    app.run(main)
