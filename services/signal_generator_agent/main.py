"""Entry point for the Signal Generator Agent service.

Runs as a long-lived service with health checks and graceful shutdown,
periodically generating trading signals for configured symbols.
"""

import sys

from absl import app, flags, logging

from services.signal_generator_agent.agent import run_agent_for_symbol
from services.shared.service_runner import ServiceRunner
from services.shared.structured_logger import StructuredLogger

FLAGS = flags.FLAGS

flags.DEFINE_string("openrouter_api_key", None, "OpenRouter API key.")
flags.DEFINE_string(
    "symbols",
    "BTC-USD,ETH-USD",
    "Comma-separated list of symbols to generate signals for.",
)
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL."
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL.")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL.")
flags.DEFINE_integer(
    "interval_seconds", 60, "Interval between signal generation runs in seconds."
)
flags.DEFINE_integer("health_port", 8080, "Port for health check HTTP server.")

flags.mark_flag_as_required("openrouter_api_key")

_log = StructuredLogger(service_name="signal_generator_agent")


def _generate_signals():
    """Run one iteration of signal generation for all configured symbols."""
    symbols = [s.strip() for s in FLAGS.symbols.split(",") if s.strip()]
    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url.rstrip("/"),
        "market": FLAGS.mcp_market_url.rstrip("/"),
        "signal": FLAGS.mcp_signal_url.rstrip("/"),
    }

    for symbol in symbols:
        try:
            _log.info("Generating signal", symbol=symbol)
            result = run_agent_for_symbol(
                symbol=symbol,
                api_key=FLAGS.openrouter_api_key,
                mcp_urls=mcp_urls,
            )
            if result:
                _log.info("Signal result", symbol=symbol, result=result[:500])
            else:
                _log.warning("No result", symbol=symbol)
        except Exception as e:
            _log.exception("Error generating signal", symbol=symbol, error=str(e))


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    symbols = [s.strip() for s in FLAGS.symbols.split(",") if s.strip()]
    if not symbols:
        _log.error("No symbols configured.")
        sys.exit(1)

    runner = ServiceRunner(
        service_name="signal_generator_agent",
        interval_seconds=FLAGS.interval_seconds,
        task_fn=_generate_signals,
        health_port=FLAGS.health_port,
    )
    runner.run()


if __name__ == "__main__":
    app.run(main)
