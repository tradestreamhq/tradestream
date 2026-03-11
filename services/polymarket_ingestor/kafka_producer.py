"""Kafka producer for publishing Polymarket data to Kafka topics."""

from absl import logging
import kafka
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


class PolymarketKafkaProducer:
    """Kafka producer for Polymarket data topics."""

    def __init__(
        self,
        bootstrap_servers: str,
        security_protocol: str = "SSL",
        ssl_cafile: str = None,
        ssl_certfile: str = None,
        ssl_keyfile: str = None,
        ssl_password: str = None,
    ):
        self.bootstrap_servers = bootstrap_servers
        self.security_protocol = security_protocol
        self.ssl_cafile = ssl_cafile
        self.ssl_certfile = ssl_certfile
        self.ssl_keyfile = ssl_keyfile
        self.ssl_password = ssl_password

        if self.security_protocol in ("SSL", "SASL_SSL") and not self.ssl_cafile:
            raise ValueError(
                f"ssl_cafile is required when using {self.security_protocol} "
                "security protocol. Set KAFKA_SSL_CA_LOCATION environment variable."
            )

        self.producer = None
        self._connect_with_retry()

    def _build_ssl_kwargs(self):
        """Build SSL keyword arguments for kafka-python client."""
        kwargs = {}
        if self.security_protocol in ("SSL", "SASL_SSL"):
            kwargs["security_protocol"] = self.security_protocol
            if self.ssl_cafile:
                kwargs["ssl_cafile"] = self.ssl_cafile
            if self.ssl_certfile:
                kwargs["ssl_certfile"] = self.ssl_certfile
            if self.ssl_keyfile:
                kwargs["ssl_keyfile"] = self.ssl_keyfile
            if self.ssl_password:
                kwargs["ssl_password"] = self.ssl_password
        return kwargs

    @retry(**kafka_retry_params)
    def _connect_with_retry(self):
        try:
            logging.info(f"Attempting to connect to Kafka at {self.bootstrap_servers}")
            self.producer = kafka.KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                api_version_auto_timeout_ms=10000,
                **self._build_ssl_kwargs(),
            )
            logging.info(
                f"Successfully connected KafkaProducer to {self.bootstrap_servers}"
            )
        except kafka.errors.NoBrokersAvailable as e:
            logging.error(
                f"No Kafka brokers available at {self.bootstrap_servers}: {e}"
            )
            self.producer = None
            raise
        except Exception as e:
            logging.error(f"Failed to initialize KafkaProducer: {e}")
            self.producer = None
            raise

    @retry(**kafka_retry_params)
    def _publish_message_retryable(
        self, topic: str, message_bytes: bytes, key_bytes: bytes = None
    ):
        if not self.producer:
            logging.error("Kafka producer not initialized. Cannot publish message.")
            self._connect_with_retry()
            if not self.producer:
                raise kafka.errors.KafkaConnectionError(
                    "Kafka producer could not be initialized after retry."
                )

        future = self.producer.send(topic, value=message_bytes, key=key_bytes)
        try:
            record_metadata = future.get(timeout=10)
            logging.debug(
                f"Published to topic '{topic}', partition {record_metadata.partition}, "
                f"offset {record_metadata.offset}"
            )
        except kafka.errors.KafkaError as e:
            logging.error(f"Error publishing to Kafka topic '{topic}': {e}")
            raise

    def publish(self, topic: str, message_bytes: bytes, key: str = None):
        """Publish a serialized protobuf message to a Kafka topic.

        Args:
            topic: Kafka topic name.
            message_bytes: Serialized protobuf bytes.
            key: Optional message key.
        """
        try:
            key_bytes = key.encode("utf-8") if key else None
            self._publish_message_retryable(topic, message_bytes, key_bytes)
        except Exception as e:
            logging.error(
                f"Failed to publish to Kafka topic '{topic}' after all retries: {e}"
            )

    def close(self):
        """Flush and close the Kafka producer."""
        if self.producer:
            try:
                logging.info("Flushing Kafka producer...")
                self.producer.flush(timeout=10)
            except kafka.errors.KafkaError as e:
                logging.error(f"Error flushing Kafka producer: {e}")
            finally:
                logging.info("Closing Kafka producer...")
                self.producer.close(timeout=10)
                logging.info("Kafka producer closed.")
                self.producer = None
