"""
Strategy Discovery Request Factory - Cron Job

This service runs as a cron job to:
1. Process configured currency pairs
2. Poll InfluxDB for new candle data using InfluxDBLastProcessedTracker for state
3. Process candles through strategy discovery processor
4. Publish strategy discovery requests to Kafka

Currency pairs are configured via flags, not fetched from Redis.
"""

import sys
import time
from typing import List
from absl import app, flags, logging

from services.strategy_discovery_request_factory.config import (
    FIBONACCI_WINDOWS_MINUTES,
    DEQUE_MAXLEN,
    DEFAULT_TOP_N,
    DEFAULT_MAX_GENERATIONS,
    DEFAULT_POPULATION_SIZE,
    CANDLE_GRANULARITY_MINUTES,
    validate_fibonacci_windows,
    validate_deque_maxlen,
    validate_ga_parameters,
)
from services.strategy_discovery_request_factory.influx_poller import InfluxPoller
from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)
from services.strategy_discovery_request_factory.kafka_publisher import KafkaPublisher
from shared.persistence.influxdb_last_processed_tracker import InfluxDBLastProcessedTracker

# Currency pair configuration
flags.DEFINE_list(
    "currency_pairs",
    ["BTC/USD", "ETH/USD", "ADA/USD", "SOL/USD", "DOGE/USD"],
    "List of currency pairs to process",
)

# InfluxDB flags
flags.DEFINE_string("influxdb_url", "http://localhost:8086", "InfluxDB URL")
flags.DEFINE_string("influxdb_token", None, "InfluxDB token")
flags.DEFINE_string("influxdb_org", None, "InfluxDB organization")
flags.DEFINE_string("influxdb_bucket_candles", "tradestream-data", "Candles bucket")
flags.DEFINE_string("influxdb_bucket_tracker", "tradestream-data", "Tracker bucket")
flags.DEFINE_string(
    "tracker_service_name", 
    "strategy_discovery", 
    "Service name for tracker"
)

# Kafka flags
flags.DEFINE_string("kafka_bootstrap_servers", "localhost:9092", "Kafka servers")
flags.DEFINE_string("kafka_topic", "strategy-discovery-requests", "Kafka topic")

# Processing flags
flags.DEFINE_integer("lookback_minutes", 60 * 24 * 7, "Lookback window for first run")
flags.DEFINE_list("fibonacci_windows_minutes", [str(x) for x in FIBONACCI_WINDOWS_MINUTES], "Fibonacci windows")
flags.DEFINE_integer("deque_maxlen", DEQUE_MAXLEN, "Max deque length")
flags.DEFINE_integer("default_top_n", DEFAULT_TOP_N, "Default top N strategies")
flags.DEFINE_integer("default_max_generations", DEFAULT_MAX_GENERATIONS, "GA generations")
flags.DEFINE_integer("default_population_size", DEFAULT_POPULATION_SIZE, "GA population")
flags.DEFINE_integer("candle_granularity_minutes", CANDLE_GRANULARITY_MINUTES, "Candle granularity")

FLAGS = flags.FLAGS


class StrategyDiscoveryService:
    """Main service orchestrator for strategy discovery request generation."""
    
    def __init__(self):
        self.influx_poller = None
        self.kafka_publisher = None
        self.strategy_processor = None
        self.timestamp_tracker = None
        
    def _validate_configuration(self) -> None:
        """Validate all configuration parameters."""
        if not FLAGS.influxdb_token:
            raise ValueError("InfluxDB token is required (--influxdb_token)")
        if not FLAGS.influxdb_org:
            raise ValueError("InfluxDB organization is required (--influxdb_org)")
        
        # Validate currency pairs
        if not FLAGS.currency_pairs:
            raise ValueError("At least one currency pair must be specified")
        
        for pair in FLAGS.currency_pairs:
            if "/" not in pair:
                raise ValueError(f"Invalid currency pair format: {pair}. Expected format: BASE/QUOTE")
        
        # Validate processing parameters
        fibonacci_windows = [int(x) for x in FLAGS.fibonacci_windows_minutes]
        if not validate_fibonacci_windows(fibonacci_windows):
            raise ValueError(f"Invalid fibonacci windows: {fibonacci_windows}")
        
        if not validate_deque_maxlen(FLAGS.deque_maxlen):
            raise ValueError(f"Invalid deque maxlen: {FLAGS.deque_maxlen}")
        
        if not validate_ga_parameters(FLAGS.default_max_generations, FLAGS.default_population_size):
            raise ValueError(f"Invalid GA parameters: {FLAGS.default_max_generations}, {FLAGS.default_population_size}")
        
        if FLAGS.lookback_minutes <= 0:
            raise ValueError("Lookback minutes must be positive")
        
        if FLAGS.candle_granularity_minutes <= 0:
            raise ValueError("Candle granularity must be positive")
    
    def _connect_influxdb(self) -> None:
        """Connect to InfluxDB for candle data and timestamp tracking."""
        # Timestamp tracker
        self.timestamp_tracker = InfluxDBLastProcessedTracker(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket_tracker,
        )
        if not self.timestamp_tracker.client:
            raise ConnectionError("Failed to connect to InfluxDB for timestamp tracking")
        
        # Candle data poller
        self.influx_poller = InfluxPoller(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket_candles,
        )
        if not self.influx_poller.client:
            raise ConnectionError("Failed to connect to InfluxDB for candle data")
            
        logging.info("Connected to InfluxDB for candles and tracking")
    
    def _connect_kafka(self) -> None:
        """Connect to Kafka for publishing requests."""
        self.kafka_publisher = KafkaPublisher(
            bootstrap_servers=FLAGS.kafka_bootstrap_servers,
            topic_name=FLAGS.kafka_topic,
        )
        if not self.kafka_publisher.producer:
            raise ConnectionError("Failed to connect to Kafka")
        logging.info("Connected to Kafka")
    
    def _initialize_processor(self) -> None:
        """Initialize the strategy discovery processor."""
        fibonacci_windows = [int(x) for x in FLAGS.fibonacci_windows_minutes]
        
        self.strategy_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=fibonacci_windows,
            deque_maxlen=FLAGS.deque_maxlen,
            default_top_n=FLAGS.default_top_n,
            default_max_generations=FLAGS.default_max_generations,
            default_population_size=FLAGS.default_population_size,
            candle_granularity_minutes=FLAGS.candle_granularity_minutes,
            tracker=self.timestamp_tracker,
            service_identifier=FLAGS.tracker_service_name,
        )
        logging.info("Initialized strategy discovery processor")
    
    def _process_currency_pair(self, currency_pair: str) -> int:
        """Process a single currency pair and return number of requests published."""
        logging.info(f"Processing {currency_pair}")
        
        try:
            # Determine starting timestamp
            last_processed_ts = (
                self.strategy_processor.last_processed_timestamps.get(currency_pair, 0)
            )
            
            if last_processed_ts > 0:
                # Resume from last processed
                start_fetch_ts = last_processed_ts
                logging.info(f"Resuming {currency_pair} from timestamp {start_fetch_ts}")
            else:
                # First run - use lookback
                current_time_ms = int(time.time() * 1000)
                start_fetch_ts = current_time_ms - (FLAGS.lookback_minutes * 60 * 1000)
                logging.info(f"First run for {currency_pair}, using lookback from {start_fetch_ts}")
            
            # Fetch new candles
            candles, latest_ts = self.influx_poller.fetch_new_candles(
                currency_pair, start_fetch_ts
            )
            
            if not candles:
                logging.info(f"No new candles for {currency_pair}")
                return 0
            
            logging.info(f"Fetched {len(candles)} new candles for {currency_pair}")
            
            # Process candles and publish requests
            total_requests = 0
            for candle in candles:
                discovery_requests = self.strategy_processor.add_candle(candle)
                for request in discovery_requests:
                    self.kafka_publisher.publish_request(request, currency_pair)
                    total_requests += 1
            
            logging.info(f"Published {total_requests} discovery requests for {currency_pair}")
            return total_requests
            
        except Exception as e:
            logging.error(f"Error processing {currency_pair}: {e}")
            return 0
    
    def run(self) -> None:
        """Run the main cron job logic."""
        try:
            # Validate configuration
            self._validate_configuration()
            logging.info(f"Processing {len(FLAGS.currency_pairs)} currency pairs: {FLAGS.currency_pairs}")
            
            # Connect to all services
            self._connect_influxdb()
            self._connect_kafka()
            self._initialize_processor()
            
            # Initialize processor with all pairs
            self.strategy_processor.initialize_pairs(FLAGS.currency_pairs)
            
            # Process each currency pair
            total_requests_published = 0
            successful_pairs = 0
            failed_pairs = 0
            
            for currency_pair in FLAGS.currency_pairs:
                try:
                    pair_requests = self._process_currency_pair(currency_pair)
                    total_requests_published += pair_requests
                    successful_pairs += 1
                except Exception as e:
                    logging.error(f"Failed to process {currency_pair}: {e}")
                    failed_pairs += 1
                    continue
            
            logging.info(
                f"Cron job completed. "
                f"Total requests: {total_requests_published}, "
                f"Successful pairs: {successful_pairs}, "
                f"Failed pairs: {failed_pairs}"
            )
            
            if failed_pairs > 0 and successful_pairs == 0:
                raise Exception("All currency pairs failed to process")
                
        except Exception as e:
            logging.exception(f"Cron job failed: {e}")
            raise
    
    def close(self) -> None:
        """Clean up all connections."""
        if self.influx_poller:
            self.influx_poller.close()
        if self.kafka_publisher:
            self.kafka_publisher.close()
        if self.timestamp_tracker:
            self.timestamp_tracker.close()
        if self.strategy_processor:
            self.strategy_processor.close()
        logging.info("All connections closed")


def main(argv):
    """Main entry point."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")
    
    logging.set_verbosity(logging.INFO)
    logging.info("Starting Strategy Discovery Request Factory Cron Job")
    
    # Log configuration
    logging.info("Configuration:")
    logging.info(f"  Currency pairs: {FLAGS.currency_pairs}")
    logging.info(f"  InfluxDB URL: {FLAGS.influxdb_url}")
    logging.info(f"  Kafka servers: {FLAGS.kafka_bootstrap_servers}")
    logging.info(f"  Kafka topic: {FLAGS.kafka_topic}")
    logging.info(f"  Lookback minutes: {FLAGS.lookback_minutes}")
    logging.info(f"  Fibonacci windows: {FLAGS.fibonacci_windows_minutes}")
    
    service = StrategyDiscoveryService()
    
    try:
        service.run()
        logging.info("Strategy Discovery Request Factory completed successfully")
    except Exception as e:
        logging.exception(f"Service failed: {e}")
        sys.exit(1)
    finally:
        service.close()


if __name__ == "__main__":
    app.run(main)
