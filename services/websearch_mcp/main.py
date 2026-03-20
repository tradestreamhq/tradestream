"""Entry point for the web search MCP server."""

import asyncio
import os
import sys

from absl import app, flags
from mcp.server.stdio import stdio_server

from services.websearch_mcp.search_client import SearchClient
from services.websearch_mcp.server import create_server

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "brave_api_key",
    os.environ.get("BRAVE_API_KEY", ""),
    "Brave Search API key",
)
flags.DEFINE_string(
    "google_api_key",
    os.environ.get("GOOGLE_API_KEY", ""),
    "Google Custom Search API key",
)
flags.DEFINE_string(
    "google_cx",
    os.environ.get("GOOGLE_CX", ""),
    "Google Custom Search engine ID",
)


def main(argv):
    del argv

    search_client = SearchClient(
        brave_api_key=FLAGS.brave_api_key or None,
        google_api_key=FLAGS.google_api_key or None,
        google_cx=FLAGS.google_cx or None,
    )

    server = create_server(search_client)

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == "__main__":
    app.run(main)
