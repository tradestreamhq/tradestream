"""Entry point for the Opportunity Scorer Agent."""

import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from absl import app, flags, logging

from services.opportunity_scorer_agent.agent import (
    TOOL_TO_MCP_SERVER,
    score_signal,
)
from services.shared.mcp_client import resolve_and_call

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
flags.DEFINE_integer(
    "batch_size", 10, "Number of signals to fetch and score per poll cycle"
)

_shutdown = False


def _handle_shutdown(signum, frame):
    global _shutdown
    logging.info("Received signal %d, shutting down...", signum)
    _shutdown = True


def _score_one(signal_data, api_key, mcp_urls):
    """Score a single signal, returning (signal_data, result)."""
    result = score_signal(signal_data, api_key, mcp_urls)
    return signal_data, result


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

    logging.info("Opportunity Scorer Agent starting")
    logging.info("Poll interval: %d seconds", FLAGS.poll_interval_seconds)
    logging.info("Batch size: %d", FLAGS.batch_size)

    while not _shutdown:
        try:
            # Fetch a batch of unscored signals in one MCP call
            signals = resolve_and_call(
                "get_recent_signals",
                {"limit": FLAGS.batch_size},
                TOOL_TO_MCP_SERVER,
                mcp_urls,
                return_type="parsed",
            )

            if signals and isinstance(signals, list) and len(signals) > 0:
                logging.info("Fetched %d signals to score", len(signals))

                # Score all signals concurrently instead of one at a time
                with ThreadPoolExecutor(max_workers=len(signals)) as executor:
                    futures = {
                        executor.submit(
                            _score_one,
                            sig,
                            FLAGS.openrouter_api_key,
                            mcp_urls,
                        ): sig
                        for sig in signals
                    }

                    for future in as_completed(futures):
                        sig = futures[future]
                        sid = sig.get("signal_id", "unknown")
                        try:
                            _, result = future.result()
                            if result:
                                logging.info(
                                    "Scored signal %s: score=%s tier=%s",
                                    sid,
                                    result.get("score"),
                                    result.get("tier"),
                                )
                            else:
                                logging.info("No result for signal %s", sid)
                        except Exception as e:
                            logging.error("Error scoring signal %s: %s", sid, e)
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
