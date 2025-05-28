"""
Strategy Discovery Request Factory - Cron Job Version

This service runs as a cron job to:
1. Fetch crypto symbols from Redis
2. Poll InfluxDB for new candle data for each symbol, using a persistent timestamp tracker.
3. Process candles through strategy discovery processor
4. Publish strategy discovery requests to Kafka

Designed to run once per execution via cron.
"""

import sys
import time 
from absl import app, flags, logging
import redis # For fetching symbols
import json # For parsing symbols from Redis

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
from shared.persistence.influxdb_last_processed_tracker import InfluxDBLastProcessedTracker # Using InfluxDB tracker

# Redis flags (for fetching symbols)
flags.DEFINE_string("redis_host", "localhost", "Redis host for fetching symbols.")
flags.DEFINE_integer("redis_port", 6379, "Redis port for fetching symbols.")
flags.DEFINE_integer("redis_db_symbols", 0, "Redis database number for symbols.") # Specific DB for symbols
flags.DEFINE_string("redis_password_symbols", None, "Redis password for symbols (if required).")
flags.DEFINE_string(
    "crypto_symbols_key", "top_cryptocurrencies", "Redis key containing top crypto symbols (JSON list string)."
)

# InfluxDB flags (for candle data AND for timestamp tracking)
flags.DEFINE_string("influxdb_url", "http://localhost:8086", "InfluxDB URL for candles and state.")
flags.DEFINE_string("influxdb_token", None, "InfluxDB authentication token.")
flags.DEFINE_string("influxdb_org", None, "InfluxDB organization.")
flags.DEFINE_string("influxdb_bucket_candles", "tradestream-data", "InfluxDB bucket for candle data.")
flags.DEFINE_string("influxdb_bucket_tracker", "tradestream-data", "InfluxDB bucket for timestamp tracker state.") # Can be same or different
flags.DEFINE_string(
    "influxdb_tracker_service_name", "strategy_discovery", "Service identifier for InfluxDB Last Processed Tracker."
)


# Kafka flags
flags.DEFINE_string(
    "kafka_bootstrap_servers", "localhost:9092", "Kafka bootstrap servers"
)
flags.DEFINE_string(
    "kafka_topic", "strategy-discovery-requests", "Kafka topic for publishing requests"
)

# Processing flags
flags.DEFINE_integer(
    "lookback_minutes", 60 * 24 * 7, "Lookback window in minutes for fetching candles on the first run for a symbol (default 1 week)."
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


FLAGS = flags.FLAGS


def get_crypto_symbols_from_redis( # Copied from top_crypto_updater for consistency
    redis_client: redis.Redis, symbols_key: str
) -> list[str]:
    try:
        symbols_json_str = redis_client.get(symbols_key)
        if not symbols_json_str:
            raise ValueError(f"No crypto symbols found in Redis key: {symbols_key}")

        symbol_strings = json.loads(symbols_json_str)

        if not isinstance(symbol_strings, list) or not all(isinstance(s, str) for s in symbol_strings):
            raise ValueError(f"Redis key {symbols_key} does not contain a valid JSON list of strings.")

        logging.info(
            f"Fetched {len(symbol_strings)} crypto symbols from Redis: {symbol_strings}"
        )
        return symbol_strings
    except redis.RedisError as e:
        raise Exception(f"Failed to fetch crypto symbols from Redis: {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON from Redis key {symbols_key}: {e}")
    except ValueError as e:
        raise Exception(f"Error processing symbols from Redis: {e}")

def convert_symbol_to_currency_pair(symbol: str) -> str: # Copied from this file's previous version
    if not isinstance(symbol, str) or len(symbol) < 4:
        logging.warning(f"Invalid symbol format for conversion: {symbol}. Returning as is.")
        return symbol.upper()
    try:
        if symbol.lower().endswith("usd"):
            base = symbol[:-3].upper()
            quote = "USD"
            return f"{base}/{quote}"
        elif symbol.lower().endswith("usdt"):
            base = symbol[:-4].upper()
            quote = "USDT"
            return f"{base}/{quote}"
        else:
            if '/' in symbol:
                parts = symbol.split('/')
                return f"{parts[0].upper()}/{parts[1].upper()}"
            elif '-' in symbol:
                parts = symbol.split('-')
                return f"{parts[0].upper()}/{parts[1].upper()}"
            else:
                base = symbol[:-3].upper()
                quote = symbol[-3:].upper()
                return f"{base}/{quote}"
    except Exception as e:
        logging.warning(f"Error converting symbol '{symbol}' to currency pair: {e}. Returning as uppercase.")
        return symbol.upper()


def main(argv):
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments.")

    if not FLAGS.influxdb_token:
        logging.error("InfluxDB token is required. Set --influxdb_token")
        sys.exit(1)
    if not FLAGS.influxdb_org:
        logging.error("InfluxDB organization is required. Set --influxdb_org")
        sys.exit(1)

    logging.set_verbosity(logging.INFO)
    logging.info("Starting Strategy Discovery Request Factory Cron Job")

    redis_client_symbols = None
    influx_poller = None
    kafka_publisher = None
    timestamp_tracker = None

    try:
        redis_client_symbols = redis.Redis(
            host=FLAGS.redis_host,
            port=FLAGS.redis_port,
            db=FLAGS.redis_db_symbols,
            password=FLAGS.redis_password_symbols,
            decode_responses=True, # For JSON string from symbols key
        )
        redis_client_symbols.ping()
        logging.info(f"Connected to Redis for symbols at {FLAGS.redis_host}:{FLAGS.redis_port}")

        raw_symbols = get_crypto_symbols_from_redis(
            redis_client_symbols, FLAGS.crypto_symbols_key
        )
        if not raw_symbols:
            logging.error("No crypto symbols retrieved from Redis. Exiting.")
            sys.exit(1)
        currency_pairs = [convert_symbol_to_currency_pair(s) for s in raw_symbols]
        logging.info(f"Processing currency pairs: {currency_pairs}")

        timestamp_tracker = InfluxDBLastProcessedTracker(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket_tracker, # Use specific bucket for tracker
        )
        if not timestamp_tracker.client: # Check if connection was successful
             logging.error("Failed to connect to InfluxDB for timestamp tracking. Exiting.")
             sys.exit(1)


        influx_poller = InfluxPoller(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket_candles, # Use specific bucket for candles
        )
        if not influx_poller.client: # Check if connection was successful
            logging.error("Failed to connect to InfluxDB for candle polling. Exiting.")
            sys.exit(1)


        strategy_discovery_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[int(x) for x in FLAGS.fibonacci_windows_minutes],
            deque_maxlen=FLAGS.deque_maxlen,
            default_top_n=FLAGS.default_top_n,
            default_max_generations=FLAGS.default_max_generations,
            default_population_size=FLAGS.default_population_size,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
        )

        kafka_publisher = KafkaPublisher(
            bootstrap_servers=FLAGS.kafka_bootstrap_servers, topic_name=FLAGS.kafka_topic
        )
        if not kafka_publisher.producer: # Check if connection was successful
            logging.error("Failed to connect to Kafka. Exiting.")
            sys.exit(1)


        strategy_discovery_processor.initialize_deques(currency_pairs)
        total_requests_published = 0

        for currency_pair in currency_pairs:
            logging.info(f"Processing currency pair: {currency_pair}")
            try:
                last_processed_ts_ms = timestamp_tracker.get_last_processed_timestamp(
                    service_identifier=FLAGS.influxdb_tracker_service_name, key=currency_pair
                )

                start_fetch_ts_ms = 0
                if last_processed_ts_ms is not None and last_processed_ts_ms > 0:
                    start_fetch_ts_ms = last_processed_ts_ms
                    logging.info(
                        f"Resuming fetch for {currency_pair} from timestamp: {start_fetch_ts_ms}"
                    )
                else:
                    current_time_ms = int(time.time() * 1000)
                    start_fetch_ts_ms = current_time_ms - (
                        FLAGS.lookback_minutes * 60 * 1000
                    )
                    logging.info(
                        f"First run for {currency_pair}, using lookback. Fetching from: {start_fetch_ts_ms}"
                    )
                
                candles, latest_candle_timestamp_ms = influx_poller.fetch_new_candles(
                    currency_pair, start_fetch_ts_ms
                )

                if not candles:
                    logging.info(f"No new candles for {currency_pair} since {start_fetch_ts_ms}")
                    if last_processed_ts_ms is not None and last_processed_ts_ms > 0 :
                        latest_candle_timestamp_ms = last_processed_ts_ms
                    else: 
                        latest_candle_timestamp_ms = start_fetch_ts_ms
                else:
                    logging.info(f"Fetched {len(candles)} new candles for {currency_pair}")
                    pair_requests_published = 0
                    for candle in candles:
                        discovery_requests = strategy_discovery_processor.add_candle(candle)
                        for request_proto in discovery_requests: # Renamed to avoid conflict
                            kafka_publisher.publish_request(request_proto, currency_pair)
                            pair_requests_published += 1
                    total_requests_published += pair_requests_published
                    logging.info(
                        f"Published {pair_requests_published} requests for {currency_pair}"
                    )
                
                if latest_candle_timestamp_ms > (last_processed_ts_ms or 0):
                    timestamp_tracker.update_last_processed_timestamp(
                        FLAGS.influxdb_tracker_service_name, currency_pair, latest_candle_timestamp_ms
                    )
                    logging.info(
                        f"Updated last timestamp for {currency_pair} to: {latest_candle_timestamp_ms}"
                    )
                elif (
                    last_processed_ts_ms is None
                ):  # First run, no candles found, still mark the attempt
                    timestamp_tracker.update_last_processed_timestamp(
                        FLAGS.influxdb_tracker_service_name,
                        currency_pair,
                        latest_candle_timestamp_ms,
                    )
                    logging.info(
                        f"Marked first run attempt for {currency_pair} at: {latest_candle_timestamp_ms}"
                    )

            except Exception as e:
                logging.error(f"Error processing {currency_pair}: {e}")
                continue

        logging.info(
            f"Cron job completed. Total requests published: {total_requests_published}"
        )

    except Exception as e:
        logging.exception(f"Cron job failed: {e}")
        sys.exit(1)
    finally:
        if redis_client_symbols:
            redis_client_symbols.close()
        if influx_poller:
            influx_poller.close()
        if kafka_publisher:
            kafka_publisher.close()
        if timestamp_tracker:
            timestamp_tracker.close()
        logging.info("Strategy Discovery Request Factory Cron Job finished.")


if __name__ == "__main__":
    app.run(main)