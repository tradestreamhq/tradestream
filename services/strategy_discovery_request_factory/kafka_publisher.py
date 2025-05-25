from absl import logging
import kafka  # Using kafka-python
from protos.discovery_pb2 import StrategyDiscoveryRequest
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

kafka_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (kafka.errors.KafkaConnectionError, kafka.errors.KafkaTimeoutError)
    ),
    reraise=True,
)


class KafkaPublisher:
    def __init__(self, bootstrap_servers: str, topic_name: str):
        self.bootstrap_servers = bootstrap_servers
        self.topic_name = topic_name
        self.producer = None
        self._connect_with_retry()

    @retry(**kafka_retry_params)
    def _connect_with_retry(self):
        try:
            logging.info(f"Attempting to connect to Kafka at {self.bootstrap_servers}")
            self.producer = kafka.KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                api_version_auto_timeout_ms=10000,  # Added timeout for API version fetch
            )
            logging.info(
                f"Successfully connected KafkaProducer to {self.bootstrap_servers}"
            )
        except kafka.errors.NoBrokersAvailable as e:
            logging.error(
                f"No Kafka brokers available at {self.bootstrap_servers}: {e}"
            )
            self.producer = None  # Ensure producer is None if connection fails
            raise  # Reraise to allow tenacity to handle it
        except Exception as e:
            logging.error(f"Failed to initialize KafkaProducer: {e}")
            self.producer = None
            raise

    @retry(**kafka_retry_params)
    def _publish_message_retryable(self, request_bytes: bytes, key_bytes: bytes = None):
        if not self.producer:
            logging.error("Kafka producer not initialized. Cannot publish message.")
            # Attempt to reconnect if producer is None
            self._connect_with_retry()
            if not self.producer:  # If still None after retry, then fail
                raise kafka.errors.KafkaConnectionError(
                    "Kafka producer could not be initialized after retry."
                )

        future = self.producer.send(self.topic_name, value=request_bytes, key=key_bytes)
        try:
            record_metadata = future.get(timeout=10)  # Block for 'timeout' seconds.
            logging.info(
                f"Successfully published StrategyDiscoveryRequest to Kafka topic '{self.topic_name}', partition {record_metadata.partition}, offset {record_metadata.offset}"
            )
        except kafka.errors.KafkaError as e:
            logging.error(f"Error publishing StrategyDiscoveryRequest to Kafka: {e}")
            raise  # Reraise to allow tenacity to handle it

    def publish_request(self, request: StrategyDiscoveryRequest, key: str = None):
        if not self.producer:
            logging.warning(
                "Kafka producer not available. Attempting to send message might fail or retry."
            )
            # The retry decorator on _publish_message_retryable will handle reconnection if necessary

        try:
            request_bytes = request.SerializeToString()
            key_bytes = key.encode("utf-8") if key else None
            self._publish_message_retryable(request_bytes, key_bytes)
        except Exception as e:
            # This will catch the reraised exception from _publish_message_retryable if all retries fail
            logging.error(
                f"Failed to publish StrategyDiscoveryRequest to Kafka after all retries: {e}"
            )

    def close(self):
        if self.producer:
            try:
                logging.info("Flushing Kafka producer...")
                self.producer.flush(timeout=10)  # Wait for all messages to be sent
            except kafka.errors.KafkaError as e:
                logging.error(f"Error flushing Kafka producer: {e}")
            finally:
                logging.info("Closing Kafka producer...")
                self.producer.close(timeout=10)
                logging.info("Kafka producer closed.")
                self.producer = None
