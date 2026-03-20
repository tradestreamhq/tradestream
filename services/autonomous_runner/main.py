"""Entry point for the Autonomous Signal Generation Pipeline."""

import threading

from absl import app, flags, logging

from services.autonomous_runner.config import Config
from services.autonomous_runner.dashboard import app as dashboard_app
from services.autonomous_runner.runner import AutonomousRunner

FLAGS = flags.FLAGS

flags.DEFINE_string("openrouter_api_key", None, "OpenRouter API key.")
flags.DEFINE_string(
    "symbols",
    "BTC-USD,ETH-USD,SOL-USD,DOGE-USD,AVAX-USD,LINK-USD",
    "Comma-separated list of symbols.",
)
flags.DEFINE_string(
    "mcp_strategy_url", "http://localhost:8080", "Strategy MCP server URL."
)
flags.DEFINE_string("mcp_market_url", "http://localhost:8081", "Market MCP server URL.")
flags.DEFINE_string("mcp_signal_url", "http://localhost:8082", "Signal MCP server URL.")
flags.DEFINE_string(
    "redis_url", "redis://localhost:6379", "Redis URL for locks and kill switch."
)
flags.DEFINE_integer(
    "interval_minutes", 1, "Interval between signal generation cycles."
)
flags.DEFINE_integer("dashboard_port", 8090, "Port for the pipeline dashboard API.")
flags.DEFINE_boolean("enable_dashboard", True, "Enable the pipeline dashboard API.")

flags.mark_flag_as_required("openrouter_api_key")


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    config = Config(
        schedule=f"*/{FLAGS.interval_minutes} * * * *",
        symbols=[s.strip() for s in FLAGS.symbols.split(",") if s.strip()],
        mcp_strategy_url=FLAGS.mcp_strategy_url.rstrip("/"),
        mcp_market_url=FLAGS.mcp_market_url.rstrip("/"),
        mcp_signal_url=FLAGS.mcp_signal_url.rstrip("/"),
        redis_url=FLAGS.redis_url,
        openrouter_api_key=FLAGS.openrouter_api_key,
    )

    # Try to connect to Redis for kill switch and locks
    redis_client = None
    try:
        import redis

        redis_client = redis.Redis.from_url(FLAGS.redis_url)
        redis_client.ping()
        logging.info("Connected to Redis at %s", FLAGS.redis_url)
    except Exception as e:
        logging.warning("Redis not available, running without kill switch: %s", e)
        redis_client = None

    runner = AutonomousRunner(config, redis_client=redis_client)

    # Start dashboard in a separate thread if enabled
    if FLAGS.enable_dashboard:

        def run_dashboard():
            import uvicorn

            uvicorn.run(
                dashboard_app,
                host="0.0.0.0",
                port=FLAGS.dashboard_port,
                log_level="warning",
            )

        dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
        dashboard_thread.start()
        logging.info("Dashboard API started on port %d", FLAGS.dashboard_port)

    # Start the runner (blocks until shutdown)
    runner.start()


if __name__ == "__main__":
    app.run(main)
