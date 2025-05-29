"""Unit tests for kafka_publisher module."""

import unittest
from unittest.mock import Mock, patch
import kafka.errors

from protos.discovery_pb2 import StrategyDiscoveryRequest, GAConfig
from protos.strategies_pb2 import StrategyType
from google.protobuf.timestamp_pb2 import Timestamp

from services.strategy_discovery_request_factory.kafka_publisher import KafkaPublisher


class KafkaPublisherTest(unittest.TestCase):
    """Test Kafka publishing functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_bootstrap_servers = "test-kafka:9092"
        self.test_topic = "test-topic"

        # Mock KafkaProducer to avoid actual connections
        self.mock_producer_class = patch(
            "services.strategy_discovery_request_factory.kafka_publisher.kafka.KafkaProducer"
        ).start()
        self.mock_producer = Mock()
        self.mock_producer_class.return_value = self.mock_producer

        # Mock successful send
        self.mock_future = Mock()
        self.mock_record_metadata = Mock()
        self.mock_record_metadata.partition = 0
        self.mock_record_metadata.offset = 123
        self.mock_future.get.return_value = self.mock_record_metadata
        self.mock_producer.send.return_value = self.mock_future

        self.publisher = KafkaPublisher(
            bootstrap_servers=self.test_bootstrap_servers, topic_name=self.test_topic
        )

    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()

    def _create_test_strategy_discovery_request(
        self,
        symbol: str = "BTC/USD",
        strategy_type: StrategyType = StrategyType.SMA_RSI,
        top_n: int = 5,
    ) -> StrategyDiscoveryRequest:
        """Create a test strategy discovery request."""
        start_time = Timestamp()
        start_time.FromMilliseconds(1640995200000)  # 2022-01-01 00:00:00 UTC

        end_time = Timestamp()
        end_time.FromMilliseconds(1640995260000)  # 2022-01-01 00:01:00 UTC

        ga_config = GAConfig(max_generations=30, population_size=50)

        return StrategyDiscoveryRequest(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            strategy_type=strategy_type,
            top_n=top_n,
            ga_config=ga_config,
        )

    def test_initialization_success(self):
        """Test successful KafkaPublisher initialization."""
        self.assertEqual(self.publisher.bootstrap_servers, self.test_bootstrap_servers)
        self.assertEqual(self.publisher.topic_name, self.test_topic)
        self.assertIsNotNone(self.publisher.producer)

        # Verify producer was created with correct parameters
        self.mock_producer_class.assert_called_once_with(
            bootstrap_servers=self.test_bootstrap_servers,
            api_version_auto_timeout_ms=10000,
        )

    def test_initialization_no_brokers_available(self):
        """Test initialization failure due to no brokers available."""
        self.mock_producer_class.side_effect = kafka.errors.NoBrokersAvailable(
            "No brokers"
        )

        with self.assertRaises(kafka.errors.NoBrokersAvailable):
            KafkaPublisher(
                bootstrap_servers=self.test_bootstrap_servers,
                topic_name=self.test_topic,
            )

    def test_initialization_general_error(self):
        """Test initialization failure due to general error."""
        self.mock_producer_class.side_effect = Exception("Connection failed")

        with self.assertRaises(Exception):
            KafkaPublisher(
                bootstrap_servers=self.test_bootstrap_servers,
                topic_name=self.test_topic,
            )

    def test_publish_request_success(self):
        """Test successful request publishing."""
        test_request = self._create_test_strategy_discovery_request()
        test_key = "BTC/USD"

        self.publisher.publish_request(test_request, test_key)

        # Verify send was called with correct parameters
        self.mock_producer.send.assert_called_once()
        call_args = self.mock_producer.send.call_args

        self.assertEqual(call_args[0][0], self.test_topic)  # Topic
        self.assertEqual(
            call_args[1]["value"], test_request.SerializeToString()
        )  # Serialized request
        self.assertEqual(call_args[1]["key"], test_key.encode("utf-8"))  # Key as bytes

        # Verify future.get was called
        self.mock_future.get.assert_called_once_with(timeout=10)

    def test_publish_request_no_key(self):
        """Test publishing request without key."""
        test_request = self._create_test_strategy_discovery_request()

        self.publisher.publish_request(test_request)

        # Verify send was called with None key
        call_args = self.mock_producer.send.call_args
        self.assertIsNone(call_args[1]["key"])

    def test_publish_request_kafka_error(self):
        """Test handling of Kafka error during publishing."""
        test_request = self._create_test_strategy_discovery_request()
        self.mock_future.get.side_effect = kafka.errors.KafkaTimeoutError("Timeout")

        # Should not raise exception, but handle gracefully
        self.publisher.publish_request(test_request, "BTC/USD")

        # Verify send was attempted multiple times due to retry
        self.assertEqual(self.mock_producer.send.call_count, 5)

    def test_publish_request_no_producer(self):
        """Test publishing when producer is None."""
        self.publisher.producer = None
        test_request = self._create_test_strategy_discovery_request()

        # Should attempt to reconnect
        with patch.object(self.publisher, "_connect_with_retry") as mock_connect:
            mock_connect.return_value = None  # Simulate failed reconnection

            self.publisher.publish_request(test_request, "BTC/USD")

            self.assertEqual(mock_connect.call_count, 5)

    def test_publish_message_retryable_reconnect(self):
        """Test reconnection during message publishing."""
        self.publisher.producer = None
        test_request = self._create_test_strategy_discovery_request()

        # Mock successful reconnection
        with patch.object(self.publisher, "_connect_with_retry") as mock_connect:
            # First call sets up the producer
            def setup_producer():
                self.publisher.producer = self.mock_producer

            mock_connect.side_effect = setup_producer

            self.publisher.publish_request(test_request, "BTC/USD")

            # Verify reconnection was attempted and send was called
            mock_connect.assert_called()
            self.mock_producer.send.assert_called_once()

    def test_publish_message_retryable_connection_error(self):
        """Test handling of connection error during publishing."""
        test_bytes = b"test message"

        # Mock connection error that should trigger retry
        self.mock_producer.send.side_effect = kafka.errors.KafkaConnectionError(
            "Connection lost"
        )

        with patch.object(self.publisher, "_connect_with_retry") as mock_connect:
            # This should raise the connection error after retries
            with self.assertRaises(kafka.errors.KafkaConnectionError):
                self.publisher._publish_message_retryable(test_bytes)

    def test_close_success(self):
        """Test successful producer closure."""
        self.publisher.close()

        self.mock_producer.flush.assert_called_once_with(timeout=10)
        self.mock_producer.close.assert_called_once_with(timeout=10)
        self.assertIsNone(self.publisher.producer)

    def test_close_flush_error(self):
        """Test producer closure with flush error."""
        self.mock_producer.flush.side_effect = kafka.errors.KafkaError("Flush failed")

        # Should still close the producer despite flush error
        self.publisher.close()

        self.mock_producer.flush.assert_called_once_with(timeout=10)
        self.mock_producer.close.assert_called_once_with(timeout=10)
        self.assertIsNone(self.publisher.producer)

    def test_close_no_producer(self):
        """Test closing when producer is None."""
        self.publisher.producer = None

        # Should not raise exception
        self.publisher.close()

    def test_retry_mechanism(self):
        """Test that retry mechanism is properly configured."""
        # Test that connection failures trigger retries
        connection_attempts = []

        def mock_producer_creation(*args, **kwargs):
            connection_attempts.append(1)
            if len(connection_attempts) < 3:
                raise kafka.errors.KafkaConnectionError("Temporary failure")
            return self.mock_producer

        self.mock_producer_class.side_effect = mock_producer_creation

        # Should eventually succeed after retries
        publisher = KafkaPublisher(
            bootstrap_servers=self.test_bootstrap_servers, topic_name=self.test_topic
        )

        # Verify multiple attempts were made
        self.assertEqual(len(connection_attempts), 3)
        self.assertIsNotNone(publisher.producer)

    def test_serialization_handling(self):
        """Test proper serialization of discovery requests."""
        test_request = self._create_test_strategy_discovery_request()
        expected_bytes = test_request.SerializeToString()

        self.publisher.publish_request(test_request, "BTC/USD")

        call_args = self.mock_producer.send.call_args
        actual_bytes = call_args[1]["value"]

        self.assertEqual(actual_bytes, expected_bytes)
        self.assertIsInstance(actual_bytes, bytes)

    def test_key_encoding(self):
        """Test proper encoding of string keys to bytes."""
        test_request = self._create_test_strategy_discovery_request()
        test_key = "BTC/USD"

        self.publisher.publish_request(test_request, test_key)

        call_args = self.mock_producer.send.call_args
        actual_key = call_args[1]["key"]

        self.assertEqual(actual_key, test_key.encode("utf-8"))
        self.assertIsInstance(actual_key, bytes)

    @patch("services.strategy_discovery_request_factory.kafka_publisher.logging")
    def test_logging_behavior(self, mock_logging):
        """Test that appropriate logging occurs."""
        test_request = self._create_test_strategy_discovery_request()

        # Test successful publish logging
        self.publisher.publish_request(test_request, "BTC/USD")
        mock_logging.info.assert_called()

        # Test error logging
        self.mock_future.get.side_effect = kafka.errors.KafkaError("Test error")
        self.publisher.publish_request(test_request, "BTC/USD")
        mock_logging.error.assert_called()

    def test_timeout_configuration(self):
        """Test that timeouts are properly configured."""
        test_request = self._create_test_strategy_discovery_request()

        self.publisher.publish_request(test_request, "BTC/USD")

        # Verify get timeout
        self.mock_future.get.assert_called_with(timeout=10)

        # Test close timeouts
        self.publisher.close()
        self.mock_producer.flush.assert_called_with(timeout=10)
        self.mock_producer.close.assert_called_with(timeout=10)

    def test_different_strategy_types(self):
        """Test publishing requests with different strategy types."""
        # Get available strategy types dynamically instead of hardcoding
        available_strategy_types = [
            st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED
        ]

        # Take first 3 available types for testing, or all if less than 3
        strategy_types_to_test = available_strategy_types[:3]

        # Skip test if no strategy types available
        if not strategy_types_to_test:
            self.skipTest("No strategy types available for testing")

        for strategy_type in strategy_types_to_test:
            with self.subTest(strategy_type=strategy_type):
                request = self._create_test_strategy_discovery_request(
                    strategy_type=strategy_type
                )
                self.publisher.publish_request(request, "BTC/USD")

        # Should have published all requests
        self.assertEqual(
            self.mock_producer.send.call_count, len(strategy_types_to_test)
        )

    def test_different_symbols(self):
        """Test publishing requests for different currency pairs."""
        symbols = ["BTC/USD", "ETH/USD", "ADA/USD"]

        for symbol in symbols:
            with self.subTest(symbol=symbol):
                request = self._create_test_strategy_discovery_request(symbol=symbol)
                self.publisher.publish_request(request, symbol)

        # Should have published all requests
        self.assertEqual(self.mock_producer.send.call_count, len(symbols))


if __name__ == "__main__":
    unittest.main()
