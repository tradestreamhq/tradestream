"""Entry point for the Opportunity Scorer Agent."""

import json
import sys
import time

from absl import app, flags, logging

from services.opportunity_scorer_agent.agent import (
    _call_mcp_tool,
    score_signal,
)

FLAGS = flags.FLAGS

flags.DEFINE_string("openrouter_api_key", "", "OpenRouter API key")
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL"
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL")
flags.DEFINE_integer(
    "poll_interval_seconds", 10, "Seconds between polling for new signals"
)


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    if not FLAGS.openrouter_api_key:
        logging.error("--openrouter_api_key is required")
        sys.exit(1)

    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url,
        "market": FLAGS.mcp_market_url,
        "signal": FLAGS.mcp_signal_url,
    }

    logging.info("Opportunity Scorer Agent starting")
    logging.info("Poll interval: %d seconds", FLAGS.poll_interval_seconds)

    while True:
        try:
            # Fetch the most recent unscored signal
            signals = _call_mcp_tool("get_recent_signals", {"limit": 1}, mcp_urls)

            if signals and isinstance(signals, list) and len(signals) > 0:
                signal = signals[0]
                logging.info(
                    "Scoring signal %s for %s",
                    signal.get("signal_id", "unknown"),
                    signal.get("symbol", "unknown"),
                )
                result = score_signal(signal, FLAGS.openrouter_api_key, mcp_urls)
                if result:
                    logging.info(
                        "Scored signal %s: score=%s tier=%s",
                        signal.get("signal_id", "unknown"),
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
        time.sleep(FLAGS.poll_interval_seconds)


if __name__ == "__main__":
    app.run(main)
