"""
Main entry point for the CoinMarketCap MCP server.
Configurable via absl flags for API key and MCP transport settings.
"""

import asyncio
import os
import sys

from absl import app
from absl import flags
from absl import logging

from services.coinmarketcap_mcp.cmc_client import CoinMarketCapClient
from services.coinmarketcap_mcp.server import server, _set_cmc_client

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "cmc_api_key",
    os.environ.get("CMC_API_KEY", ""),
    "CoinMarketCap Pro API key.",
)

flags.DEFINE_string(
    "mcp_transport",
    "stdio",
    "MCP transport type (stdio or sse).",
)

flags.DEFINE_integer(
    "mcp_port",
    8080,
    "MCP server port (for SSE transport).",
)


async def main_async() -> None:
    """Main async function."""
    api_key = FLAGS.cmc_api_key
    if not api_key:
        logging.error("CoinMarketCap API key is required (--cmc_api_key or CMC_API_KEY env)")
        sys.exit(1)

    cmc_client = CoinMarketCapClient(api_key=api_key)

    try:
        _set_cmc_client(cmc_client)
        logging.info("Starting CoinMarketCap MCP server with %s transport", FLAGS.mcp_transport)

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
                host="0.0.0.0",
                port=FLAGS.mcp_port,
            )
            uvicorn_server = uvicorn.Server(config)
            await uvicorn_server.serve()
        else:
            logging.error("Unknown transport: %s", FLAGS.mcp_transport)
            sys.exit(1)
    finally:
        await cmc_client.close()


def main(argv):
    """Main function."""
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    asyncio.run(main_async())


if __name__ == "__main__":
    app.run(main)
