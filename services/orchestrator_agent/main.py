"""Entry point for the Orchestrator Agent."""

import signal
import sys

from absl import app, flags, logging

from services.orchestrator_agent.health_monitor import HealthMonitor
from services.orchestrator_agent.orchestrator import run_orchestrator_loop
from services.orchestrator_agent.scheduler import Scheduler

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL."
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL.")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL.")
flags.DEFINE_string(
    "signal_generator_url",
    "http://localhost:9001",
    "Signal Generator agent HTTP URL.",
)
flags.DEFINE_string(
    "opportunity_scorer_url",
    "http://localhost:9002",
    "Opportunity Scorer agent HTTP URL.",
)
flags.DEFINE_string(
    "strategy_proposer_url",
    "http://localhost:9003",
    "Strategy Proposer agent HTTP URL.",
)
flags.DEFINE_integer(
    "signal_interval_seconds",
    60,
    "Interval between signal generation runs in seconds.",
)
flags.DEFINE_integer(
    "strategy_proposer_interval_seconds",
    1800,
    "Interval between strategy proposer runs in seconds.",
)
flags.DEFINE_string(
    "fallback_symbols",
    "BTC-USD,ETH-USD",
    "Comma-separated fallback symbols if market-mcp is unreachable.",
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

    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url.rstrip("/"),
        "market": FLAGS.mcp_market_url.rstrip("/"),
        "signal": FLAGS.mcp_signal_url.rstrip("/"),
    }

    agent_urls = {
        "signal_generator": FLAGS.signal_generator_url.rstrip("/"),
        "opportunity_scorer": FLAGS.opportunity_scorer_url.rstrip("/"),
        "strategy_proposer": FLAGS.strategy_proposer_url.rstrip("/"),
    }

    fallback_symbols = [
        s.strip() for s in FLAGS.fallback_symbols.split(",") if s.strip()
    ]

    scheduler = Scheduler(
        signal_interval=FLAGS.signal_interval_seconds,
        strategy_proposer_interval=FLAGS.strategy_proposer_interval_seconds,
    )
    health_monitor = HealthMonitor()

    logging.info(
        "Orchestrator Agent started. Signal interval: %ds, "
        "Strategy proposer interval: %ds",
        FLAGS.signal_interval_seconds,
        FLAGS.strategy_proposer_interval_seconds,
    )

    run_orchestrator_loop(
        mcp_urls=mcp_urls,
        agent_urls=agent_urls,
        scheduler=scheduler,
        health_monitor=health_monitor,
        shutdown_check=lambda: _shutdown,
        fallback_symbols=fallback_symbols,
    )

    logging.info("Orchestrator Agent shut down.")


if __name__ == "__main__":
    app.run(main)
