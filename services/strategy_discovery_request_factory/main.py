"""
Strategy Discovery Request Factory - Stateless Orchestration Service

This service runs as a cron job to:
1. Read "latest actual data timestamp" for each currency pair from InfluxDBLastProcessedTracker
   (populated by external services like candle ingestor)
2. Use the tracker to maintain its own state about which end_time it has processed for idempotency
3. Generate strategy discovery requests using the stateless processor for specific timepoints
4. Publish requests to Kafka

The InfluxPoller component has been removed - this service is now purely orchestrational.
"""

import sys
import time
from datetime import datetime, timezone
from typing import List, Optional
from absl import app, flags, logging

from services.strategy_discovery_request_factory.config import (
    FIBONACCI_WINDOWS_MINUTES,
    DEFAULT_TOP_N,
    DEFAULT_MAX_GENERATIONS,
    DEFAULT_POPULATION_SIZE,
    validate_fibonacci_windows,
    validate_ga_parameters,
)
from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)
from services.strategy_discovery_request_factory.kafka_publisher import KafkaPublisher
from shared.persistence.influxdb_last_processed_tracker import (
    InfluxDBLastProcessedTracker,
)

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
flags.DEFINE_string("influxdb_bucket_tracker", "tradestream-data", "Tracker bucket")
flags.DEFINE_string(
    "tracker_service_name",
    "strategy_discovery",
    "Service name for this service's tracker state",
)
flags.DEFINE_string(
    "global_status_tracker_service_name",
    "global_candle_status",
    "Service name registered in InfluxDBLastProcessedTracker by external services that report the latest ingested candle timestamps.",
)
flags.DEFINE_integer(
    "min_processing_advance_minutes",
    1,
    "Minimum number of minutes the latest actual data point for a pair must be beyond this service's last processed data point for that pair to trigger new request generation. Use 0 to process any newer data point.",
)

# Kafka flags
flags.DEFINE_string("kafka_bootstrap_servers", "localhost:9092", "Kafka servers")
flags.DEFINE_string("kafka_topic", "strategy-discovery-requests", "Kafka topic")

# Processing flags
flags.DEFINE_list(
    "fibonacci_windows_minutes",
    [str(x) for x in FIBONACCI_WINDOWS_MINUTES],
    "Fibonacci windows",
)
flags.DEFINE_integer("default_top_n", DEFAULT_TOP_N, "Default top N strategies")
flags.DEFINE_integer(
    "default_max_generations", DEFAULT_MAX_GENERATIONS, "GA generations"
)
flags.DEFINE_integer(
    "default_population_size", DEFAULT_POPULATION_SIZE, "GA population"
)

FLAGS = flags.FLAGS


class StrategyDiscoveryService:
    """Main service orchestrator for stateless strategy discovery request generation."""

    def __init__(self):
        self.kafka_publisher = None
        self.strategy_processor = None
        self.timestamp_tracker = None
        self.fibonacci_windows_config: List[int] = []

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
                raise ValueError(
                    f"Invalid currency pair format: {pair}. Expected format: BASE/QUOTE"
                )

        # Validate processing parameters
        fibonacci_windows = [int(x) for x in FLAGS.fibonacci_windows_minutes]
        if not validate_fibonacci_windows(fibonacci_windows):
            raise ValueError(f"Invalid fibonacci windows: {fibonacci_windows}")

        if not validate_ga_parameters(
            FLAGS.default_max_generations, FLAGS.default_population_size
        ):
            raise ValueError(
                f"Invalid GA parameters: {FLAGS.default_max_generations}, {FLAGS.default_population_size}"
            )

        if FLAGS.min_processing_advance_minutes < 0:
            raise ValueError("Minimum processing advance minutes must be non-negative")

    def _connect_kafka(self) -> None:
        """Connect to Kafka for publishing requests."""
        self.kafka_publisher = KafkaPublisher(
            bootstrap_servers=FLAGS.kafka_bootstrap_servers,
            topic_name=FLAGS.kafka_topic,
        )
        if not self.kafka_publisher.producer:
            raise ConnectionError("Failed to connect to Kafka")
        logging.info("Connected to Kafka")

    def _initialize_tracker(self) -> None:
        """Initialize the InfluxDB timestamp tracker."""
        self.timestamp_tracker = InfluxDBLastProcessedTracker(
            url=FLAGS.influxdb_url,
            token=FLAGS.influxdb_token,
            org=FLAGS.influxdb_org,
            bucket=FLAGS.influxdb_bucket_tracker,
        )
        if not self.timestamp_tracker.client:
            raise ConnectionError(
                "Failed to connect to InfluxDB for timestamp tracking"
            )
        logging.info("Connected to InfluxDB for timestamp tracking")

    def _initialize_processor(self) -> None:
        """Initialize the stateless strategy discovery processor."""
        fibonacci_windows = [int(x) for x in FLAGS.fibonacci_windows_minutes]
        self.fibonacci_windows_config = fibonacci_windows

        self.strategy_processor = StrategyDiscoveryProcessor(
            default_top_n=FLAGS.default_top_n,
            default_max_generations=FLAGS.default_max_generations,
            default_population_size=FLAGS.default_population_size,
        )
        logging.info("Initialized stateless strategy discovery processor")

    def _get_sdrf_processed_tracker_key(self, currency_pair: str) -> str:
        """Get the tracker key for this service's processed end timestamp for a currency pair."""
        return f"{FLAGS.tracker_service_name}_{currency_pair.replace('/', '_')}_sdrf_processed_end_ts"

    def _get_ingested_data_tracker_item_id(self, currency_pair: str) -> str:
        """Get the tracker item ID for the latest ingested data timestamp for a currency pair."""
        return f"{currency_pair.replace('/', '_')}_latest_ingested_ts"

    def run(self) -> None:
        """Run the main cron job logic."""
        try:
            self._validate_configuration()
            logging.info(
                f"Processing {len(FLAGS.currency_pairs)} currency pairs: {FLAGS.currency_pairs}"
            )

            # Connect to all services
            self._connect_kafka()
            self._initialize_tracker()
            self._initialize_processor()

            total_requests_published_all_pairs = 0
            successful_pairs_count = 0
            failed_pairs_count = 0

            for currency_pair in FLAGS.currency_pairs:
                pair_requests_published_this_run = 0
                try:
                    logging.info(f"Starting processing for {currency_pair}...")

                    # Get the latest actual data timestamp from global tracker (set by external services)
                    ingested_ts_item_id = self._get_ingested_data_tracker_item_id(
                        currency_pair
                    )
                    actual_latest_data_ts_ms = (
                        self.timestamp_tracker.get_last_processed_timestamp(
                            FLAGS.global_status_tracker_service_name,
                            ingested_ts_item_id,
                        )
                    )

                    if actual_latest_data_ts_ms is None:
                        logging.warning(
                            f"No 'latest ingested data timestamp' found in tracker for {currency_pair} under key ({FLAGS.global_status_tracker_service_name}, {ingested_ts_item_id}). This is normal if upstream data ingestion hasn't started yet. Skipping."
                        )
                        successful_pairs_count += 1
                        continue

                    window_end_time_utc = datetime.fromtimestamp(
                        actual_latest_data_ts_ms / 1000, tz=timezone.utc
                    )

                    # Get this service's last processed end timestamp for the pair
                    sdrf_tracker_key = self._get_sdrf_processed_tracker_key(
                        currency_pair
                    )
                    sdrf_last_processed_end_ts_ms = (
                        self.timestamp_tracker.get_last_processed_timestamp(
                            FLAGS.tracker_service_name, sdrf_tracker_key
                        )
                        or 0
                    )  # Default to 0 if no prior processing

                    # Check if there's sufficient advance to warrant processing
                    min_advance_required_ms = (
                        FLAGS.min_processing_advance_minutes * 60 * 1000
                    )
                    if (
                        actual_latest_data_ts_ms - sdrf_last_processed_end_ts_ms
                    ) < min_advance_required_ms:
                        logging.info(
                            f"Data for {currency_pair} (ends {window_end_time_utc.isoformat()}) has not advanced sufficiently "
                            f"beyond last processed point ({datetime.fromtimestamp(sdrf_last_processed_end_ts_ms / 1000, tz=timezone.utc).isoformat() if sdrf_last_processed_end_ts_ms > 0 else 'never'}). Skipping."
                        )
                        successful_pairs_count += (
                            1  # Count as success if no work needed due to idempotency
                        )
                        continue

                    # Generate strategy discovery requests for this timepoint
                    logging.info(
                        f"Generating requests for {currency_pair} with window ending at {window_end_time_utc.isoformat()}."
                    )
                    discovery_requests = (
                        self.strategy_processor.generate_requests_for_timepoint(
                            currency_pair,
                            window_end_time_utc,
                            self.fibonacci_windows_config,
                        )
                    )

                    # Publish all generated requests
                    for request in discovery_requests:
                        self.kafka_publisher.publish_request(request, currency_pair)
                        pair_requests_published_this_run += 1

                    # Update tracker only if new requests were generated
                    if discovery_requests:
                        self.timestamp_tracker.update_last_processed_timestamp(
                            FLAGS.tracker_service_name,
                            sdrf_tracker_key,
                            actual_latest_data_ts_ms,
                        )
                        logging.info(
                            f"Published {pair_requests_published_this_run} requests for {currency_pair} and updated SDRF tracker to {window_end_time_utc.isoformat()}."
                        )
                    else:
                        logging.info(
                            f"No new requests were generated by the processor for {currency_pair} ending at {window_end_time_utc.isoformat()}."
                        )

                    successful_pairs_count += 1
                    total_requests_published_all_pairs += (
                        pair_requests_published_this_run
                    )

                except Exception as e:
                    logging.exception(
                        f"Error processing currency pair {currency_pair}: {e}"
                    )
                    failed_pairs_count += 1
                    # Continue to the next pair

            logging.info(
                f"Cron job completed. Total requests: {total_requests_published_all_pairs}, "
                f"Successful pairs: {successful_pairs_count}, Failed pairs: {failed_pairs_count}"
            )
            if failed_pairs_count > 0 and successful_pairs_count == 0:
                raise Exception(
                    "All currency pairs failed to process in StrategyDiscoveryService."
                )

        except Exception as e:
            logging.exception(f"StrategyDiscoveryService run failed: {e}")
            raise

    def close(self) -> None:
        """Clean up all connections."""
        if self.kafka_publisher:
            self.kafka_publisher.close()
        if self.timestamp_tracker:
            self.timestamp_tracker.close()
        logging.info("All connections closed")


def main(argv):
    """Main entry point."""
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments")

    logging.set_verbosity(logging.INFO)
    logging.info(
        "Starting Strategy Discovery Request Factory Cron Job (Stateless Orchestration)"
    )

    # Log configuration
    logging.info("Configuration:")
    logging.info(f"  Currency pairs: {FLAGS.currency_pairs}")
    logging.info(f"  InfluxDB URL: {FLAGS.influxdb_url}")
    logging.info(f"  Kafka servers: {FLAGS.kafka_bootstrap_servers}")
    logging.info(f"  Kafka topic: {FLAGS.kafka_topic}")
    logging.info(f"  Tracker service name: {FLAGS.tracker_service_name}")
    logging.info(
        f"  Global status service name: {FLAGS.global_status_tracker_service_name}"
    )
    logging.info(
        f"  Min processing advance (minutes): {FLAGS.min_processing_advance_minutes}"
    )
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
