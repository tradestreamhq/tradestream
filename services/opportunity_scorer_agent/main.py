"""Entry point for the Opportunity Scorer Agent."""

import signal
import sys
import time

from absl import app, flags, logging

from services.opportunity_scorer_agent.agent import (
    TOOL_TO_MCP_SERVER,
    score_signal,
)
from services.shared.config import get_openrouter_api_key
from services.shared.mcp_client import resolve_and_call

FLAGS = flags.FLAGS
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL"
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL")
flags.DEFINE_integer(
    "poll_interval_seconds", 10, "Seconds between polling for new signals"
)

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

    openrouter_api_key = get_openrouter_api_key()
    if not openrouter_api_key:
        logging.error("OPENROUTER_API_KEY environment variable is required")
        sys.exit(1)

    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url,
        "market": FLAGS.mcp_market_url,
        "signal": FLAGS.mcp_signal_url,
    }

    logging.info("Opportunity Scorer Agent starting")
    logging.info("Poll interval: %d seconds", FLAGS.poll_interval_seconds)

    while not _shutdown:
        try:
            # Fetch the most recent unscored signal
            signals = resolve_and_call(
                "get_recent_signals",
                {"limit": 1},
                TOOL_TO_MCP_SERVER,
                mcp_urls,
                return_type="parsed",
            )

            if signals and isinstance(signals, list) and len(signals) > 0:
                signal_data = signals[0]
                logging.info(
                    "Scoring signal %s for %s",
                    signal_data.get("signal_id", "unknown"),
                    signal_data.get("symbol", "unknown"),
                )
                result = score_signal(signal_data, openrouter_api_key, mcp_urls)
                if result:
                    logging.info(
                        "Scored signal %s: score=%s tier=%s",
                        signal_data.get("signal_id", "unknown"),
                        result.get("score"),
                        result.get("tier"),
                    )
                else:
                    logging.info("No result for signal scoring")
            else:
                logging.info("No signals to score")
        except Exception as e:
            logging.error("Error in scoring loop: %s", e)

        if FLAGS.poll_interval_seconds <= 0:
            break

        for _ in range(FLAGS.poll_interval_seconds):
            if _shutdown:
                break
            time.sleep(1)

    logging.info("Opportunity Scorer Agent shut down.")


if __name__ == "__main__":
    app.run(main)
