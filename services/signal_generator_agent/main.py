"""Entry point for the Signal Generator Agent."""

import signal
import sys
import time

from absl import app, flags, logging

from services.signal_generator_agent.agent import generate_signal

FLAGS = flags.FLAGS

flags.DEFINE_string("openrouter_api_key", "", "OpenRouter API key")
flags.DEFINE_string(
    "symbols", "BTC-USD,ETH-USD", "Comma-separated list of symbols to generate signals for"
)
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL"
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL")
flags.DEFINE_integer(
    "interval_seconds", 60, "Seconds between signal generation cycles"
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

    if not FLAGS.openrouter_api_key:
        logging.error("--openrouter_api_key is required")
        sys.exit(1)

    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url,
        "market": FLAGS.mcp_market_url,
        "signal": FLAGS.mcp_signal_url,
    }

    symbols = [s.strip() for s in FLAGS.symbols.split(",") if s.strip()]
    if not symbols:
        logging.error("No symbols specified")
        sys.exit(1)

    logging.info("Signal Generator Agent starting")
    logging.info("Symbols: %s", symbols)
    logging.info("Interval: %d seconds", FLAGS.interval_seconds)

    while not _shutdown:
        for symbol in symbols:
            if _shutdown:
                break
            try:
                logging.info("Generating signal for %s", symbol)
                result = generate_signal(symbol, FLAGS.openrouter_api_key, mcp_urls)
                if result:
                    if result.get("skipped"):
                        logging.info(
                            "Skipped %s: %s",
                            symbol,
                            result.get("reason", "duplicate"),
                        )
                    else:
                        logging.info(
                            "Signal for %s: %s (confidence: %s)",
                            symbol,
                            result.get("action", "unknown"),
                            result.get("confidence", "N/A"),
                        )
                else:
                    logging.warning("No result for %s", symbol)
            except Exception as e:
                logging.error("Error generating signal for %s: %s", symbol, e)

        if FLAGS.interval_seconds <= 0:
            break

        for _ in range(FLAGS.interval_seconds):
            if _shutdown:
                break
            time.sleep(1)

    logging.info("Signal Generator Agent shut down.")


if __name__ == "__main__":
    app.run(main)
