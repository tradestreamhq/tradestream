"""
Tests for the Kafka consumer.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

# Import Protocol Buffer classes for testing
from protos.discovery_pb2 import DiscoveredStrategy
from protos.strategies_pb2 import Strategy, StrategyType
from google.protobuf import any_pb2
from google.protobuf import timestamp_pb2
import datetime

from services.strategy_consumer.kafka_consumer import StrategyKafkaConsumer


class TestStrategyKafkaConsumer:
    """Test cases for StrategyKafkaConsumer."""

    @pytest.fixture
    def kafka_consumer(self):
        """Create a StrategyKafkaConsumer instance for testing."""
        return StrategyKafkaConsumer(
            bootstrap_servers="localhost:9092",
            topic="test-topic",
            group_id="test-group",
        )

    def test_init(self, kafka_consumer):
        """Test consumer initialization."""
        assert kafka_consumer.bootstrap_servers == "localhost:9092"
        assert kafka_consumer.topic == "test-topic"
        assert kafka_consumer.group_id == "test-group"
        assert kafka_consumer.consumer is None
        assert kafka_consumer.is_running is False

    @patch("kafka.KafkaConsumer")
    def test_connect_success(self, mock_kafka_consumer, kafka_consumer):
        """Test successful connection to Kafka."""
        mock_consumer = MagicMock()
        mock_kafka_consumer.return_value = mock_consumer

        kafka_consumer.connect()

        assert kafka_consumer.consumer is not None
        mock_kafka_consumer.assert_called_once()

    @patch("kafka.KafkaConsumer")
    def test_connect_failure(self, mock_kafka_consumer, kafka_consumer):
        """Test connection failure to Kafka."""
        mock_kafka_consumer.side_effect = Exception("Connection failed")

        with pytest.raises(Exception):
            kafka_consumer.connect()

        assert kafka_consumer.consumer is None

    def test_close(self, kafka_consumer):
        """Test closing the Kafka consumer."""
        mock_consumer = MagicMock()
        kafka_consumer.consumer = mock_consumer

        kafka_consumer.close()

        mock_consumer.close.assert_called_once()

    def test_set_processor_callback(self, kafka_consumer):
        """Test setting the processor callback."""

        def test_callback(messages):
            pass

        kafka_consumer.set_processor_callback(test_callback)

        assert kafka_consumer.processor_callback == test_callback

    def test_parse_strategy_message_valid(self, kafka_consumer):
        """Test parsing a valid strategy message."""
        # Create a test DiscoveredStrategy protobuf message
        strategy = Strategy()
        strategy.type = StrategyType.MACD_CROSSOVER
        
        # Create parameters as Any field
        parameters = any_pb2.Any()
        parameters.type_url = "type.googleapis.com/com.verlumen.tradestream.strategies.MacdCrossoverParameters"
        parameters.value = b"test_parameters_data"
        strategy.parameters.CopyFrom(parameters)
        
        discovered_strategy = DiscoveredStrategy()
        discovered_strategy.strategy.CopyFrom(strategy)
        discovered_strategy.symbol = "BTC/USD"
        discovered_strategy.score = 0.85
        
        # Set timestamps
        start_time = timestamp_pb2.Timestamp()
        start_time.FromDatetime(datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc))
        discovered_strategy.start_time.CopyFrom(start_time)
        
        end_time = timestamp_pb2.Timestamp()
        end_time.FromDatetime(datetime.datetime(2024, 1, 1, 1, 0, 0, tzinfo=datetime.timezone.utc))
        discovered_strategy.end_time.CopyFrom(end_time)
        
        # Serialize to bytes
        message_bytes = discovered_strategy.SerializeToString()

        result = kafka_consumer._parse_strategy_message(message_bytes)

        assert result is not None
        assert result["symbol"] == "BTC/USD"
        assert result["strategy_type"] == "MACD_CROSSOVER"
        assert result["current_score"] == 0.85
        assert result["strategy_hash"] != ""
        assert result["discovery_symbol"] == "BTC/USD"
        assert result["discovery_start_time"] == "2024-01-01T00:00:00+00:00"
        assert result["discovery_end_time"] == "2024-01-01T01:00:00+00:00"
        assert "protobuf_type" in result["parameters"]
        assert "protobuf_data" in result["parameters"]

    def test_parse_strategy_message_invalid_bytes(self, kafka_consumer):
        """Test parsing an invalid binary message."""
        message_bytes = b"invalid protobuf data"

        result = kafka_consumer._parse_strategy_message(message_bytes)

        assert result is None

    def test_parse_strategy_message_missing_fields(self, kafka_consumer):
        """Test parsing a message with missing fields."""
        # Create a minimal DiscoveredStrategy with only required fields
        discovered_strategy = DiscoveredStrategy()
        discovered_strategy.symbol = "BTC/USD"
        discovered_strategy.score = 0.0
        
        # Serialize to bytes
        message_bytes = discovered_strategy.SerializeToString()

        result = kafka_consumer._parse_strategy_message(message_bytes)

        assert result is not None
        assert result["symbol"] == "BTC/USD"
        assert result["strategy_type"] == "UNSPECIFIED"  # Default enum value
        assert result["current_score"] == 0.0
        assert result["strategy_hash"] != ""
        assert result["discovery_symbol"] == "BTC/USD"

    def test_parse_strategy_message_protobuf_parameters(self, kafka_consumer):
        """Test parsing a message with protobuf parameters."""
        # Create a test DiscoveredStrategy with specific parameters
        strategy = Strategy()
        strategy.type = StrategyType.MACD_CROSSOVER
        # Create parameters as Any field
        parameters = any_pb2.Any()
        parameters.type_url = "type.googleapis.com/com.verlumen.tradestream.strategies.MacdCrossoverParameters"
        parameters.value = b"test_parameters_data"
        strategy.parameters.CopyFrom(parameters)
        discovered_strategy = DiscoveredStrategy()
        discovered_strategy.strategy.CopyFrom(strategy)
        discovered_strategy.symbol = "BTC/USD"
        discovered_strategy.score = 0.85
        # Serialize to bytes
        message_bytes = discovered_strategy.SerializeToString()

        result = kafka_consumer._parse_strategy_message(message_bytes)

        assert result is not None
        assert "protobuf_type" in result["parameters"]
        assert "protobuf_data" in result["parameters"]
        assert (
            result["parameters"]["protobuf_type"]
            == "type.googleapis.com/com.verlumen.tradestream.strategies.MacdCrossoverParameters"
        )

    def test_stop(self, kafka_consumer):
        """Test stopping the consumer."""
        kafka_consumer.is_running = True

        kafka_consumer.stop()

        assert kafka_consumer.is_running is False

    @patch("kafka.KafkaConsumer")
    def test_get_topic_info(self, mock_kafka_consumer, kafka_consumer):
        """Test getting topic information."""
        mock_consumer = MagicMock()
        mock_consumer.partitions_for_topic.return_value = {0, 1, 2}
        mock_consumer.config = {"client_id": "test-client"}
        kafka_consumer.consumer = mock_consumer

        result = kafka_consumer.get_topic_info()

        assert result["topic"] == "test-topic"
        assert result["partitions"] == 3
        assert result["group_id"] == "test-group"
        assert result["consumer_id"] == "test-client"

    @patch("kafka.KafkaConsumer")
    def test_get_topic_info_error(self, mock_kafka_consumer, kafka_consumer):
        """Test getting topic information with error."""
        mock_consumer = MagicMock()
        mock_consumer.partitions_for_topic.side_effect = Exception("Test error")
        kafka_consumer.consumer = mock_consumer

        result = kafka_consumer.get_topic_info()

        assert result["topic"] == "test-topic"
        assert "error" in result
        assert result["error"] == "Test error"
