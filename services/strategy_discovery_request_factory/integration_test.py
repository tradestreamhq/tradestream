"""Integration tests for strategy_discovery_request_factory with InfluxDB tracker."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from protos.marketdata_pb2 import Candle
from protos.discovery_pb2 import StrategyDiscoveryRequest
from protos.strategies_pb2 import StrategyType
from google.protobuf.timestamp_pb2 import Timestamp

from services.strategy_discovery_request_factory.influx_poller import InfluxPoller
from services.strategy_discovery_request_factory.strategy_discovery_processor import (
    StrategyDiscoveryProcessor,
)
from services.strategy_discovery_request_factory.kafka_publisher import KafkaPublisher
from shared.persistence.influxdb_last_processed_tracker import InfluxDBLastProcessedTracker


class IntegrationTest(unittest.TestCase):
    """Integration tests for component interactions with InfluxDB tracker."""

    def setUp(self):
        """Set up test environment with mocked external services."""
        # Mock InfluxDB client
        self.mock_influx_client = patch(
            "services.strategy_discovery_request_factory.influx_poller.InfluxDBClient"
        ).start()
        
        # Mock Kafka producer
        self.mock_kafka_producer = patch(
            "services.strategy_discovery_request_factory.kafka_publisher.kafka.KafkaProducer"
        ).start()
        
        # Mock InfluxDB tracker
        self.mock_tracker_class = patch(
            "shared.persistence.influxdb_last_processed_tracker.InfluxDBLastProcessedTracker"
        ).start()

        # Set up mock instances
        self.mock_influx_instance = Mock()
        self.mock_influx_instance.ping.return_value = True
        self.mock_influx_client.return_value = self.mock_influx_instance

        self.mock_producer_instance = Mock()
        mock_future = Mock()
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_future.get.return_value = mock_metadata
        self.mock_producer_instance.send.return_value = mock_future
        self.mock_kafka_producer.return_value = self.mock_producer_instance

        self.mock_tracker_instance = Mock(spec=InfluxDBLastProcessedTracker)
        self.mock_tracker_instance.client = Mock()  # Ensure client exists
        self.mock_tracker_class.return_value = self.mock_tracker_instance

    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()

    def _create_test_candle(
        self, 
        currency_pair: str, 
        timestamp_ms: int,
        open_price: float = 50000.0
    ) -> Candle:
        """Create a test candle."""
        ts_seconds = timestamp_ms // 1000
        ts_nanos = (timestamp_ms % 1000) * 1_000_000

        return Candle(
            timestamp=Timestamp(seconds=ts_seconds, nanos=ts_nanos),
            currency_pair=currency_pair,
            open=open_price,
            high=open_price + 100,
            low=open_price - 100,
            close=open_price + 50,
            volume=1000.0,
        )

    def _create_mock_influx_table(self, candle_data: list) -> list:
        """Create mock InfluxDB table response."""
        records = []
        for data in candle_data:
            mock_record = Mock()
            mock_record.get_time.return_value = datetime.fromtimestamp(
                data["timestamp_ms"] / 1000, tz=timezone.utc
            )
            mock_record.values = {
                "currency_pair": data["currency_pair"],
                "open": data.get("open", 50000.0),
                "high": data.get("high", 50100.0),
                "low": data.get("low", 49900.0),
                "close": data.get("close", 50050.0),
                "volume": data.get("volume", 1000.0),
            }
            records.append(mock_record)

        mock_table = Mock()
        mock_table.records = records
        return [mock_table] if records else []

    def test_end_to_end_processing_with_tracker(self):
        """Test complete processing pipeline with InfluxDB tracker integration."""
        currency_pair = "BTC/USD"
        
        # Set up components
        influx_poller = InfluxPoller("http://test:8086", "token", "org", "bucket")
        
        strategy_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5, 8, 13],
            deque_maxlen=100,
            tracker=self.mock_tracker_instance,
            service_identifier="test_service",
        )
        
        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        # Mock initial tracker state (first run)
        self.mock_tracker_instance.get_last_processed_timestamp.return_value = None

        # Create test candle data
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        test_data = []
        for i in range(15):  # Enough for all windows
            test_data.append({
                "timestamp_ms": base_timestamp + (i * 60000),
                "currency_pair": currency_pair,
                "open": 50000.0 + i,
            })

        # Mock InfluxDB query response
        mock_query_api = Mock()
        self.mock_influx_instance.query_api.return_value = mock_query_api
        mock_tables = self._create_mock_influx_table(test_data)
        mock_query_api.query.return_value = mock_tables

        # Execute pipeline
        strategy_processor.initialize_pair(currency_pair)
        
        # Fetch candles
        candles, latest_ts = influx_poller.fetch_new_candles(currency_pair, 0)
        
        # Process candles and publish requests
        total_published = 0
        for candle in candles:
            discovery_requests = strategy_processor.add_candle(candle)
            for request in discovery_requests:
                kafka_publisher.publish_request(request, currency_pair)
                total_published += 1

        # Verify results
        self.assertEqual(len(candles), 15)
        self.assertGreater(total_published, 0)
        
        # Verify tracker was called for initialization
        self.mock_tracker_instance.get_last_processed_timestamp.assert_called_with(
            "test_service", currency_pair
        )
        
        # Verify tracker was updated for each candle
        self.assertGreater(self.mock_tracker_instance.update_last_processed_timestamp.call_count, 0)
        
        # Verify Kafka publishing
        self.assertGreater(self.mock_producer_instance.send.call_count, 0)

    def test_resume_from_tracker_state(self):
        """Test resuming processing from tracker state."""
        currency_pair = "BTC/USD"
        last_processed_timestamp = 1640995200000  # Previous run timestamp
        
        # Set up components
        influx_poller = InfluxPoller("http://test:8086", "token", "org", "bucket")
        
        strategy_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5],
            deque_maxlen=50,
            tracker=self.mock_tracker_instance,
            service_identifier="test_service",
        )

        # Mock tracker returns previous timestamp
        self.mock_tracker_instance.get_last_processed_timestamp.return_value = last_processed_timestamp

        # Create newer test data
        new_timestamp = last_processed_timestamp + 60000  # 1 minute later
        test_data = [{
            "timestamp_ms": new_timestamp,
            "currency_pair": currency_pair,
            "open": 51000.0,
        }]

        mock_query_api = Mock()
        self.mock_influx_instance.query_api.return_value = mock_query_api
        mock_tables = self._create_mock_influx_table(test_data)
        mock_query_api.query.return_value = mock_tables

        # Initialize and process
        strategy_processor.initialize_pair(currency_pair)
        
        # Verify initial state was loaded
        self.assertEqual(
            strategy_processor.last_processed_timestamps[currency_pair], 
            last_processed_timestamp
        )

        # Fetch and process newer candles
        candles, latest_ts = influx_poller.fetch_new_candles(currency_pair, last_processed_timestamp)
        
        for candle in candles:
            strategy_processor.add_candle(candle)

        # Verify new timestamp was updated
        self.mock_tracker_instance.update_last_processed_timestamp.assert_called_with(
            "test_service", currency_pair, new_timestamp
        )

    def test_multiple_currency_pairs_tracking(self):
        """Test tracking multiple currency pairs independently."""
        currency_pairs = ["BTC/USD", "ETH/USD", "ADA/USD"]
        
        strategy_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5],
            deque_maxlen=50,
            tracker=self.mock_tracker_instance,
            service_identifier="test_service",
        )

        # Mock different initial states for each pair
        def mock_get_timestamp(service, pair):
            timestamps = {
                "BTC/USD": 1640995200000,
                "ETH/USD": None,  # First run
                "ADA/USD": 1640995100000,
            }
            return timestamps.get(pair)

        self.mock_tracker_instance.get_last_processed_timestamp.side_effect = mock_get_timestamp

        # Initialize all pairs
        strategy_processor.initialize_pairs(currency_pairs)

        # Verify each pair was loaded correctly
        self.assertEqual(strategy_processor.last_processed_timestamps["BTC/USD"], 1640995200000)
        self.assertEqual(strategy_processor.last_processed_timestamps["ETH/USD"], 0)
        self.assertEqual(strategy_processor.last_processed_timestamps["ADA/USD"], 1640995100000)

        # Verify tracker was called for each pair
        expected_calls = [
            unittest.mock.call("test_service", "BTC/USD"),
            unittest.mock.call("test_service", "ETH/USD"),
            unittest.mock.call("test_service", "ADA/USD"),
        ]
        self.mock_tracker_instance.get_last_processed_timestamp.assert_has_calls(
            expected_calls, any_order=True
        )

    def test_tracker_update_on_each_candle(self):
        """Test that tracker is updated for each processed candle."""
        currency_pair = "BTC/USD"
        
        strategy_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5],
            deque_maxlen=50,
            tracker=self.mock_tracker_instance,
            service_identifier="test_service",
        )

        strategy_processor.initialize_pair(currency_pair)

        # Process multiple candles
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        candles = []
        for i in range(3):
            timestamp_ms = base_timestamp + (i * 60000)
            candle = self._create_test_candle(currency_pair, timestamp_ms)
            candles.append(candle)
            strategy_processor.add_candle(candle)

        # Verify tracker was updated for each candle
        self.assertEqual(self.mock_tracker_instance.update_last_processed_timestamp.call_count, 3)
        
        # Verify the calls were made with correct timestamps
        expected_calls = [
            unittest.mock.call("test_service", currency_pair, base_timestamp),
            unittest.mock.call("test_service", currency_pair, base_timestamp + 60000),
            unittest.mock.call("test_service", currency_pair, base_timestamp + 120000),
        ]
        self.mock_tracker_instance.update_last_processed_timestamp.assert_has_calls(expected_calls)

    def test_processor_without_tracker(self):
        """Test processor works without tracker (for backwards compatibility)."""
        strategy_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5],
            deque_maxlen=50,
            tracker=None,  # No tracker
        )

        currency_pair = "BTC/USD"
        strategy_processor.initialize_pair(currency_pair)

        # Should not fail without tracker
        candle = self._create_test_candle(currency_pair, 1640995200000)
        requests = strategy_processor.add_candle(candle)

        # Should still process candle
        self.assertEqual(len(strategy_processor.pair_deques[currency_pair]), 1)
        self.assertEqual(strategy_processor.last_processed_timestamps[currency_pair], 1640995200000)

    def test_error_handling_with_tracker(self):
        """Test error handling when tracker operations fail."""
        currency_pair = "BTC/USD"
        
        # Mock tracker to raise exception on update
        self.mock_tracker_instance.update_last_processed_timestamp.side_effect = Exception("Tracker error")
        
        strategy_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5],
            deque_maxlen=50,
            tracker=self.mock_tracker_instance,
            service_identifier="test_service",
        )

        strategy_processor.initialize_pair(currency_pair)

        # Processing should continue despite tracker error
        candle = self._create_test_candle(currency_pair, 1640995200000)
        
        # Should not raise exception
        requests = strategy_processor.add_candle(candle)
        
        # Candle should still be processed
        self.assertEqual(len(strategy_processor.pair_deques[currency_pair]), 1)

    def test_component_cleanup(self):
        """Test proper cleanup of all components."""
        influx_poller = InfluxPoller("http://test:8086", "token", "org", "bucket")
        
        strategy_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5],
            deque_maxlen=50,
            tracker=self.mock_tracker_instance,
        )
        
        kafka_publisher = KafkaPublisher("test:9092", "test-topic")

        # Add some state to processor
        strategy_processor.initialize_pair("BTC/USD")
        strategy_processor.add_candle(self._create_test_candle("BTC/USD", 1640995200000))

        # Close all components
        influx_poller.close()
        strategy_processor.close()
        kafka_publisher.close()

        # Verify cleanup
        self.mock_influx_instance.close.assert_called_once()
        self.mock_producer_instance.flush.assert_called_once()
        self.mock_producer_instance.close.assert_called_once()
        self.assertEqual(len(strategy_processor.pair_deques), 0)
        self.assertEqual(len(strategy_processor.last_processed_timestamps), 0)


if __name__ == "__main__":
    unittest.main()
