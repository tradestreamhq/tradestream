"""Unit tests for influx_poller module."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from influxdb_client.client.exceptions import InfluxDBError
from services.backtest_request_factory.influx_poller import InfluxPoller
from services.backtest_request_factory.test_utils import (
    create_mock_influx_response,
    assert_candles_equal,
    get_candle_timestamp_ms
)


class InfluxPollerTest(unittest.TestCase):
    """Test InfluxDB polling functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_url = "http://test-influx:8086"
        self.test_token = "test-token"
        self.test_org = "test-org"
        self.test_bucket = "test-bucket"
        
        # Mock InfluxDBClient to avoid actual connections
        self.mock_client_class = patch('services.backtest_request_factory.influx_poller.InfluxDBClient').start()
        self.mock_client = Mock()
        self.mock_client_class.return_value = self.mock_client
        self.mock_client.ping.return_value = True
        
        self.poller = InfluxPoller(
            url=self.test_url,
            token=self.test_token,
            org=self.test_org,
            bucket=self.test_bucket
        )
    
    def tearDown(self):
        """Clean up test environment."""
        patch.stopall()
    
    def test_initialization_success(self):
        """Test successful InfluxPoller initialization."""
        self.assertEqual(self.poller.url, self.test_url)
        self.assertEqual(self.poller.token, self.test_token)
        self.assertEqual(self.poller.org, self.test_org)
        self.assertEqual(self.poller.bucket, self.test_bucket)
        self.assertIsNotNone(self.poller.client)
        self.mock_client.ping.assert_called_once()
    
    def test_initialization_ping_failure(self):
        """Test initialization failure due to ping failure."""
        self.mock_client.ping.return_value = False
        
        with self.assertRaises(InfluxDBError):
            InfluxPoller(
                url=self.test_url,
                token=self.test_token,
                org=self.test_org,
                bucket=self.test_bucket
            )
    
    def test_initialization_connection_error(self):
        """Test initialization failure due to connection error."""
        self.mock_client_class.side_effect = ConnectionError("Connection failed")
        
        with self.assertRaises(ConnectionError):
            InfluxPoller(
                url=self.test_url,
                token=self.test_token,
                org=self.test_org,
                bucket=self.test_bucket
            )
    
    def test_fetch_new_candles_success(self):
        """Test successful fetching of new candles."""
        # Set up mock query response
        mock_query_api = Mock()
        self.mock_client.query_api.return_value = mock_query_api
        
        # Create test data
        test_data = [
            {
                'timestamp_ms': 1640995200000,  # 2022-01-01 00:00:00 UTC
                'currency_pair': 'BTC/USD',
                'open': 50000.0,
                'high': 51000.0,
                'low': 49000.0,
                'close': 50500.0,
                'volume': 1000.0
            },
            {
                'timestamp_ms': 1640995260000,  # 2022-01-01 00:01:00 UTC
                'currency_pair': 'BTC/USD',
                'open': 50500.0,
                'high': 51500.0,
                'low': 49500.0,
                'close': 51000.0,
                'volume': 1100.0
            }
        ]
        
        mock_tables = create_mock_influx_response(test_data)
        mock_query_api.query.return_value = mock_tables
        
        # Execute test
        candles, latest_ts = self.poller.fetch_new_candles("BTC/USD", 0)
        
        # Verify results
        self.assertEqual(len(candles), 2)
        self.assertEqual(latest_ts, 1640995260000)
        
        # Verify first candle
        first_candle = candles[0]
        self.assertEqual(first_candle.currency_pair, "BTC/USD")
        self.assertEqual(first_candle.open, 50000.0)
        self.assertEqual(first_candle.high, 51000.0)
        self.assertEqual(first_candle.low, 49000.0)
        self.assertEqual(first_candle.close, 50500.0)
        self.assertEqual(first_candle.volume, 1000.0)
        self.assertEqual(get_candle_timestamp_ms(first_candle), 1640995200000)
        
        # Verify query was called with correct parameters
        mock_query_api.query.assert_called_once()
        query_args = mock_query_api.query.call_args
        self.assertIn('BTC/USD', query_args[1]['query'])
        self.assertIn(self.test_bucket, query_args[1]['query'])
    
    def test_fetch_new_candles_with_last_timestamp(self):
        """Test fetching candles with a non-zero last timestamp."""
        mock_query_api = Mock()
        self.mock_client.query_api.return_value = mock_query_api
        mock_query_api.query.return_value = []
        
        last_timestamp_ms = 1640995200000
        self.poller.fetch_new_candles("BTC/USD", last_timestamp_ms)
        
        # Verify query includes timestamp filter
        query_args = mock_query_api.query.call_args
        expected_start_ns = (last_timestamp_ms * 1_000_000) + 1
        self.assertIn(f'time(v: {expected_start_ns}ns)', query_args[1]['query'])
    
    def test_fetch_new_candles_empty_result(self):
        """Test fetching candles with empty result."""
        mock_query_api = Mock()
        self.mock_client.query_api.return_value = mock_query_api
        mock_query_api.query.return_value = []
        
        candles, latest_ts = self.poller.fetch_new_candles("BTC/USD", 0)
        
        self.assertEqual(len(candles), 0)
        self.assertEqual(latest_ts, 0)
    
    def test_fetch_new_candles_influx_error(self):
        """Test handling of InfluxDB query error."""
        mock_query_api = Mock()
        self.mock_client.query_api.return_value = mock_query_api
        mock_query_api.query.side_effect = InfluxDBError("Query failed")
        
        candles, latest_ts = self.poller.fetch_new_candles("BTC/USD", 0)
        
        self.assertEqual(len(candles), 0)
        self.assertEqual(latest_ts, 0)
    
    def test_fetch_new_candles_no_client(self):
        """Test fetching candles when client is not initialized."""
        self.poller.client = None
        
        candles, latest_ts = self.poller.fetch_new_candles("BTC/USD", 0)
        
        self.assertEqual(len(candles), 0)
        self.assertEqual(latest_ts, 0)
    
    def test_fetch_new_candles_record_processing_error(self):
        """Test handling of record processing errors."""
        mock_query_api = Mock()
        self.mock_client.query_api.return_value = mock_query_api
        
        # Create a mock record that will cause processing error
        mock_record = Mock()
        mock_record.get_time.side_effect = Exception("Time parsing error")
        mock_record.values = {'currency_pair': 'BTC/USD'}
        
        mock_table = Mock()
        mock_table.records = [mock_record]
        mock_query_api.query.return_value = [mock_table]
        
        candles, latest_ts = self.poller.fetch_new_candles("BTC/USD", 0)
        
        # Should return empty result due to processing error
        self.assertEqual(len(candles), 0)
        self.assertEqual(latest_ts, 0)
    
    def test_timezone_handling(self):
        """Test proper timezone handling for timestamps."""
        mock_query_api = Mock()
        self.mock_client.query_api.return_value = mock_query_api
        
        # Create mock record with naive datetime
        mock_record = Mock()
        naive_datetime = datetime.fromtimestamp(1640995200)  # Naive datetime
        mock_record.get_time.return_value = naive_datetime
        mock_record.values = {
            'currency_pair': 'BTC/USD',
            'open': 50000.0,
            'high': 51000.0,
            'low': 49000.0,
            'close': 50500.0,
            'volume': 1000.0
        }
        
        mock_table = Mock()
        mock_table.records = [mock_record]
        mock_query_api.query.return_value = [mock_table]
        
        candles, latest_ts = self.poller.fetch_new_candles("BTC/USD", 0)
        
        # Should handle naive datetime correctly
        self.assertEqual(len(candles), 1)
        self.assertGreater(latest_ts, 0)
    
    def test_close_client(self):
        """Test closing the InfluxDB client."""
        self.poller.close()
        self.mock_client.close.assert_called_once()
    
    def test_close_client_when_none(self):
        """Test closing when client is None."""
        self.poller.client = None
        # Should not raise exception
        self.poller.close()
    
    @patch('services.backtest_request_factory.influx_poller.logging')
    def test_logging_behavior(self, mock_logging):
        """Test that appropriate logging occurs."""
        mock_query_api = Mock()
        self.mock_client.query_api.return_value = mock_query_api
        mock_query_api.query.return_value = []
        
        self.poller.fetch_new_candles("BTC/USD", 0)
        
        # Verify info logging was called
        mock_logging.info.assert_called()
    
    def test_flux_query_construction(self):
        """Test that Flux query is constructed correctly."""
        mock_query_api = Mock()
        self.mock_client.query_api.return_value = mock_query_api
        mock_query_api.query.return_value = []
        
        self.poller.fetch_new_candles("ETH/USD", 1640995200000)
        
        query_args = mock_query_api.query.call_args
        flux_query = query_args[1]['query']
        
        # Verify query components
        self.assertIn(f'from(bucket: "{self.test_bucket}")', flux_query)
        self.assertIn('_measurement == "candles"', flux_query)
        self.assertIn('currency_pair == "ETH/USD"', flux_query)
        self.assertIn('pivot(rowKey:["_time"], columnKey: ["_field"]', flux_query)
        self.assertIn('sort(columns: ["_time"], desc: false)', flux_query)


if __name__ == '__main__':
    unittest.main()
