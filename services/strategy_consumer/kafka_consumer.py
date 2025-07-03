"""
Kafka consumer for the strategy consumer service.
Reads discovered strategies from the Kafka topic and processes them.
"""

import asyncio
import json
import logging
import time
from typing import List, Optional, Callable, Awaitable

from kafka import KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable
from absl import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Import Protocol Buffer generated classes
from protos.discovery_pb2 import DiscoveredStrategy
from protos.strategies_pb2 import StrategyType
from google.protobuf import any_pb2
from google.protobuf import timestamp_pb2

# Define retry parameters for Kafka operations
kafka_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((KafkaError, NoBrokersAvailable, ConnectionError)),
    reraise=True,
)


class StrategyKafkaConsumer:
    """Kafka consumer for discovered strategies."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str = "strategy_consumer_group",
        auto_offset_reset: str = "latest",
        enable_auto_commit: bool = True,
        auto_commit_interval_ms: int = 5000,
        session_timeout_ms: int = 30000,
        heartbeat_interval_ms: int = 3000,
        max_poll_records: int = 500,
        max_poll_interval_ms: int = 300000,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.auto_commit_interval_ms = auto_commit_interval_ms
        self.session_timeout_ms = session_timeout_ms
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.max_poll_records = max_poll_records
        self.max_poll_interval_ms = max_poll_interval_ms

        self.consumer: Optional[KafkaConsumer] = None
        self.is_running = False
        self.processor_callback: Optional[Callable[[List[dict]], Awaitable[None]]] = (
            None
        )

    @retry(**kafka_retry_params)
    def connect(self) -> None:
        """Establish connection to Kafka."""
        try:
            logging.info(f"Connecting to Kafka at {self.bootstrap_servers}")

            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                auto_commit_interval_ms=self.auto_commit_interval_ms,
                session_timeout_ms=self.session_timeout_ms,
                heartbeat_interval_ms=self.heartbeat_interval_ms,
                max_poll_records=self.max_poll_records,
                max_poll_interval_ms=self.max_poll_interval_ms,
                # Remove UTF-8 deserializers - we'll handle binary data directly
                consumer_timeout_ms=1000,  # 1 second timeout for polling
            )

            logging.info(f"Successfully connected to Kafka topic: {self.topic}")
        except Exception as e:
            logging.error(f"Failed to connect to Kafka: {e}")
            self.consumer = None
            raise

    def close(self) -> None:
        """Close the Kafka consumer."""
        if self.consumer:
            self.consumer.close()
            logging.info("Kafka consumer closed")

    def set_processor_callback(
        self, callback: Callable[[List[dict]], Awaitable[None]]
    ) -> None:
        """Set the callback function to process strategies."""
        self.processor_callback = callback

    def _parse_strategy_message(self, message_bytes: bytes) -> Optional[dict]:
        """
        Parse a strategy message from Kafka binary Protocol Buffer data.

        Args:
            message_bytes: Binary Protocol Buffer data containing DiscoveredStrategy

        Returns:
            Parsed strategy dictionary or None if parsing fails
        """
        try:
            # Deserialize the Protocol Buffer message
            discovered_strategy = DiscoveredStrategy.FromString(message_bytes)

            # Extract basic fields
            strategy = {
                "symbol": discovered_strategy.symbol,
                "strategy_type": discovered_strategy.strategy.type.name,
                "current_score": discovered_strategy.score,
                "strategy_hash": self._generate_strategy_hash(discovered_strategy.strategy),
                "discovery_symbol": discovered_strategy.symbol,
                "discovery_start_time": self._timestamp_to_iso(discovered_strategy.start_time),
                "discovery_end_time": self._timestamp_to_iso(discovered_strategy.end_time),
            }

            # Parse strategy parameters from the protobuf Any field
            strategy["parameters"] = self._extract_strategy_parameters(discovered_strategy.strategy.parameters)

            return strategy

        except Exception as e:
            logging.error(f"Failed to parse Protocol Buffer message: {e}")
            logging.error(f"Raw message bytes (hex): {message_bytes.hex()}")
            return None

    def _generate_strategy_hash(self, strategy_proto) -> str:
        """Generate a hash for the strategy based on its parameters."""
        try:
            # Use the serialized parameters as the basis for the hash
            import hashlib
            parameters_bytes = strategy_proto.parameters.SerializeToString()
            return hashlib.sha256(parameters_bytes).hexdigest()
        except Exception as e:
            logging.warning(f"Failed to generate strategy hash: {e}")
            return ""

    def _timestamp_to_iso(self, timestamp_proto) -> Optional[str]:
        """Convert protobuf timestamp to ISO format string."""
        try:
            if timestamp_proto:
                # Convert seconds and nanos to datetime
                import datetime
                dt = datetime.datetime.fromtimestamp(
                    timestamp_proto.seconds + timestamp_proto.nanos / 1e9,
                    tz=datetime.timezone.utc
                )
                return dt.isoformat()
            return None
        except Exception as e:
            logging.warning(f"Failed to convert timestamp: {e}")
            return None

    def _extract_strategy_parameters(self, parameters_any) -> dict:
        """Extract strategy parameters from protobuf Any field."""
        try:
            # For now, we'll store the raw protobuf data
            # In a real implementation, you'd unpack this based on type_url
            return {
                "protobuf_type": parameters_any.type_url,
                "protobuf_data": parameters_any.value.hex(),  # Store as hex string
                "raw_parameters": {
                    "type_url": parameters_any.type_url,
                    "value": parameters_any.value.hex(),
                },
            }
        except Exception as e:
            logging.warning(f"Failed to extract strategy parameters: {e}")
            return {}

    async def _process_messages(self, messages: List[dict]) -> None:
        """Process a batch of strategy messages."""
        if not self.processor_callback:
            logging.warning("No processor callback set, skipping message processing")
            return

        try:
            await self.processor_callback(messages)
        except Exception as e:
            logging.error(f"Error processing messages: {e}")

    async def consume_messages(
        self,
        batch_size: int = 100,
        timeout_ms: int = 1000,
        idle_timeout_seconds: int = 60,
        max_processing_time_seconds: int = 300,
    ) -> None:
        """
        Consume messages from Kafka in batches.

        Args:
            batch_size: Maximum number of messages to process in a batch
            timeout_ms: Timeout for polling messages
            idle_timeout_seconds: Time to wait for messages before exiting
            max_processing_time_seconds: Maximum time to run before exiting
        """
        if not self.consumer:
            raise RuntimeError("Kafka consumer not connected")

        self.is_running = True
        start_time = time.time()
        last_message_time = start_time
        
        logging.info(f"Starting to consume messages from topic: {self.topic}")
        logging.info(
            f"Will exit after {idle_timeout_seconds}s of no messages or {max_processing_time_seconds}s total"
        )

        try:
            while self.is_running:
                # Check if we've exceeded max processing time
                current_time = time.time()
                if current_time - start_time > max_processing_time_seconds:
                    logging.info(
                        f"Reached max processing time of {max_processing_time_seconds}s, exiting"
                    )
                    break

                # Check if we've been idle too long
                if current_time - last_message_time > idle_timeout_seconds:
                    logging.info(f"No messages for {idle_timeout_seconds}s, exiting")
                    break

                # Poll for messages
                logging.debug(f"Polling for messages with timeout {timeout_ms}ms")
                message_batch = self.consumer.poll(timeout_ms=timeout_ms)

                if not message_batch:
                    # No messages available, continue polling
                    logging.debug("No messages in poll response, continuing")
                    continue

                # Update last message time
                last_message_time = time.time()
                logging.info(f"Received message batch with {len(message_batch)} partitions")
                strategies = []

                # Process messages from all partitions
                for tp, messages in message_batch.items():
                    logging.info(f"Processing {len(messages)} messages from partition {tp.partition}")
                    for message in messages:
                        try:
                            logging.info(f"Received message from partition {tp.partition}, offset {message.offset}")
                            logging.info(f"Message value type: {type(message.value)}")
                            logging.info(
                                f"Message value length: {len(message.value) if message.value else 0}"
                            )

                            if not message.value:
                                logging.warning(
                                    "Received message with empty/null value"
                                )
                                continue

                            # message.value is now bytes (binary data)
                            strategy = self._parse_strategy_message(message.value)
                            if strategy:
                                strategies.append(strategy)
                                logging.info(
                                    f"Successfully parsed strategy: {strategy.get('symbol', 'unknown')}"
                                )

                                if len(strategies) >= batch_size:
                                    # Process batch and continue
                                    logging.info(
                                        f"Processing batch of {len(strategies)} strategies"
                                    )
                                    await self._process_messages(strategies)
                                    strategies = []

                        except Exception as e:
                            logging.error(f"Error processing message: {e}")
                            continue

                # Process remaining strategies in the batch
                if strategies:
                    logging.info(
                        f"Processing final batch of {len(strategies)} strategies"
                    )
                    await self._process_messages(strategies)

        except Exception as e:
            logging.error(f"Error in message consumption loop: {e}")
            raise
        finally:
            self.is_running = False
            logging.info("Message consumption stopped")

    def stop(self) -> None:
        """Stop the message consumption loop."""
        self.is_running = False
        logging.info("Stopping message consumption")

    async def get_topic_info(self) -> dict:
        """Get information about the Kafka topic."""
        if not self.consumer:
            raise RuntimeError("Kafka consumer not connected")

        try:
            # Get topic partitions
            partitions = self.consumer.partitions_for_topic(self.topic)

            # Get beginning and end offsets for each partition
            topic_info = {
                "topic": self.topic,
                "partitions": len(partitions) if partitions else 0,
                "group_id": self.group_id,
                "consumer_id": self.consumer.config.get("client_id", "unknown"),
            }

            return topic_info

        except Exception as e:
            logging.error(f"Failed to get topic info: {e}")
            return {"topic": self.topic, "error": str(e)}
