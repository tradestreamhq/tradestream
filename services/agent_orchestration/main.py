"""Entry point for the Agent Orchestration Layer."""

import signal
import sys
import threading

from absl import app, flags, logging

from services.agent_orchestration.dashboard import create_dashboard_app
from services.agent_orchestration.orchestration_loop import run_orchestration_loop
from services.agent_orchestration.state import OrchestrationState
from services.shared.structured_logger import StructuredLogger

FLAGS = flags.FLAGS

flags.DEFINE_string("api_key", "", "LLM API key (OpenRouter).")
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL."
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL.")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL.")
flags.DEFINE_string(
    "mcp_backtest_url", "http://localhost:8083", "Backtest MCP server URL."
)
flags.DEFINE_integer(
    "cycle_interval_seconds",
    3600,
    "Interval between orchestration cycles in seconds.",
)
flags.DEFINE_string(
    "state_file",
    "/tmp/agent_orchestration_state.json",
    "Path to persist orchestration state.",
)
flags.DEFINE_integer(
    "dashboard_port",
    9010,
    "Port for the orchestration dashboard API.",
)
flags.DEFINE_boolean(
    "enable_dashboard",
    True,
    "Enable the dashboard HTTP server.",
)

_shutdown = False

_log = StructuredLogger(service_name="agent_orchestration")


def _handle_shutdown(signum, frame):
    global _shutdown
    _log.info("Received shutdown signal", signum=signum)
    _shutdown = True


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    _log.new_correlation_id()

    api_key = FLAGS.api_key
    if not api_key:
        import os

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        logging.error("No API key provided. Set --api_key or OPENROUTER_API_KEY.")
        sys.exit(1)

    mcp_urls = {
        "strategy": FLAGS.mcp_strategy_url.rstrip("/"),
        "market": FLAGS.mcp_market_url.rstrip("/"),
        "signal": FLAGS.mcp_signal_url.rstrip("/"),
        "backtest": FLAGS.mcp_backtest_url.rstrip("/"),
    }

    state = OrchestrationState(state_file=FLAGS.state_file)

    _log.info(
        "Agent Orchestration Layer starting",
        cycle_interval=FLAGS.cycle_interval_seconds,
        state_file=FLAGS.state_file,
        dashboard_port=FLAGS.dashboard_port if FLAGS.enable_dashboard else "disabled",
    )

    # Start dashboard in a background thread
    if FLAGS.enable_dashboard:
        dashboard_app = create_dashboard_app(state)
        dashboard_thread = threading.Thread(
            target=lambda: dashboard_app.run(
                host="0.0.0.0",
                port=FLAGS.dashboard_port,
                use_reloader=False,
            ),
            daemon=True,
        )
        dashboard_thread.start()
        _log.info("Dashboard started", port=FLAGS.dashboard_port)

    run_orchestration_loop(
        api_key=api_key,
        mcp_urls=mcp_urls,
        state=state,
        cycle_interval_seconds=FLAGS.cycle_interval_seconds,
        shutdown_check=lambda: _shutdown,
    )

    _log.info("Agent Orchestration Layer shut down.")


if __name__ == "__main__":
    app.run(main)
