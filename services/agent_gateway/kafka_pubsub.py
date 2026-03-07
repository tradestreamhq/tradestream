"""Kafka Pub/Sub manager for inter-agent communication.

Topics:
- agent-signals-raw - Raw signals from Signal Generator agent
- agent-signals-scored - Signals with opportunity scores
- agent-signals-validated - Signals validated by Portfolio Advisor
- agent-dashboard-signals - Final signals for dashboard display
- agent-commands - User commands from the gateway
- agent-status - Agent health and status updates
"""

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import logging

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


logger = logging.getLogger(__name__)


# Kafka topic names for the agent pipeline
class Topics:
    """Kafka topic names for agent communication."""

    RAW_SIGNALS = "agent-signals-raw"
    SCORED_SIGNALS = "agent-signals-scored"
    VALIDATED_SIGNALS = "agent-signals-validated"
    DASHBOARD_SIGNALS = "agent-dashboard-signals"
    AGENT_COMMANDS = "agent-commands"
    AGENT_STATUS = "agent-status"


# Retry parameters for Kafka operations
kafka_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((KafkaError, NoBrokersAvailable, ConnectionError)),
    reraise=True,
)


@dataclass
class AgentMessage:
    """Standard message format for agent communication."""

    message_id: str
    message_type: str  # signal, reasoning, tool_call, tool_result, error, status
    source_agent: str
    timestamp: str
    payload: Dict[str, Any]
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, data: str) -> "AgentMessage":
        d = json.loads(data)
        return cls(**d)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentMessage":
        return cls(**d)


class KafkaPubSub:
    """Kafka Pub/Sub manager for agent communication."""

    def __init__(
        self,
        bootstrap_servers: str = None,
        group_id: str = "agent-gateway-group",
    ):
        self.bootstrap_servers = bootstrap_servers or os.environ.get(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.group_id = group_id

        # Producer for publishing messages
        self._producer: Optional[KafkaProducer] = None

        # Consumer for subscriptions
        self._consumer: Optional[KafkaConsumer] = None
        self._subscriber_thread: Optional[threading.Thread] = None
        self._handlers: Dict[str, List[Callable[[AgentMessage], None]]] = {}
        self._running = False
        self._subscribed_topics: List[str] = []

        logger.info(f"KafkaPubSub initialized: {self.bootstrap_servers}")

    @retry(**kafka_retry_params)
    def _connect_producer(self) -> None:
        """Establish producer connection to Kafka."""
        logger.info(f"Connecting Kafka producer to {self.bootstrap_servers}")
        self._producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
            api_version_auto_timeout_ms=10000,
        )
        logger.info("Kafka producer connected successfully")

    @retry(**kafka_retry_params)
    def _connect_consumer(self, topics: List[str]) -> None:
        """Establish consumer connection to Kafka."""
        logger.info(f"Connecting Kafka consumer to topics: {topics}")
        self._consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda v: v.decode("utf-8"),
            consumer_timeout_ms=1000,
        )
        self._subscribed_topics = topics
        logger.info(f"Kafka consumer connected to topics: {topics}")

    def ping(self) -> bool:
        """Check Kafka connection by attempting producer bootstrap."""
        try:
            if self._producer is None:
                self._connect_producer()
            # Check if producer is connected by getting cluster metadata
            self._producer.bootstrap_connected()
            return True
        except Exception as e:
            logger.warning(f"Kafka ping failed: {e}")
            return False

    def publish(self, topic: str, message: AgentMessage) -> bool:
        """Publish a message to a topic.

        Args:
            topic: Topic name
            message: AgentMessage to publish

        Returns:
            True if published successfully, False otherwise
        """
        try:
            if self._producer is None:
                self._connect_producer()

            future = self._producer.send(topic, value=message.to_json())
            record_metadata = future.get(timeout=10)
            logger.debug(
                f"Published to {topic}, partition {record_metadata.partition}, "
                f"offset {record_metadata.offset}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            return False

    def publish_signal(
        self,
        topic: str,
        signal_data: Dict[str, Any],
        source_agent: str,
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Convenience method to publish a signal message."""
        import uuid

        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            message_type="signal",
            source_agent=source_agent,
            timestamp=datetime.utcnow().isoformat() + "Z",
            payload=signal_data,
            correlation_id=correlation_id,
        )
        return self.publish(topic, message)

    def subscribe(
        self,
        topic: str,
        handler: Callable[[AgentMessage], None],
    ) -> None:
        """Subscribe to a topic with a handler function.

        Args:
            topic: Topic name to subscribe to
            handler: Callback function that receives AgentMessage
        """
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        logger.info(f"Registered handler for topic: {topic}")

    def start_listening(self) -> None:
        """Start the subscriber thread."""
        if self._running:
            return

        topics = list(self._handlers.keys())
        if not topics:
            logger.warning("No subscriptions registered, nothing to listen to")
            return

        # Connect consumer to all registered topics
        self._connect_consumer(topics)

        self._running = True
        self._subscriber_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="kafka-pubsub-listener",
        )
        self._subscriber_thread.start()
        logger.info(f"Started Kafka Pub/Sub listener for topics: {topics}")

    def _listen_loop(self) -> None:
        """Main listening loop."""
        while self._running:
            try:
                # Poll for messages
                message_batch = self._consumer.poll(timeout_ms=1000)

                if not message_batch:
                    continue

                for topic_partition, messages in message_batch.items():
                    topic = topic_partition.topic
                    handlers = self._handlers.get(topic, [])

                    for message in messages:
                        try:
                            agent_message = AgentMessage.from_json(message.value)
                            for handler in handlers:
                                try:
                                    handler(agent_message)
                                except Exception as e:
                                    logger.error(f"Handler error on {topic}: {e}")
                        except (json.JSONDecodeError, TypeError, KeyError) as e:
                            logger.warning(f"Invalid message on {topic}: {e}")

            except NoBrokersAvailable:
                logger.error("Kafka connection lost, attempting reconnect...")
                time.sleep(5)
                try:
                    self._connect_consumer(self._subscribed_topics)
                except Exception as e:
                    logger.error(f"Reconnection failed: {e}")
            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
                time.sleep(1)

    def stop_listening(self) -> None:
        """Stop the subscriber thread."""
        self._running = False
        if self._subscriber_thread:
            self._subscriber_thread.join(timeout=5)
        if self._consumer:
            self._consumer.close()
        logger.info("Stopped Kafka Pub/Sub listener")

    def close(self) -> None:
        """Close all connections."""
        self.stop_listening()
        if self._producer:
            self._producer.flush(timeout=10)
            self._producer.close(timeout=10)
            logger.info("Kafka producer closed")


class SignalPipeline:
    """Manages the signal processing pipeline across agents."""

    def __init__(self, pubsub: KafkaPubSub):
        self.pubsub = pubsub

    def forward_to_scorer(self, signal: AgentMessage) -> bool:
        """Forward raw signal to opportunity scorer."""
        return self.pubsub.publish(Topics.SCORED_SIGNALS, signal)

    def forward_to_validator(self, signal: AgentMessage) -> bool:
        """Forward scored signal to portfolio validator."""
        return self.pubsub.publish(Topics.VALIDATED_SIGNALS, signal)

    def forward_to_dashboard(self, signal: AgentMessage) -> bool:
        """Forward validated signal to dashboard stream."""
        return self.pubsub.publish(Topics.DASHBOARD_SIGNALS, signal)
