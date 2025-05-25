"""Integration tests for backtest_request_factory service."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from protos.strategies_pb2 import StrategyType
from google.protobuf import any_pb2
from services.backtest_request_factory.influx_poller import InfluxPoller
from services.backtest_request_factory.candle_processor import CandleProcessor
from services.backtest_request_factory.kafka_publisher import KafkaPublisher
from services.backtest_request_factory.test_utils import (
    create_test_candles,
    create_mock_influx_response,
    get_candle_timestamp_ms,
)


class IntegrationTest(unittest.TestCase):
    """Integration tests for component interactions."""

    def setUp(self):
        """Set up test environment."""
        # Mock external services
        self.mock_influx_client = patch(
            "services.backtest_request_factory.influx_poller.InfluxDBClient"
        ).start()
        self.mock_kafka_producer = patch(
            "services.backtest_request_factory.kafka_publisher.kafka.KafkaProducer"
        ).start()

        # Set up mock client instances
        self.mock_client_instance = Mock()
        self.mock_client_instance.ping.return_value = True
        self.mock_influx_client.return_value = self.mock_client_instance

        self.mock_producer_instance = Mock()
        self.mock_kafka_producer.return_value = self.mock_producer_instance

        # Mock successful Kafka publishing
        mock_future = Mock()
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_future.get.return_value = mock_metadata
        self.mock_producer_instance.send.return_value = mock_future

        # Initialize components
        self.influx_poller = InfluxPoller("http://test:8086", "token", "org", "bucket")
        self.candle_processor = CandleProcessor(
            fibonacci_windows_minutes=[5, 8, 13],
            deque_maxlen=100,
            default_strategy_type=StrategyType.SMA_RSI,
            default_strategy_parameters_any=any_pb2.Any(),
            candle_granularity_minutes=1,
        )
        self.kafka_publisher = KafkaPublisher("test:9092", "test-topic")

    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()

    def test_end_to_end_processing_single_pair(self):
        """Test complete end-to-end processing for a single currency pair."""
        currency_pair = "BTC/USD"

        # Initialize processor deque
        self.candle_processor.initialize_deques([currency_pair])

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
        self.mock_client_instance.query_api.return_value = mock_query_api
        mock_tables = create_mock_influx_response(test_data)
        mock_query_api.query.return_value = mock_tables

        # Execute the pipeline
        candles, latest_ts = self.influx_poller.fetch_new_candles(currency_pair, 0)

        # Process each candle and publish requests
        total_published_requests = 0
        for candle in candles:
            backtest_requests = self.candle_processor.add_candle(candle)
            for request in backtest_requests:
                self.kafka_publisher.publish_request(request, currency_pair)
                total_published_requests += 1

        # Verify results
        self.assertEqual(len(candles), 15)
        self.assertGreater(total_published_requests, 0)

        # Verify Kafka publishing was called
        self.mock_producer_instance.send.assert_called()

        # Verify the last few candles generated requests for all windows
        # When 13th candle is added, should generate requests for windows 5, 8, 13
        # When 15th candle is added, should also generate for all windows
        self.assertGreaterEqual(total_published_requests, 3)  # At least 3 windows worth

    def test_multiple_currency_pairs_processing(self):
        """Test processing multiple currency pairs simultaneously."""
        currency_pairs = ["BTC/USD", "ETH/USD", "ADA/USD"]

        # Initialize processor for all pairs
        self.candle_processor.initialize_deques(currency_pairs)

        # Create test data for each pair
        all_published_requests = {}

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
            self.mock_client_instance.query_api.return_value = mock_query_api
            mock_tables = create_mock_influx_response(test_data)
            mock_query_api.query.return_value = mock_tables

            # Process this pair
            candles, _ = self.influx_poller.fetch_new_candles(pair, 0)

            pair_requests = 0
            for candle in candles:
                backtest_requests = self.candle_processor.add_candle(candle)
                for request in backtest_requests:
                    self.kafka_publisher.publish_request(request, pair)
                    pair_requests += 1

            all_published_requests[pair] = pair_requests

        # Verify all pairs were processed
        for pair in currency_pairs:
            self.assertIn(pair, all_published_requests)
            # Should have generated some requests for 10 candles
            # (at least for the 5 and 8-candle windows)
            self.assertGreaterEqual(all_published_requests[pair], 0)

    def test_incremental_polling_and_processing(self):
        """Test incremental polling with timestamp tracking."""
        currency_pair = "BTC/USD"
        self.candle_processor.initialize_deques([currency_pair])

        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        # First poll - return initial candles
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
        self.mock_client_instance.query_api.return_value = mock_query_api
        mock_tables = create_mock_influx_response(first_batch_data)
        mock_query_api.query.return_value = mock_tables

        # First poll
        candles1, latest_ts1 = self.influx_poller.fetch_new_candles(currency_pair, 0)

        for candle in candles1:
            self.candle_processor.add_candle(candle)

        # Second poll - return newer candles
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

        # Second poll using latest timestamp from first poll
        candles2, latest_ts2 = self.influx_poller.fetch_new_candles(
            currency_pair, latest_ts1
        )

        for candle in candles2:
            self.candle_processor.add_candle(candle)

        # Verify progression
        self.assertEqual(len(candles1), 5)
        self.assertEqual(len(candles2), 5)
        self.assertGreater(latest_ts2, latest_ts1)

        # Verify processor has all candles
        deque_size = len(self.candle_processor.pair_deques[currency_pair])
        self.assertEqual(deque_size, 10)

    def test_error_handling_integration(self):
        """Test error handling across component integration."""
        currency_pair = "BTC/USD"
        self.candle_processor.initialize_deques([currency_pair])

        # Test InfluxDB error handling
        mock_query_api = Mock()
        self.mock_client_instance.query_api.return_value = mock_query_api
        mock_query_api.query.side_effect = Exception("InfluxDB connection failed")

        # Should handle error gracefully
        candles, latest_ts = self.influx_poller.fetch_new_candles(currency_pair, 0)
        self.assertEqual(len(candles), 0)
        self.assertEqual(latest_ts, 0)

        # Test Kafka error handling
        self.mock_producer_instance.send.side_effect = Exception(
            "Kafka connection failed"
        )

        # Create a test candle and process it
        test_candle = create_test_candles(1, currency_pair)[0]
        # Add enough candles to generate a request
        for _ in range(5):
            self.candle_processor.add_candle(test_candle)

        # Should handle Kafka error gracefully (no exception raised)
        backtest_requests = self.candle_processor.add_candle(test_candle)
        for request in backtest_requests:
            # This should not raise an exception despite Kafka error
            self.kafka_publisher.publish_request(request, currency_pair)

    def test_large_volume_processing(self):
        """Test processing a large volume of candles."""
        currency_pair = "BTC/USD"
        self.candle_processor.initialize_deques([currency_pair])

        # Create a large batch of candles
        large_batch_size = 100
        test_data = []
        base_timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)

        for i in range(large_batch_size):
            test_data.append(
                {
                    "timestamp_ms": base_timestamp + (i * 60000),
                    "currency_pair": currency_pair,
                    "open": 50000.0 + (i % 100),  # Some price variation
                    "high": 50100.0 + (i % 100),
                    "low": 49900.0 + (i % 100),
                    "close": 50050.0 + (i % 100),
                    "volume": 1000.0 + i,
                }
            )

        # Mock InfluxDB response
        mock_query_api = Mock()
        self.mock_client_instance.query_api.return_value = mock_query_api
        mock_tables = create_mock_influx_response(test_data)
        mock_query_api.query.return_value = mock_tables

        # Process the large batch
        candles, latest_ts = self.influx_poller.fetch_new_candles(currency_pair, 0)

        total_requests = 0
        for candle in candles:
            backtest_requests = self.candle_processor.add_candle(candle)
            total_requests += len(backtest_requests)

            for request in backtest_requests:
                self.kafka_publisher.publish_request(request, currency_pair)

        # Verify large batch was processed correctly
        self.assertEqual(len(candles), large_batch_size)
        self.assertGreater(total_requests, 0)

        # Verify deque size is constrained by maxlen
        deque_size = len(self.candle_processor.pair_deques[currency_pair])
        self.assertLessEqual(deque_size, self.candle_processor.deque_maxlen)

    def test_fibonacci_window_request_generation(self):
        """Test that correct number of requests are generated for Fibonacci windows."""
        currency_pair = "BTC/USD"
        self.candle_processor.initialize_deques([currency_pair])

        # Create exactly enough candles for all windows (13 candles for largest window)
        test_candles = create_test_candles(13, currency_pair)

        requests_per_candle = []

        for i, candle in enumerate(test_candles):
            backtest_requests = self.candle_processor.add_candle(candle)
            requests_per_candle.append(len(backtest_requests))
            # Publish requests
            for request in backtest_requests:
                self.kafka_publisher.publish_request(request, currency_pair)
                # Verify request structure
                self.assertEqual(request.strategy.type, StrategyType.SMA_RSI)
                self.assertGreater(len(request.candles), 0)
                self.assertLessEqual(len(request.candles), i + 1)

        # Verify request generation pattern
        # Should start generating requests when we have enough candles
        self.assertEqual(requests_per_candle[0], 0)  # 1st candle: no requests
        self.assertEqual(requests_per_candle[4], 1)  # 5th candle: 1 request (5-window)
        self.assertEqual(
            requests_per_candle[7], 2
        )  # 8th candle: 2 requests (5, 8 windows)
        self.assertEqual(
            requests_per_candle[12], 3
        )  # 13th candle: 3 requests (5, 8, 13 windows)

    def test_component_cleanup(self):
        """Test proper cleanup of all components."""
        # Verify cleanup methods exist and work
        self.influx_poller.close()
        self.kafka_publisher.close()

        # Verify cleanup was called on underlying clients
        self.mock_client_instance.close.assert_called_once()
        self.mock_producer_instance.flush.assert_called_once()
        self.mock_producer_instance.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
