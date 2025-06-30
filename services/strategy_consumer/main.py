"""
Main application for the strategy consumer service.
Consumes discovered strategies from Kafka and stores them in PostgreSQL.
Runs as a cron job that processes messages and winds down when no work is available.
"""

import asyncio
import signal
import sys
import time
from typing import List

from absl import app
from absl import flags
from absl import logging

from services.strategy_consumer.kafka_consumer import StrategyKafkaConsumer
from services.strategy_consumer.postgres_client import PostgresClient

FLAGS = flags.FLAGS

# Kafka Configuration Flags
flags.DEFINE_string(
    "kafka_bootstrap_servers",
    "localhost:9092",
    "Kafka bootstrap servers.",
)
flags.DEFINE_string(
    "kafka_topic",
    "discovered-strategies",
    "Kafka topic for discovered strategies.",
)
flags.DEFINE_string(
    "kafka_group_id",
    "strategy_consumer_group",
    "Kafka consumer group ID.",
)
flags.DEFINE_string(
    "kafka_auto_offset_reset",
    "latest",
    "Kafka auto offset reset policy (earliest/latest).",
)

# PostgreSQL Configuration Flags
flags.DEFINE_string(
    "postgres_host",
    "localhost",
    "PostgreSQL host.",
)
flags.DEFINE_integer(
    "postgres_port",
    5432,
    "PostgreSQL port.",
)
flags.DEFINE_string(
    "postgres_database",
    "tradestream",
    "PostgreSQL database name.",
)
flags.DEFINE_string(
    "postgres_username",
    "postgres",
    "PostgreSQL username.",
)
flags.DEFINE_string(
    "postgres_password",
    "",
    "PostgreSQL password.",
)

# Processing Configuration Flags
flags.DEFINE_integer(
    "batch_size",
    100,
    "Maximum number of strategies to process in a batch.",
)
flags.DEFINE_integer(
    "poll_timeout_ms",
    1000,
    "Timeout for polling Kafka messages in milliseconds.",
)
flags.DEFINE_integer(
    "idle_timeout_seconds",
    60,
    "Timeout for idle periods before winding down.",
)
flags.DEFINE_integer(
    "max_processing_time_seconds",
    300,
    "Maximum time to process messages before winding down.",
)

# Connection Configuration Flags
flags.DEFINE_integer(
    "postgres_min_connections",
    1,
    "Minimum PostgreSQL connection pool size.",
)
flags.DEFINE_integer(
    "postgres_max_connections",
    10,
    "Maximum PostgreSQL connection pool size.",
)

# Service Configuration
SERVICE_NAME = "strategy_consumer"


class StrategyConsumerService:
    """Main service class for consuming and storing strategies."""

    def __init__(self):
        self.kafka_consumer: Optional[StrategyKafkaConsumer] = None
        self.postgres_client: Optional[PostgresClient] = None
        self.is_running = False
        self.processed_count = 0
        self.start_time = None

    async def initialize(self) -> None:
        """Initialize Kafka consumer and PostgreSQL client."""
        logging.info("Initializing strategy consumer service")

        # Initialize PostgreSQL client
        self.postgres_client = PostgresClient(
            host=FLAGS.postgres_host,
            port=FLAGS.postgres_port,
            database=FLAGS.postgres_database,
            username=FLAGS.postgres_username,
            password=FLAGS.postgres_password,
            min_connections=FLAGS.postgres_min_connections,
            max_connections=FLAGS.postgres_max_connections,
        )

        # Connect to PostgreSQL
        await self.postgres_client.connect()
        await self.postgres_client.ensure_table_exists()

        # Initialize Kafka consumer
        self.kafka_consumer = StrategyKafkaConsumer(
            bootstrap_servers=FLAGS.kafka_bootstrap_servers,
            topic=FLAGS.kafka_topic,
            group_id=FLAGS.kafka_group_id,
            auto_offset_reset=FLAGS.kafka_auto_offset_reset,
        )

        # Connect to Kafka
        self.kafka_consumer.connect()

        # Set up the processor callback
        self.kafka_consumer.set_processor_callback(self._process_strategies)

        logging.info("Strategy consumer service initialized successfully")

    async def _process_strategies(self, strategies: List[dict]) -> None:
        """Process a batch of strategies by storing them in PostgreSQL."""
        if not self.postgres_client:
            logging.error("PostgreSQL client not initialized")
            return

        try:
            processed_count = await self.postgres_client.insert_strategies(strategies)
            self.processed_count += processed_count
            
            logging.info(f"Processed {processed_count} strategies (total: {self.processed_count})")
            
        except Exception as e:
            logging.error(f"Failed to process strategies: {e}")

    async def run(self) -> None:
        """Run the main service loop."""
        if not self.kafka_consumer or not self.postgres_client:
            raise RuntimeError("Service not properly initialized")

        self.is_running = True
        self.start_time = time.time()
        
        logging.info("Starting strategy consumer service")
        logging.info(f"Configuration: batch_size={FLAGS.batch_size}, "
                    f"poll_timeout={FLAGS.poll_timeout_ms}ms, "
                    f"idle_timeout={FLAGS.idle_timeout_seconds}s")

        try:
            # Start consuming messages
            await self.kafka_consumer.consume_messages(
                batch_size=FLAGS.batch_size,
                timeout_ms=FLAGS.poll_timeout_ms
            )

        except KeyboardInterrupt:
            logging.info("Received interrupt signal, shutting down gracefully")
        except Exception as e:
            logging.error(f"Error in service loop: {e}")
            raise
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.is_running = False
        
        logging.info("Cleaning up resources")
        
        if self.kafka_consumer:
            self.kafka_consumer.stop()
            self.kafka_consumer.close()
            
        if self.postgres_client:
            await self.postgres_client.close()
            
        if self.start_time:
            runtime = time.time() - self.start_time
            logging.info(f"Service runtime: {runtime:.2f} seconds")
            logging.info(f"Total strategies processed: {self.processed_count}")

    def stop(self) -> None:
        """Stop the service."""
        self.is_running = False
        if self.kafka_consumer:
            self.kafka_consumer.stop()


async def main_async() -> None:
    """Main async function."""
    # Validate required flags
    if not FLAGS.postgres_password:
        logging.error("PostgreSQL password is required")
        sys.exit(1)

    # Create and run the service
    service = StrategyConsumerService()
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, shutting down gracefully")
        service.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await service.initialize()
        await service.run()
    except Exception as e:
        logging.error(f"Service failed: {e}")
        sys.exit(1)


def main(argv):
    """Main function."""
    # Parse command line arguments
    app.parse_flags_with_usage(argv)
    
    # Set up logging
    logging.set_verbosity(logging.INFO)
    
    # Run the async main function
    asyncio.run(main_async())


if __name__ == "__main__":
    app.run(main) 