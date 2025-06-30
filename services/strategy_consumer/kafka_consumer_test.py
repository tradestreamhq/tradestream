"""
Tests for the Kafka consumer.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

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
        message = json.dumps(
            {
                "symbol": "BTC/USD",
                "strategy_type": "MACD_CROSSOVER",
                "current_score": 0.85,
                "strategy_hash": "hash123",
                "discovery_symbol": "BTC/USD",
                "discovery_start_time": "2024-01-01T00:00:00Z",
                "discovery_end_time": "2024-01-01T01:00:00Z",
                "strategy": {"parameters": {"fast_period": 12, "slow_period": 26}},
            }
        )

        result = kafka_consumer._parse_strategy_message(message)

        assert result is not None
        assert result["symbol"] == "BTC/USD"
        assert result["strategy_type"] == "MACD_CROSSOVER"
        assert result["current_score"] == 0.85
        assert result["strategy_hash"] == "hash123"
        assert result["parameters"] == {"fast_period": 12, "slow_period": 26}

    def test_parse_strategy_message_invalid_json(self, kafka_consumer):
        """Test parsing an invalid JSON message."""
        message = "invalid json"

        result = kafka_consumer._parse_strategy_message(message)

        assert result is None

    def test_parse_strategy_message_missing_fields(self, kafka_consumer):
        """Test parsing a message with missing fields."""
        message = json.dumps(
            {
                "symbol": "BTC/USD",
                # Missing other required fields
            }
        )

        result = kafka_consumer._parse_strategy_message(message)

        assert result is not None
        assert result["symbol"] == "BTC/USD"
        assert result["strategy_type"] == ""
        assert result["current_score"] == 0.0
        assert result["strategy_hash"] == ""

    def test_parse_strategy_message_protobuf_parameters(self, kafka_consumer):
        """Test parsing a message with protobuf parameters."""
        message = json.dumps(
            {
                "symbol": "BTC/USD",
                "strategy_type": "MACD_CROSSOVER",
                "current_score": 0.85,
                "strategy_hash": "hash123",
                "strategy": {
                    "parameters": {
                        "type_url": "type.googleapis.com/com.verlumen.tradestream.strategies.MacdCrossoverParameters",
                        "value": "base64_encoded_data",
                    }
                },
            }
        )

        result = kafka_consumer._parse_strategy_message(message)

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
