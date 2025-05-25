import os
import sys
import signal
import json
import redis  # Import redis for exception handling

from absl import app
from absl import flags
from absl import logging

from services.top_crypto_updater.redis_client import RedisManager
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


# Global variable for shutdown handling
redis_manager_global = None


def handle_shutdown_signal(signum, frame):
    global redis_manager_global
    logging.info(
        f"Shutdown signal {signal.Signals(signum).name} received. Initiating graceful shutdown..."
    )
    if redis_manager_global:
        try:
            logging.info("Attempting to close Redis connection from signal handler...")
            redis_manager_global.close()
            logging.info("Redis connection closed via signal handler.")
        except Exception as e:
            logging.error(f"Error closing Redis connection from signal handler: {e}")
    sys.exit(0)


def main(argv):
    del argv  # Unused.
    global redis_manager_global
    logging.set_verbosity(logging.INFO)
    logging.info("Starting Top Crypto Updater CronJob...")

    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    if not FLAGS.cmc_api_key:
        logging.error(
            "CMC_API_KEY is required. Set environment variable or use --cmc_api_key."
        )
        sys.exit(1)

    logging.info("Configuration:")
    logging.info(
        f"  CoinMarketCap API Key: {'****' if FLAGS.cmc_api_key else 'Not Set'}"
    )
    logging.info(f"  Top N Cryptos: {FLAGS.top_n_cryptos}")
    logging.info(f"  Redis Host: {FLAGS.redis_host}")
    logging.info(f"  Redis Port: {FLAGS.redis_port}")
    logging.info(f"  Redis Key: {FLAGS.redis_key}")

    try:
        redis_manager_global = RedisManager(
            host=FLAGS.redis_host, port=FLAGS.redis_port, password=FLAGS.redis_password
        )
        if not redis_manager_global.get_client():
            logging.error("Failed to connect to Redis (client check). Exiting.")
            sys.exit(1)
    except redis.exceptions.RedisError as e:
        logging.error(f"Failed to initialize RedisManager: {e}. Exiting.")
        sys.exit(1)

    try:
        logging.info(
            f"Fetching top {FLAGS.top_n_cryptos} cryptocurrency symbols from CoinMarketCap..."
        )
        top_symbols_tiingo_format = get_top_n_crypto_symbols(
            FLAGS.cmc_api_key, FLAGS.top_n_cryptos
        )

        if not top_symbols_tiingo_format:
            logging.warning(
                "No symbols fetched from CoinMarketCap. Nothing to update in Redis."
            )
        else:
            logging.info(f"Successfully fetched symbols: {top_symbols_tiingo_format}")
            symbols_json = json.dumps(top_symbols_tiingo_format)
            if redis_manager_global.set_value(FLAGS.redis_key, symbols_json):
                logging.info(f"Successfully updated Redis key '{FLAGS.redis_key}'.")
            else:
                logging.error(f"Failed to update Redis key '{FLAGS.redis_key}'.")

    except Exception as e:
        logging.exception(f"An error occurred during the update process: {e}")
        sys.exit(1)
    finally:
        if redis_manager_global:
            redis_manager_global.close()
        logging.info("Top Crypto Updater CronJob finished.")


if __name__ == "__main__":
    app.run(main)
