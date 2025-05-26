"""
Strategy Discovery Request Factory - Cron Job Version

This service runs as a cron job to:
1. Fetch crypto symbols from Redis
2. Poll InfluxDB for new candle data
3. Process candles through strategy discovery processor
4. Publish strategy discovery requests to Kafka

Designed to run once per execution via cron.
"""

import sys
from absl import app, flags, logging
import redis
from services.strategy_discovery_request_factory.config import (
    FIBONACCI_WINDOWS_MINUTES,
    DEQUE_MAXLEN,
    DEFAULT_TOP_N,
    DEFAULT_MAX_GENERATIONS,
    DEFAULT_POPULATION_SIZE,
    CANDLE_GRANULARITY_MINUTES,
)
from services.strategy_discovery_request_factory.influx_poller import InfluxPoller
from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)
from services.strategy_discovery_request_factory.kafka_publisher import KafkaPublisher
from shared.persistence.last_processed_tracker import LastProcessedTracker

# Redis flags
flags.DEFINE_string("redis_host", "localhost", "Redis host")
flags.DEFINE_integer("redis_port", 6379, "Redis port")
flags.DEFINE_integer("redis_db", 0, "Redis database number")
flags.DEFINE_string("redis_password", None, "Redis password (if required)")
flags.DEFINE_string(
    "crypto_symbols_key", "crypto:symbols", "Redis key containing crypto symbols set"
)

# InfluxDB flags
flags.DEFINE_string("influxdb_url", "http://localhost:8086", "InfluxDB URL")
flags.DEFINE_string("influxdb_token", None, "InfluxDB authentication token")
flags.DEFINE_string("influxdb_org", None, "InfluxDB organization")
flags.DEFINE_string("influxdb_bucket", "marketdata", "InfluxDB bucket name")

# Kafka flags
flags.DEFINE_string(
    "kafka_bootstrap_servers", "localhost:9092", "Kafka bootstrap servers"
)
flags.DEFINE_string(
    "kafka_topic", "strategy-discovery-requests", "Kafka topic for publishing requests"
)

# Processing flags
flags.DEFINE_integer(
    "lookback_minutes", 60, "Lookback window in minutes for fetching candles"
)
flags.DEFINE_list(
    "fibonacci_windows_minutes",
    FIBONACCI_WINDOWS_MINUTES,
    "Fibonacci windows in minutes",
)
flags.DEFINE_integer("deque_maxlen", DEQUE_MAXLEN, "Maximum length of candle deques")
flags.DEFINE_integer(
    "default_top_n", DEFAULT_TOP_N, "Default number of top strategies to discover"
)
flags.DEFINE_integer(
    "default_max_generations", DEFAULT_MAX_GENERATIONS, "Default GA max generations"
)
flags.DEFINE_integer(
    "default_population_size", DEFAULT_POPULATION_SIZE, "Default GA population size"
)
flags.DEFINE_integer(
    "candle_granularity_minutes",
    CANDLE_GRANULARITY_MINUTES,
    "Candle granularity in minutes",
)

# Persistence flags
flags.DEFINE_string(
    "tracker_file_path",
    "/tmp/strategy_discovery_last_processed.json",
    "Path to last processed timestamp tracker file",
)

FLAGS = flags.FLAGS


def get_crypto_symbols_from_redis(
    redis_client: redis.Redis, symbols_key: str
) -> list[str]:
    """
    Fetch crypto symbols from Redis.

    Args:
        redis_client: Redis client instance
        symbols_key: Redis key containing the symbols set

    Returns:
        List of crypto symbols in format like ['btcusd', 'ethusd']

    Raises:
        Exception: If Redis fetch fails or no symbols found
    """
    try:
        # Assume symbols are stored as a Redis set
        symbols = redis_client.smembers(symbols_key)
        if not symbols:
            raise ValueError(f"No crypto symbols found in Redis key: {symbols_key}")

        # Convert bytes to strings and return
        symbol_strings = [symbol.decode("utf-8") for symbol in symbols]
        logging.info(
            f"Fetched {len(symbol_strings)} crypto symbols from Redis: {symbol_strings}"
        )
        return symbol_strings

    except redis.RedisError as e:
        raise Exception(f"Failed to fetch crypto symbols from Redis: {e}")


def convert_symbol_to_currency_pair(symbol: str) -> str:
    """
    Convert symbol format from Redis to currency pair format.

    Args:
        symbol: Symbol like 'btcusd'

    Returns:
        Currency pair like 'BTC/USD'
    """
    if len(symbol) < 6:
        raise ValueError(f"Invalid symbol format: {symbol}")

    # Assume format is like 'btcusd' -> 'BTC/USD'
    base = symbol[:-3].upper()  # Everything except last 3 chars
    quote = symbol[-3:].upper()  # Last 3 chars
    return f"{base}/{quote}"


def main(argv):
    """Main cron job execution function."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments.")

    # Validate required flags
    if not FLAGS.influxdb_token:
        logging.error("InfluxDB token is required. Set --influxdb_token")
        sys.exit(1)

    if not FLAGS.influxdb_org:
        logging.error("InfluxDB organization is required. Set --influxdb_org")
        sys.exit(1)

    logging.set_verbosity(logging.INFO)
    logging.info("Starting Strategy Discovery Request Factory Cron Job")

    try:
        # Initialize Redis client
        redis_client = redis.Redis(
            host=FLAGS.redis_host,
            port=FLAGS.redis_port,
            db=FLAGS.redis_db,
            password=FLAGS.redis_password,
            decode_responses=False,  # We handle decoding manually
        )

        # Test Redis connection
        redis_client.ping()
        logging.info(f"Connected to Redis at {FLAGS.redis_host}:{FLAGS.redis_port}")

        # Fetch crypto symbols from Redis
        crypto_symbols = get_crypto_symbols_from_redis(
            redis_client, FLAGS.crypto_symbols_key
        )
        if not crypto_symbols:
            logging.error("No crypto symbols retrieved from Redis")
            sys.exit(1)

        # Convert symbols to currency pairs
        currency_pairs = [
            convert_symbol_to_currency_pair(symbol) for symbol in crypto_symbols
        ]
        logging.info(f"Processing currency pairs: {currency_pairs}")

        # Initialize components
        last_processed_tracker = LastProcessedTracker(FLAGS.tracker_file_path)

        influx_poller = InfluxPoller(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket,
        )

        strategy_discovery_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[int(x) for x in FLAGS.fibonacci_windows_minutes],
            deque_maxlen=FLAGS.deque_maxlen,
            default_top_n=FLAGS.default_top_n,
            default_max_generations=FLAGS.default_max_generations,
            default_population_size=FLAGS.default_population_size,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
        )

        kafka_publisher = KafkaPublisher(
            bootstrap_servers=FLAGS.kafka_bootstrap_servers, topic=FLAGS.kafka_topic
        )

        # Initialize deques for all currency pairs
        strategy_discovery_processor.initialize_deques(currency_pairs)

        # Process each currency pair
        total_requests_published = 0

        for currency_pair in currency_pairs:
            logging.info(f"Processing currency pair: {currency_pair}")

            try:
                # Get last processed timestamp for this pair
                last_timestamp = last_processed_tracker.get_last_timestamp(
                    currency_pair
                )

                # Calculate lookback timestamp if this is the first run
                if last_timestamp == 0:
                    # Use lookback_minutes for initial fetch
                    import time

                    current_time_ms = int(time.time() * 1000)
                    last_timestamp = current_time_ms - (
                        FLAGS.lookback_minutes * 60 * 1000
                    )
                    logging.info(
                        f"First run for {currency_pair}, using lookback timestamp: {last_timestamp}"
                    )

                # Fetch new candles
                candles, latest_timestamp = influx_poller.fetch_new_candles(
                    currency_pair, last_timestamp
                )

                if not candles:
                    logging.info(f"No new candles for {currency_pair}")
                    continue

                logging.info(f"Fetched {len(candles)} new candles for {currency_pair}")

                # Process each candle
                pair_requests_published = 0
                for candle in candles:
                    # Generate strategy discovery requests
                    discovery_requests = strategy_discovery_processor.add_candle(candle)

                    # Publish each request
                    for request in discovery_requests:
                        kafka_publisher.publish_request(request, currency_pair)
                        pair_requests_published += 1
                        total_requests_published += 1

                # Update last processed timestamp
                if latest_timestamp > last_timestamp:
                    last_processed_tracker.set_last_timestamp(
                        currency_pair, latest_timestamp
                    )
                    logging.info(
                        f"Updated last timestamp for {currency_pair}: {latest_timestamp}"
                    )

                logging.info(
                    f"Published {pair_requests_published} requests for {currency_pair}"
                )

            except Exception as e:
                logging.error(f"Error processing {currency_pair}: {e}")
                # Continue with other pairs rather than failing completely
                continue

        logging.info(
            f"Cron job completed. Total requests published: {total_requests_published}"
        )

        # Clean up
        influx_poller.close()
        kafka_publisher.close()
        redis_client.close()

    except Exception as e:
        logging.error(f"Cron job failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    app.run(main)
