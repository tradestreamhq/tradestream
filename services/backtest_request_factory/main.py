import os
import signal
import sys
import time
from absl import app
from absl import flags
from absl import logging
from google.protobuf import any_pb2

from services.backtest_request_factory import config
from services.backtest_request_factory.influx_poller import InfluxPoller
from services.backtest_request_factory.candle_processor import CandleProcessor
from services.backtest_request_factory.kafka_publisher import KafkaPublisher
from shared.cryptoclient.cmc_client import get_top_n_crypto_symbols

FLAGS = flags.FLAGS

flags.DEFINE_string("cmc_api_key", config.CMC_API_KEY, "CoinMarketCap API Key. Can also be set via CMC_API_KEY env var.")
flags.DEFINE_integer("top_n_cryptos", config.TOP_N_CRYPTOS, "Number of top cryptocurrencies to fetch.")
flags.DEFINE_string("influxdb_url", config.INFLUXDB_URL, "InfluxDB URL.")
flags.DEFINE_string("influxdb_token", config.INFLUXDB_TOKEN, "InfluxDB Token. Must be set via flag or INFLUXDB_TOKEN env var.")
flags.DEFINE_string("influxdb_org", config.INFLUXDB_ORG, "InfluxDB Organization. Must be set via flag or INFLUXDB_ORG env var.")
flags.DEFINE_string("influxdb_bucket_candles", config.INFLUXDB_BUCKET_CANDLES, "InfluxDB Bucket for candles.")
flags.DEFINE_string("kafka_bootstrap_servers", config.KAFKA_BOOTSTRAP_SERVERS, "Kafka bootstrap servers.")
flags.DEFINE_string("kafka_backtest_request_topic", config.KAFKA_BACKTEST_REQUEST_TOPIC, "Kafka topic for backtest requests.")
flags.DEFINE_integer("polling_interval_seconds", config.POLLING_INTERVAL_SECONDS, "Polling interval for InfluxDB.")
flags.DEFINE_list("fibonacci_windows_minutes", [str(w) for w in config.FIBONACCI_WINDOWS_MINUTES], "Comma-separated list of Fibonacci window sizes in minutes.")
flags.DEFINE_integer("deque_maxlen", config.DEQUE_MAXLEN, "Maximum length for candle deques.")
flags.DEFINE_enum("default_strategy_type", config.DEFAULT_STRATEGY_TYPE.name, [name for name, value in config.StrategyType.items()], "Default StrategyType for BacktestRequest.")
flags.DEFINE_integer("candle_granularity_minutes", config.CANDLE_GRANULARITY_MINUTES, "Granularity of candles in InfluxDB in minutes.")


shutdown_requested = False
influx_poller_global: InfluxPoller = None
kafka_publisher_global: KafkaPublisher = None

def handle_shutdown_signal(signum, frame):
    global shutdown_requested, influx_poller_global, kafka_publisher_global
    logging.info(f"Shutdown signal {signal.Signals(signum).name} received. Initiating graceful shutdown...")
    shutdown_requested = True
    if influx_poller_global:
        influx_poller_global.close()
    if kafka_publisher_global:
        kafka_publisher_global.close()

def main(argv):
    global shutdown_requested, influx_poller_global, kafka_publisher_global
    del argv  # Unused.
    logging.set_verbosity(logging.INFO)
    logging.info("Starting BacktestRequestFactory service...")

    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    # Validate required configurations
    if not FLAGS.cmc_api_key:
        logging.error("CMC_API_KEY is required. Set via flag or environment variable.")
        sys.exit(1)
    if not FLAGS.influxdb_token:
        logging.error("INFLUXDB_TOKEN is required. Set via flag or environment variable.")
        sys.exit(1)
    if not FLAGS.influxdb_org:
        logging.error("INFLUXDB_ORG is required. Set via flag or environment variable.")
        sys.exit(1)

    try:
        # Initialize components
        logging.info("Fetching top N crypto symbols...")
        currency_pairs_str = get_top_n_crypto_symbols(FLAGS.cmc_api_key, FLAGS.top_n_cryptos)
        if not currency_pairs_str:
            logging.error("Failed to fetch any currency pairs from CMC. Exiting.")
            sys.exit(1)
        # The shared client returns symbols like "btcusd", BacktestRequestFactory expects "BTC/USD"
        currency_pairs = [f"{s[:-3].upper()}/{s[-3:].upper()}" for s in currency_pairs_str]
        logging.info(f"Monitoring currency pairs: {currency_pairs}")

        influx_poller_global = InfluxPoller(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket_candles
        )

        fib_windows_minutes_int = [int(w) for w in FLAGS.fibonacci_windows_minutes]
        default_strategy_parameters = any_pb2.Any() # Create an empty Any message

        candle_processor = CandleProcessor(
            fibonacci_windows_minutes=fib_windows_minutes_int,
            deque_maxlen=FLAGS.deque_maxlen,
            default_strategy_type=config.StrategyType.Value(FLAGS.default_strategy_type),
            default_strategy_parameters_any=default_strategy_parameters,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes
        )
        candle_processor.initialize_deques(currency_pairs)

        kafka_publisher_global = KafkaPublisher(
            bootstrap_servers=FLAGS.kafka_bootstrap_servers,
            topic_name=FLAGS.kafka_backtest_request_topic
        )

        last_polled_timestamps_ms: dict[str, int] = {pair: 0 for pair in currency_pairs}

        logging.info("Initialization complete. Starting polling loop.")
        while not shutdown_requested:
            loop_start_time = time.monotonic()
            for pair in currency_pairs:
                if shutdown_requested:
                    break
                logging.info(f"Polling InfluxDB for new candles for {pair} since {last_polled_timestamps_ms.get(pair, 0)}ms")
                new_candles, latest_ts_ms = influx_poller_global.fetch_new_candles(
                    pair, last_polled_timestamps_ms.get(pair, 0)
                )

                if new_candles:
                    logging.info(f"Fetched {len(new_candles)} new candles for {pair}.")
                    for candle in new_candles: # Process candles one by one to maintain order
                        backtest_requests = candle_processor.add_candle(candle)
                        for req in backtest_requests:
                            kafka_publisher_global.publish_request(req, key=pair)
                    last_polled_timestamps_ms[pair] = latest_ts_ms
                else:
                    logging.info(f"No new candles found for {pair}.")
                
                if shutdown_requested: break
                time.sleep(1) # Small delay between pairs if many are configured

            if shutdown_requested:
                break

            loop_duration = time.monotonic() - loop_start_time
            sleep_time = FLAGS.polling_interval_seconds - loop_duration
            if sleep_time > 0:
                logging.info(f"Polling cycle finished in {loop_duration:.2f}s. Sleeping for {sleep_time:.2f}s.")
                for _ in range(int(sleep_time)): # Allow interruption during sleep
                    if shutdown_requested: break
                    time.sleep(1)
            else:
                logging.warning(f"Polling cycle duration ({loop_duration:.2f}s) exceeded interval ({FLAGS.polling_interval_seconds}s).")

    except Exception as e:
        logging.exception(f"Critical error in BacktestRequestFactory main loop: {e}")
    finally:
        logging.info("BacktestRequestFactory service shutting down.")
        if influx_poller_global:
            influx_poller_global.close()
        if kafka_publisher_global:
            kafka_publisher_global.close()
        logging.info("Shutdown complete.")
        sys.exit(0 if shutdown_requested else 1)

if __name__ == "__main__":
    app.run(main)
