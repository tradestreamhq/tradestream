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
from services.shared.config import get_cmc_api_key, get_redis_config


FLAGS = flags.FLAGS

# Non-credential flags
flags.DEFINE_integer(
    "top_n_cryptos",
    int(os.getenv("TOP_N_CRYPTOS", "20")),
    "Number of top cryptocurrencies to fetch from CMC.",
)
flags.DEFINE_string(
    "redis_key",
    os.getenv("REDIS_KEY", "top_cryptocurrencies"),
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

    cmc_api_key = get_cmc_api_key()
    if not cmc_api_key:
        logging.error(
            "CMC_API_KEY is required. Set the CMC_API_KEY environment variable."
        )
        sys.exit(1)

    redis_cfg = get_redis_config()

    logging.info("Configuration:")
    logging.info(f"  CoinMarketCap API Key: {'****' if cmc_api_key else 'Not Set'}")
    logging.info(f"  Top N Cryptos: {FLAGS.top_n_cryptos}")
    logging.info(f"  Redis Host: {redis_cfg['host']}")
    logging.info(f"  Redis Port: {redis_cfg['port']}")
    logging.info(f"  Redis Key: {FLAGS.redis_key}")

    try:
        redis_manager_global = RedisManager(
            host=redis_cfg["host"],
            port=redis_cfg["port"],
            password=redis_cfg["password"],
        )
        if not redis_manager_global.get_client():
            logging.error("Failed to connect to Redis (client check). Exiting.")
            sys.exit(1)
    except redis.exceptions.RedisError as e:
        logging.error(f"Failed to initialize RedisManager: {e}. Exiting.")
        sys.exit(1)
    # If Redis initialization failed and exited, the rest of the `try` block for symbol fetching won't run.

    try:
        logging.info(
            f"Fetching top {FLAGS.top_n_cryptos} cryptocurrency symbols from CoinMarketCap..."
        )
        top_symbols_tiingo_format = get_top_n_crypto_symbols(
            cmc_api_key, FLAGS.top_n_cryptos
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

    except SystemExit:  # Explicitly catch SystemExit from a previous sys.exit()
        raise  # Re-raise to ensure the script terminates
    except Exception as e:
        logging.exception(f"An error occurred during the update process: {e}")
        sys.exit(1)  # This is the second potential exit point if other errors occur
    finally:
        if redis_manager_global:
            redis_manager_global.close()
        logging.info("Top Crypto Updater CronJob finished.")


if __name__ == "__main__":
    app.run(main)
