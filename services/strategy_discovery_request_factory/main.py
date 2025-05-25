import os
import sys
import time
from absl import app
from absl import flags
from absl import logging

from services.strategy_discovery_request_factory import config
from services.strategy_discovery_request_factory.influx_poller import InfluxPoller
from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)
from services.strategy_discovery_request_factory.kafka_publisher import KafkaPublisher
from shared.cryptoclient.cmc_client import get_top_n_crypto_symbols

FLAGS = flags.FLAGS

flags.DEFINE_string(
    "cmc_api_key",
    config.CMC_API_KEY,
    "CoinMarketCap API Key. Can also be set via CMC_API_KEY env var.",
)
flags.DEFINE_integer(
    "top_n_cryptos", config.TOP_N_CRYPTOS, "Number of top cryptocurrencies to fetch."
)
flags.DEFINE_string("influxdb_url", config.INFLUXDB_URL, "InfluxDB URL.")
flags.DEFINE_string(
    "influxdb_token",
    config.INFLUXDB_TOKEN,
    "InfluxDB Token. Must be set via flag or INFLUXDB_TOKEN env var.",
)
flags.DEFINE_string(
    "influxdb_org",
    config.INFLUXDB_ORG,
    "InfluxDB Organization. Must be set via flag or INFLUXDB_ORG env var.",
)
flags.DEFINE_string(
    "influxdb_bucket_candles",
    config.INFLUXDB_BUCKET_CANDLES,
    "InfluxDB Bucket for candles.",
)
flags.DEFINE_string(
    "kafka_bootstrap_servers",
    config.KAFKA_BOOTSTRAP_SERVERS,
    "Kafka bootstrap servers.",
)
flags.DEFINE_string(
    "kafka_strategy_discovery_request_topic",
    config.KAFKA_STRATEGY_DISCOVERY_REQUEST_TOPIC,
    "Kafka topic for strategy discovery requests.",
)
flags.DEFINE_list(
    "fibonacci_windows_minutes",
    [str(w) for w in config.FIBONACCI_WINDOWS_MINUTES],
    "Comma-separated list of Fibonacci window sizes in minutes.",
)
flags.DEFINE_integer(
    "deque_maxlen", config.DEQUE_MAXLEN, "Maximum length for candle deques."
)
flags.DEFINE_integer(
    "default_top_n",
    config.DEFAULT_TOP_N,
    "Default number of top strategies to return.",
)
flags.DEFINE_integer(
    "default_max_generations",
    config.DEFAULT_MAX_GENERATIONS,
    "Default maximum generations for GA optimization.",
)
flags.DEFINE_integer(
    "default_population_size",
    config.DEFAULT_POPULATION_SIZE,
    "Default population size for GA optimization.",
)
flags.DEFINE_integer(
    "candle_granularity_minutes",
    config.CANDLE_GRANULARITY_MINUTES,
    "Granularity of candles in InfluxDB in minutes.",
)
flags.DEFINE_integer(
    "lookback_minutes",
    5,
    "How many minutes to look back for new candles (should be >= cron frequency).",
)


class LastProcessedTracker:
    """Simple file-based tracker for last processed timestamps per currency pair."""

    def __init__(self, filepath: str = "/tmp/last_processed_timestamps.txt"):
        self.filepath = filepath

    def get_last_timestamp(self, currency_pair: str) -> int:
        """Get last processed timestamp for a currency pair (returns 0 if not found)."""
        try:
            if not os.path.exists(self.filepath):
                return 0

            with open(self.filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line:
                        pair, timestamp_str = line.split("=", 1)
                        if pair == currency_pair:
                            return int(timestamp_str)
            return 0
        except Exception as e:
            logging.warning(
                f"Error reading last processed timestamp for {currency_pair}: {e}"
            )
            return 0

    def set_last_timestamp(self, currency_pair: str, timestamp_ms: int):
        """Set last processed timestamp for a currency pair."""
        try:
            # Read existing data
            existing_data = {}
            if os.path.exists(self.filepath):
                with open(self.filepath, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and "=" in line:
                            pair, timestamp_str = line.split("=", 1)
                            existing_data[pair] = timestamp_str

            # Update with new timestamp
            existing_data[currency_pair] = str(timestamp_ms)

            # Write back to file
            with open(self.filepath, "w") as f:
                for pair, timestamp_str in existing_data.items():
                    f.write(f"{pair}={timestamp_str}\n")

        except Exception as e:
            logging.error(
                f"Error saving last processed timestamp for {currency_pair}: {e}"
            )


def main(argv):
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    logging.info("Starting StrategyDiscoveryRequestFactory cron job...")

    # Validate required configurations
    if not FLAGS.cmc_api_key:
        logging.error("CMC_API_KEY is required. Set via flag or environment variable.")
        sys.exit(1)
    if not FLAGS.influxdb_token:
        logging.error(
            "INFLUXDB_TOKEN is required. Set via flag or environment variable."
        )
        sys.exit(1)
    if not FLAGS.influxdb_org:
        logging.error("INFLUXDB_ORG is required. Set via flag or environment variable.")
        sys.exit(1)

    influx_poller = None
    kafka_publisher = None

    try:
        # Initialize timestamp tracker
        timestamp_tracker = LastProcessedTracker()

        # Initialize components
        logging.info("Fetching top N crypto symbols...")
        currency_pairs_str = get_top_n_crypto_symbols(
            FLAGS.cmc_api_key, FLAGS.top_n_cryptos
        )
        if not currency_pairs_str:
            logging.error("Failed to fetch any currency pairs from CMC. Exiting.")
            sys.exit(1)

        # Convert symbols like "btcusd" to "BTC/USD"
        currency_pairs = [
            f"{s[:-3].upper()}/{s[-3:].upper()}" for s in currency_pairs_str
        ]
        logging.info(f"Processing currency pairs: {currency_pairs}")

        influx_poller = InfluxPoller(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket_candles,
        )

        fib_windows_minutes_int = [int(w) for w in FLAGS.fibonacci_windows_minutes]

        strategy_discovery_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=fib_windows_minutes_int,
            deque_maxlen=FLAGS.deque_maxlen,
            default_top_n=FLAGS.default_top_n,
            default_max_generations=FLAGS.default_max_generations,
            default_population_size=FLAGS.default_population_size,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
        )
        strategy_discovery_processor.initialize_deques(currency_pairs)

        kafka_publisher = KafkaPublisher(
            bootstrap_servers=FLAGS.kafka_bootstrap_servers,
            topic_name=FLAGS.kafka_strategy_discovery_request_topic,
        )

        # Process each currency pair
        total_requests_published = 0
        current_time_ms = int(time.time() * 1000)

        for pair in currency_pairs:
            logging.info(f"Processing {pair}...")

            # Get last processed timestamp for this pair
            last_timestamp_ms = timestamp_tracker.get_last_timestamp(pair)

            # If no previous timestamp, look back by lookback_minutes
            if last_timestamp_ms == 0:
                last_timestamp_ms = current_time_ms - (
                    FLAGS.lookback_minutes * 60 * 1000
                )
                logging.info(
                    f"No previous timestamp for {pair}, looking back {FLAGS.lookback_minutes} minutes"
                )

            # Fetch new candles since last processed timestamp
            new_candles, latest_ts_ms = influx_poller.fetch_new_candles(
                pair, last_timestamp_ms
            )

            if new_candles:
                logging.info(f"Processing {len(new_candles)} new candles for {pair}")

                # Process each candle to generate strategy discovery requests
                for candle in new_candles:
                    strategy_discovery_requests = (
                        strategy_discovery_processor.add_candle(candle)
                    )

                    # Publish each request
                    for request in strategy_discovery_requests:
                        kafka_publisher.publish_request(request, key=pair)
                        total_requests_published += 1

                # Update last processed timestamp
                timestamp_tracker.set_last_timestamp(pair, latest_ts_ms)
                logging.info(
                    f"Updated last processed timestamp for {pair} to {latest_ts_ms}"
                )

            else:
                logging.info(f"No new candles found for {pair}")

        logging.info(
            f"Cron job completed successfully. Published {total_requests_published} strategy discovery requests."
        )

    except Exception as e:
        logging.exception(
            f"Critical error in StrategyDiscoveryRequestFactory cron job: {e}"
        )
        sys.exit(1)

    finally:
        # Clean up resources
        if influx_poller:
            influx_poller.close()
        if kafka_publisher:
            kafka_publisher.close()
        logging.info("Cleanup complete.")


if __name__ == "__main__":
    app.run(main)
