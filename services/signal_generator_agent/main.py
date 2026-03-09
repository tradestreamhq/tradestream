"""Entry point for the Signal Generator Agent."""

import signal
import sys
import time

from absl import app, flags, logging

from services.signal_generator_agent.agent import run_agent_for_symbol

FLAGS = flags.FLAGS

flags.DEFINE_string("openrouter_api_key", None, "OpenRouter API key.")
flags.DEFINE_string("symbols", "BTC-USD,ETH-USD", "Comma-separated list of symbols to generate signals for.")
flags.DEFINE_string("mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL.")
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL.")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL.")
flags.DEFINE_integer("interval_seconds", 60, "Interval between signal generation runs in seconds.")

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

    symbols = [s.strip() for s in FLAGS.symbols.split(",") if s.strip()]
    if not symbols:
        logging.error("No symbols configured.")
        sys.exit(1)

    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url.rstrip("/"),
        "market": FLAGS.mcp_market_url.rstrip("/"),
        "signal": FLAGS.mcp_signal_url.rstrip("/"),
    }

    logging.info("Signal Generator Agent started. Symbols: %s, Interval: %ds",
                 symbols, FLAGS.interval_seconds)

    while not _shutdown:
        for symbol in symbols:
            if _shutdown:
                break
            try:
                logging.info("Generating signal for %s", symbol)
                result = run_agent_for_symbol(
                    symbol=symbol,
                    api_key=FLAGS.openrouter_api_key,
                    mcp_urls=mcp_urls,
                )
                if result:
                    logging.info("Signal result for %s: %s", symbol, result[:500])
                else:
                    logging.warning("No result for %s", symbol)
            except Exception as e:
                logging.exception("Error generating signal for %s: %s", symbol, e)

        if not _shutdown:
            logging.info("Sleeping %ds before next run...", FLAGS.interval_seconds)
            for _ in range(FLAGS.interval_seconds):
                if _shutdown:
                    break
                time.sleep(1)

    logging.info("Signal Generator Agent shut down.")


if __name__ == "__main__":
    app.run(main)
