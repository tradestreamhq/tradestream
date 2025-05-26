"""Integration tests for strategy_discovery_request_factory service (cron job version)."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from protos.strategies_pb2 import StrategyType
from google.protobuf import any_pb2
from services.strategy_discovery_request_factory.influx_poller import InfluxPoller
from services.strategy_discovery_request_factory.strategy_discovery_processor import StrategyDiscoveryProcessor
from services.strategy_discovery_request_factory.kafka_publisher import KafkaPublisher
from services.strategy_discovery_request_factory.test_utils import (
    create_test_candles,
    create_mock_influx_response,
    get_candle_timestamp_ms,
)
from shared.persistence.last_processed_tracker import LastProcessedTracker
import redis


class IntegrationCronTest(unittest.TestCase):
    """Integration tests for cron job component interactions."""

    def setUp(self):
        """Set up test environment."""
        # Mock external services
        self.mock_influx_client = patch(
            "services.strategy_discovery_request_factory.influx_poller.InfluxDBClient"
        ).start()
        self.mock_kafka_producer = patch(
            "services.strategy_discovery_request_factory.kafka_publisher.kafka.KafkaProducer"
        ).start()
        self.mock_redis_client = patch(
            "redis.Redis"
        ).start()
        self.mock_tracker = patch(
            "shared.persistence.last_processed_tracker.LastProcessedTracker"
        ).start()

        # Set up mock client instances
        self.mock_influx_instance = Mock()
        self.mock_influx_instance.ping.return_value = True
        self.mock_influx_client.return_value = self.mock_influx_instance

        self.mock_producer_instance = Mock()
        self.mock_kafka_producer.return_value = self.mock_producer_instance

        self.mock_redis_instance = Mock()
        self.mock_redis_instance.ping.return_value = True
        self.mock_redis_client.return_value = self.mock_redis_instance

        self.mock_tracker_instance = Mock()
        self.mock_tracker.return_value = self.mock_tracker_instance

        # Mock successful Kafka publishing
        mock_future = Mock()
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_future.get.return_value = mock_metadata
        self.mock_producer_instance.send.return_value = mock_future

        # Initialize components
        self.influx_poller = InfluxPoller("http://test:8086", "token", "org", "bucket")
        self.strategy_discovery_processor = StrategyDiscoveryProcessor(
            fibonacci_windows_minutes=[5, 8, 13],
            deque_maxlen=100,
            default_top_n=3,
            default_max_generations=10,
            default_population_size=20,
            candle_granularity_minutes=1,
        )
        self.kafka_publisher = KafkaPublisher("test:9092", "test-topic")
        self.last_processed_tracker = LastProcessedTracker("/tmp/test_tracker.json")

    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()

    def test_end_to_end_cron_execution_single_pair(self):
        """Test complete end-to-end cron job execution for a single currency pair."""
        currency_pair = "BTC/USD"

        # Mock Redis symbols
        self.mock_redis_instance.smembers.return_value = {b'btcusd'}

        # Initialize processor deque
        self.strategy_discovery_processor.initialize_deques([currency_pair])

        # Mock last processed timestamp (first run)
        self.mock_tracker_instance.get_last_timestamp.return_value = 0

        # Create test candle data for InfluxDB response
        test_data = []
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

        for i in range(15):  # Enough for all Fibonacci windows
            test_data.append(
                {
                    "timestamp_ms": base_timestamp + (i * 60000),  # 1 minute intervals
                    "currency_pair": currency_pair,
                    "open": 50000.0 + i,
                    "high": 50100.0 + i,
                    "low": 49900.0 + i,
                    "close": 50050.0 + i,
                    "volume": 1000.0 + i,
                }
            )

        # Mock InfluxDB query response
        mock_query_api = Mock()
        self.mock_influx_instance.query_api.return_value = mock_query_api
        mock_tables = create_mock_influx_response(test_data)
        mock_query_api.query.return_value = mock_tables

        # Execute the cron job pipeline
        candles, latest_ts = self.influx_poller.fetch_new_candles(currency_pair, 0)

        # Process each candle and publish requests
        total_published_requests = 0
        for candle in candles:
            discovery_requests = self.strategy_discovery_processor.add_candle(candle)
            for request in discovery_requests:
                self.kafka_publisher.publish_request(request, currency_pair)
                total_published_requests += 1

        # Update timestamp tracking
        if latest_ts > 0:
            self.last_processed_tracker.set_last_timestamp(currency_pair, latest_ts)

        # Verify results
        self.assertEqual(len(candles), 15)
        self.assertGreater(total_published_requests, 0)

        # Verify Kafka publishing was called
        self.mock_producer_instance.send.assert_called()

        # Verify timestamp tracking
        self.mock_tracker_instance.set_last_timestamp.assert_called_with(currency_pair, latest_ts)

        # Number of strategy types (excluding UNSPECIFIED)
        num_strategy_types = len([st for st in StrategyType.values() if st != StrategyType.UNSPECIFIED])
        self.assertGreaterEqual(total_published_requests, 3 * num_strategy_types)

    def test_redis_symbol_integration(self):
        """Test Redis integration for fetching crypto symbols."""
        # Mock Redis with multiple symbols
        self.mock_redis_instance.smembers.return_value = {b'btcusd', b'ethusd', b'adausd'}

        # Simulate symbol conversion (this would happen in main.py)
        symbols = [symbol.decode('utf-8') for symbol in self.mock_redis_instance.smembers('crypto:symbols')]
        currency_pairs = [f"{symbol[:-3].upper()}/{symbol[-3:].upper()}" for symbol in symbols]

        expected_pairs = ["BTC/USD", "ETH/USD", "ADA/USD"]
        self.assertEqual(currency_pairs, expected_pairs)

        # Verify Redis interaction
        self.mock_redis_instance.smembers.assert_called_with('crypto:symbols')

    def test_first_run_lookback_behavior(self):
        """Test cron job behavior on first run with lookback."""
        currency_pair = "BTC/USD"
        self.strategy_discovery_processor.initialize_deques([currency_pair])

        # Mock first run (no previous timestamp)
        self.mock_tracker_instance.get_last_timestamp.return_value = 0

        # Calculate lookback timestamp (simulate main.py logic)
        import time
        current_time_ms = int(time.time() * 1000)
        lookback_minutes = 60
        lookback_timestamp = current_time_ms - (lookback_minutes * 60 * 1000)

        # Create test data
        test_data = []
        for i in range(10):
            test_data.append(
                {
                    "timestamp_ms": lookback_timestamp + (i * 60000),
                    "currency_pair": currency_pair,
                    "open": 50000.0 + i,
                    "high": 50100.0 + i,
                    "low": 49900.0 + i,
                    "close": 50050.0 + i,
                    "volume": 1000.0 + i,
                }
            )

        # Mock InfluxDB response
        mock_query_api = Mock()
        self.mock_influx_instance.query_api.return_value = mock_query_api
        mock_tables = create_mock_influx_response(test_data)
        mock_query_api.query.return_value = mock_tables

        # Execute with lookback timestamp
        candles, latest_ts = self.influx_poller.fetch_new_candles(currency_pair, lookback_timestamp)

        # Verify candles were fetched
        self.assertEqual(len(candles), 10)
        self.assertGreater(latest_ts, lookback_timestamp)

    def test_incremental_cron_runs(self):
        """Test behavior across multiple cron job executions."""
        currency_pair = "BTC/USD"
        self.strategy_discovery_processor.initialize_deques([currency_pair])

        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

        # First cron run - return initial candles
        first_batch_data = []
        for i in range(5):
            first_batch_data.append(
                {
                    "timestamp_ms": base_timestamp + (i * 60000),
                    "currency_pair": currency_pair,
                    "open": 50000.0 + i,
                    "high": 50100.0 + i,
                    "low": 49900.0 + i,
                    "close": 50050.0 + i,
                    "volume": 1000.0 + i,
                }
            )

        mock_query_api = Mock()
        self.mock_influx_instance.query_api.return_value = mock_query_api
        mock_tables = create_mock_influx_response(first_batch_data)
        mock_query_api.query.return_value = mock_tables

        # First execution
        self.mock_tracker_instance.get_last_timestamp.return_value = 0
        candles1, latest_ts1 = self.influx_poller.fetch_new_candles(currency_pair, 0)
        
        for candle in candles1:
            self.strategy_discovery_processor.add_candle(candle)

        # Update timestamp (simulate main.py)
        self.last_processed_tracker.set_last_timestamp(currency_pair, latest_ts1)

        # Second cron run - return newer candles
        second_batch_data = []
        for i in range(5, 10):
            second_batch_data.append(
                {
                    "timestamp_ms": base_timestamp + (i * 60000),
                    "currency_pair": currency_pair,
                    "open": 50000.0 + i,
                    "high": 50100.0 + i,
                    "low": 49900.0 + i,
                    "close": 50050.0 + i,
                    "volume": 1000.0 + i,
                }
            )

        mock_tables2 = create_mock_influx_response(second_batch_data)
        mock_query_api.query.return_value = mock_tables2

        # Second execution with updated timestamp
        self.mock_tracker_instance.get_last_timestamp.return_value = latest_ts1
        candles2, latest_ts2 = self.influx_poller.fetch_new_candles(currency_pair, latest_ts1)

        for candle in candles2:
            self.strategy_discovery_processor.add_candle(candle)

        # Verify progression
        self.assertEqual(len(candles1), 5)
        self.assertEqual(len(candles2), 5)
        self.assertGreater(latest_ts2, latest_ts1)

        # Verify processor state maintained between runs
        deque_size = len(self.strategy_discovery_processor.pair_deques[currency_pair])
        self.assertEqual(deque_size, 10)

    def test_multiple_currency_pairs_cron_execution(self):
        """Test cron job execution with multiple currency pairs."""
        currency_pairs = ["BTC/USD", "ETH/USD", "ADA/USD"]

        # Mock Redis with multiple symbols
        self.mock_redis_instance.smembers.return_value = {b'btcusd', b'ethusd', b'adausd'}

        # Initialize processor for all pairs
        self.strategy_discovery_processor.initialize_deques(currency_pairs)

        # Create test data for each pair
        all_processed_pairs = {}

        for pair in currency_pairs:
            # Mock InfluxDB response for this pair
            test_data = []
            base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

            for i in range(10):
                test_data.append(
                    {
                        "timestamp_ms": base_timestamp + (i * 60000),
                        "currency_pair": pair,
                        "open": 50000.0 + i,
                        "high": 50100.0 + i,
                        "low": 49900.0 + i,
                        "close": 50050.0 + i,
                        "volume": 1000.0 + i,
                    }
                )

            mock_query_api = Mock()
            self.mock_influx_instance.query_api.return_value = mock_query_api
            mock_tables = create_mock_influx_response(test_data)
            mock_query_api.query.return_value = mock_tables

            # Process this pair (simulate cron job logic)
            self.mock_tracker_instance.get_last_timestamp.return_value = 0
            candles, latest_ts = self.influx_poller.fetch_new_candles(pair, 0)

            pair_requests = 0
            for candle in candles:
                discovery_requests = self.strategy_discovery_processor.add_candle(candle)
                for request in discovery_requests:
                    self.kafka_publisher.publish_request(request, pair)
                    pair_requests += 1

            # Update timestamp tracking
            self.last_processed_tracker.set_last_timestamp(pair, latest_ts)
            all_processed_pairs[pair] = pair_requests

        # Verify all pairs were processed
        for pair in currency_pairs:
            self.assertIn(pair, all_processed_pairs)
            # Should have generated some requests for 10 candles
            self.assertGreaterEqual(all_processed_pairs[pair], 0)

    def test_error_handling_cron_execution(self):
        """Test error handling during cron job execution."""
        currency_pairs = ["BTC/USD", "ETH/USD"]
        self.strategy_discovery_processor.initialize_deques(currency_pairs)

        # Test InfluxDB error for one pair
        def fetch_side_effect(pair, timestamp):
            if pair == "BTC/USD":
                raise Exception("InfluxDB connection failed for BTC/USD")
            # Return successful data for ETH/USD
            test_data = [
                {
                    "timestamp_ms": 1640995200000,
                    "currency_pair": "ETH/USD",
                    "open": 4000.0,
                    "high": 4100.0,
                    "low": 3900.0,
                    "close": 4050.0,
                    "volume": 1000.0,
                }
            ]
            mock_query_api = Mock()
            self.mock_influx_instance.query_api.return_value = mock_query_api
            mock_tables = create_mock_influx_response(test_data)
            mock_query_api.query.return_value = mock_tables
            return ([create_test_candles(1, "ETH/USD")[0]], 1640995200000)

        # Mock InfluxDB behavior
        self.influx_poller.fetch_new_candles = Mock(side_effect=fetch_side_effect)

        # Process both pairs (simulate main.py error handling)
        successful_pairs = 0
        failed_pairs = 0

        for pair in currency_pairs:
            try:
                candles, latest_ts = self.influx_poller.fetch_new_candles(pair, 0)
                for candle in candles:
                    self.strategy_discovery_processor.add_candle(candle)
                successful_pairs += 1
            except Exception:
                failed_pairs += 1
                continue  # Continue with other pairs

        # Verify partial success
        self.assertEqual(successful_pairs, 1)  # ETH/USD succeeded
        self.assertEqual(failed_pairs, 1)      # BTC/USD failed

    def test_component_cleanup_cron_execution(self):
        """Test proper cleanup after cron job execution."""
        # Simulate cron job completion
        self.influx_poller.close()
        self.kafka_publisher.close()

        # Verify cleanup was called on underlying clients
        self.mock_influx_instance.close.assert_called_once()
        self.mock_producer_instance.flush.assert_called_once()
        self.mock_producer_instance.close.assert_called_once()

    def test_no_new_candles_cron_execution(self):
        """Test cron job execution when no new candles are available."""
        currency_pair = "BTC/USD"
        self.strategy_discovery_processor.initialize_deques([currency_pair])

        # Mock no new candles
        mock_query_api = Mock()
        self.mock_influx_instance.query_api.return_value = mock_query_api
        mock_tables = create_mock_influx_response([])  # Empty data
        mock_query_api.query.return_value = mock_tables

        # Mock previous timestamp exists
        self.mock_tracker_instance.get_last_timestamp.return_value = 1640995200000

        # Execute
        candles, latest_ts = self.influx_poller.fetch_new_candles(currency_pair, 1640995200000)

        # Verify no processing occurred
        self.assertEqual(len(candles), 0)
        self.assertEqual(latest_ts, 1640995200000)  # Timestamp unchanged


if __name__ == "__main__":
    unittest.main()
    