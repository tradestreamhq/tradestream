"""Entry point for the Opportunity Scorer Agent service.

Runs as a long-lived service with health checks and graceful shutdown,
periodically polling for and scoring unscored trading signals.
"""

import sys

from absl import app, flags, logging

from services.opportunity_scorer_agent.agent import (
    TOOL_TO_MCP_SERVER,
    score_signal,
)
from services.shared.mcp_client import resolve_and_call
from services.shared.service_runner import ServiceRunner

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
flags.DEFINE_integer("health_port", 8080, "Port for health check HTTP server.")


def _score_signals():
    """Fetch and score the most recent unscored signal."""
    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url,
        "market": FLAGS.mcp_market_url,
        "signal": FLAGS.mcp_signal_url,
    }

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
        result = score_signal(signal_data, FLAGS.openrouter_api_key, mcp_urls)
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


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    if not FLAGS.openrouter_api_key:
        logging.error("--openrouter_api_key is required")
        sys.exit(1)

    runner = ServiceRunner(
        service_name="opportunity_scorer_agent",
        interval_seconds=FLAGS.poll_interval_seconds,
        task_fn=_score_signals,
        health_port=FLAGS.health_port,
    )
    runner.run()


if __name__ == "__main__":
    app.run(main)
