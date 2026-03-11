"""Entry point for the Top Crypto Updater service.

Runs as a long-lived service with health checks and graceful shutdown,
periodically fetching top cryptocurrency symbols from CoinMarketCap
and updating Redis.
"""

import os
import sys
import json

import redis as redis_lib
from absl import app, flags, logging

from services.top_crypto_updater.redis_client import RedisManager
from services.shared.service_runner import ServiceRunner
from shared.cryptoclient.cmc_client import get_top_n_crypto_symbols

FLAGS = flags.FLAGS

# CoinMarketCap Flags
flags.DEFINE_string("cmc_api_key", os.getenv("CMC_API_KEY"), "CoinMarketCap API Key.")
flags.DEFINE_integer(
    "top_n_cryptos",
    int(os.getenv("TOP_N_CRYPTOS", "20")),
    "Number of top cryptocurrencies to fetch from CMC.",
)

# Redis Flags
default_redis_host = os.getenv("REDIS_HOST", "localhost")
flags.DEFINE_string("redis_host", default_redis_host, "Redis host.")
default_redis_port = int(os.getenv("REDIS_PORT", "6379"))
flags.DEFINE_integer("redis_port", default_redis_port, "Redis port.")
flags.DEFINE_string(
    "redis_password", os.getenv("REDIS_PASSWORD"), "Redis password (if any)."
)
default_redis_key = os.getenv("REDIS_KEY", "top_cryptocurrencies")
flags.DEFINE_string(
    "redis_key",
    default_redis_key,
    "Redis key to store the list of top cryptocurrencies.",
)

# Service flags
flags.DEFINE_integer(
    "interval_seconds", 900, "Interval between updates in seconds (default 15 min)."
)
flags.DEFINE_integer("health_port", 8080, "Port for health check HTTP server.")

# Module-level RedisManager reused across iterations.
_redis_manager = None


def _initialize_redis():
    """Create the RedisManager once and reuse it."""
    global _redis_manager
    if _redis_manager is not None:
        return
    _redis_manager = RedisManager(
        host=FLAGS.redis_host, port=FLAGS.redis_port, password=FLAGS.redis_password
    )
    if not _redis_manager.get_client():
        raise ConnectionError("Failed to connect to Redis")
    logging.info("Redis connection established")


def _update_top_cryptos():
    """Fetch top crypto symbols from CMC and update Redis."""
    _initialize_redis()

    logging.info("Fetching top %d cryptocurrency symbols from CoinMarketCap...", FLAGS.top_n_cryptos)
    top_symbols = get_top_n_crypto_symbols(FLAGS.cmc_api_key, FLAGS.top_n_cryptos)

    if not top_symbols:
        logging.warning("No symbols fetched from CoinMarketCap. Nothing to update.")
        return

    logging.info("Successfully fetched symbols: %s", top_symbols)
    symbols_json = json.dumps(top_symbols)
    if _redis_manager.set_value(FLAGS.redis_key, symbols_json):
        logging.info("Successfully updated Redis key '%s'.", FLAGS.redis_key)
    else:
        logging.error("Failed to update Redis key '%s'.", FLAGS.redis_key)


def main(argv):
    del argv
    logging.set_verbosity(logging.INFO)

    if not FLAGS.cmc_api_key:
        logging.error("CMC_API_KEY is required. Set environment variable or use --cmc_api_key.")
        sys.exit(1)

    runner = ServiceRunner(
        service_name="top_crypto_updater",
        interval_seconds=FLAGS.interval_seconds,
        task_fn=_update_top_cryptos,
        health_port=FLAGS.health_port,
    )
    runner.run()


if __name__ == "__main__":
    app.run(main)
