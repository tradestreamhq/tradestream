"""Entry point for the Strategy Proposer Agent."""

import signal
import sys
import time

from absl import app, flags, logging

from services.strategy_proposer_agent.agent import run_proposer_agent

FLAGS = flags.FLAGS

flags.DEFINE_string("openrouter_api_key", None, "OpenRouter API key.")
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL."
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL.")
flags.DEFINE_integer(
    "interval_seconds", 1800, "Interval between strategy proposal runs in seconds."
)

flags.mark_flag_as_required("openrouter_api_key")

_shutdown = False


def _handle_shutdown(signum, frame):
    global _shutdown
    logging.info("Received signal %d, shutting down...", signum)
    _shutdown = True


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url.rstrip("/"),
        "market": FLAGS.mcp_market_url.rstrip("/"),
    }

    logging.info(
        "Strategy Proposer Agent started. Interval: %ds",
        FLAGS.interval_seconds,
    )

    while not _shutdown:
        try:
            logging.info("Proposing new strategy...")
            result = run_proposer_agent(
                api_key=FLAGS.openrouter_api_key,
                mcp_urls=mcp_urls,
            )
            if result:
                logging.info("Proposer result: %s", result[:500])
            else:
                logging.warning("No result from proposer agent.")
        except Exception as e:
            logging.exception("Error in strategy proposer: %s", e)

        if not _shutdown:
            logging.info("Sleeping %ds before next run...", FLAGS.interval_seconds)
            for _ in range(FLAGS.interval_seconds):
                if _shutdown:
                    break
                time.sleep(1)

    logging.info("Strategy Proposer Agent shut down.")


if __name__ == "__main__":
    app.run(main)
