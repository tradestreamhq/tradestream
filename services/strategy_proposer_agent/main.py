"""Entry point for the Strategy Proposer Agent service.

Runs as a long-lived service with health checks and graceful shutdown,
periodically proposing new trading strategies.
"""

from absl import app, flags, logging

from services.strategy_proposer_agent.agent import run_proposer_agent
from services.shared.service_runner import ServiceRunner

FLAGS = flags.FLAGS

flags.DEFINE_string("openrouter_api_key", None, "OpenRouter API key.")
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL."
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL.")
flags.DEFINE_integer(
    "interval_seconds", 1800, "Interval between strategy proposal runs in seconds."
)
flags.DEFINE_integer("health_port", 8080, "Port for health check HTTP server.")

flags.mark_flag_as_required("openrouter_api_key")


def _propose_strategies():
    """Run one iteration of strategy proposal."""
    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url.rstrip("/"),
        "market": FLAGS.mcp_market_url.rstrip("/"),
    }

    logging.info("Proposing new strategy...")
    result = run_proposer_agent(
        api_key=FLAGS.openrouter_api_key,
        mcp_urls=mcp_urls,
    )
    if result:
        logging.info("Proposer result: %s", result[:500])
    else:
        logging.warning("No result from proposer agent.")


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    runner = ServiceRunner(
        service_name="strategy_proposer_agent",
        interval_seconds=FLAGS.interval_seconds,
        task_fn=_propose_strategies,
        health_port=FLAGS.health_port,
    )
    runner.run()


if __name__ == "__main__":
    app.run(main)
