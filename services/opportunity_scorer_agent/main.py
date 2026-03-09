"""Entry point for the Opportunity Scorer Agent."""

import signal
import sys
import time

from absl import app, flags, logging

from services.opportunity_scorer_agent.agent import run_scorer

FLAGS = flags.FLAGS

flags.DEFINE_string("openrouter_api_key", None, "OpenRouter API key.")
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL."
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL.")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL.")
flags.DEFINE_integer(
    "poll_interval_seconds", 10, "Interval between scoring runs in seconds."
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
        "signal": FLAGS.mcp_signal_url.rstrip("/"),
    }

    logging.info(
        "Opportunity Scorer Agent started. Poll interval: %ds",
        FLAGS.poll_interval_seconds,
    )

    while not _shutdown:
        try:
            logging.info("Running scoring cycle...")
            result = run_scorer(
                api_key=FLAGS.openrouter_api_key,
                mcp_urls=mcp_urls,
            )
            if result:
                logging.info("Scoring result: %s", result[:500])
            else:
                logging.warning("No result from scoring cycle")
        except Exception as e:
            logging.exception("Error in scoring cycle: %s", e)

        if not _shutdown:
            logging.info("Sleeping %ds before next cycle...", FLAGS.poll_interval_seconds)
            for _ in range(FLAGS.poll_interval_seconds):
                if _shutdown:
                    break
                time.sleep(1)

    logging.info("Opportunity Scorer Agent shut down.")


if __name__ == "__main__":
    app.run(main)
