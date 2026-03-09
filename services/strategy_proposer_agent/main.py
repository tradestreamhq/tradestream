"""
Main entry point for the Strategy Proposer Agent.

Runs on a configurable interval (default 30 minutes) and proposes novel
trading strategies by connecting to the strategy MCP server.
"""

import asyncio
import sys

from absl import app
from absl import flags
from absl import logging

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from services.strategy_proposer_agent.agent import StrategyProposerAgent

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "openrouter_api_key",
    "",
    "OpenRouter API key for LLM access.",
)
flags.DEFINE_string(
    "mcp_strategy_url",
    "http://localhost:8080",
    "URL of the strategy MCP server.",
)
flags.DEFINE_string(
    "mcp_market_url",
    "http://localhost:8081",
    "URL of the market MCP server.",
)
flags.DEFINE_integer(
    "interval_seconds",
    1800,
    "Interval between strategy proposal runs in seconds.",
)


async def run_once(agent: StrategyProposerAgent) -> None:
    """Run a single strategy proposal cycle via MCP stdio client."""
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "services.strategy_mcp.main"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await agent.run(session)
            if result:
                logging.info("Proposal cycle complete: %s", result)
            else:
                logging.info("No novel strategy proposed this cycle")


async def main_async() -> None:
    """Main async entry point."""
    if not FLAGS.openrouter_api_key:
        logging.error("OpenRouter API key is required (--openrouter_api_key)")
        sys.exit(1)

    agent = StrategyProposerAgent(
        openrouter_api_key=FLAGS.openrouter_api_key,
        mcp_strategy_url=FLAGS.mcp_strategy_url,
    )

    logging.info("Starting Strategy Proposer Agent (interval=%ds)", FLAGS.interval_seconds)

    while True:
        try:
            await run_once(agent)
        except Exception:
            logging.exception("Error during strategy proposal cycle")

        if FLAGS.interval_seconds <= 0:
            break
        logging.info("Sleeping %d seconds until next cycle...", FLAGS.interval_seconds)
        await asyncio.sleep(FLAGS.interval_seconds)


def main(argv):
    """Main function."""
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    asyncio.run(main_async())


if __name__ == "__main__":
    app.run(main)
