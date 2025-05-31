"""
Unit tests for CCXT client.
"""

import unittest
from unittest import mock
from datetime import datetime, timezone, timedelta

from services.candle_ingestor.ccxt_client import CCXTCandleClient, MultiExchangeCandleClient


class TestCCXTCandleClient(unittest.TestCase):
    
    @mock.patch('services.candle_ingestor.ccxt_client.ccxt')
    def test_init_success(self, mock_ccxt):
        """Test successful initialization"""
        mock_exchange = mock.MagicMock()
        mock_ccxt.binance.return_value = mock_exchange
        
        client = CCXTCandleClient('binance')
        
        self.assertEqual(client.exchange_name, 'binance')
        self.assertEqual(client.exchange, mock_exchange)
        mock_ccxt.binance.assert_called_once()
    
    def test_normalize_symbol(self):
        """Test symbol normalization"""
        client = CCXTCandleClient.__new__(CCXTCandleClient)  # Skip __init__
        
        # Test various formats
        self.assertEqual(client._normalize_symbol('btcusd'), 'BTC/USDT')
        self.assertEqual(client._normalize_symbol('ethusd'), 'ETH/USDT')
        self.assertEqual(client._normalize_symbol('BTC/USD'), 'BTC/USD')
        self.assertEqual(client._normalize_symbol('ethbtc'), 'ETH/BTC')
    
    @mock.patch('services.candle_ingestor.ccxt_client.ccxt')
    def test_get_historical_candles_success(self, mock_ccxt):
        """Test successful candle fetching"""
        mock_exchange = mock.MagicMock()
        mock_ccxt.binance.return_value = mock_exchange
        
        # Mock OHLCV data
        mock_ohlcv = [
            [1640995200000, 50000.0, 51000.0, 49000.0, 50500.0, 100.5],  # Valid candle
            [1640995260000, 50500.0, 50800.0, 50200.0, 50600.0, 85.2],   # Valid candle
        ]
        mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
        
        client = CCXTCandleClient('binance')
        candles = client.get_historical_candles('btcusd', '1m', 1640995200000, 100)
        
        self.assertEqual(len(candles), 2)
        
        # Verify first candle
        self.assertEqual(candles[0]['timestamp_ms'], 1640995200000)
        self.assertEqual(candles[0]['open'], 50000.0)
        self.assertEqual(candles[0]['high'], 51000.0)
        self.assertEqual(candles[0]['low'], 49000.0)
        self.assertEqual(candles[0]['close'], 50500.0)
        self.assertEqual(candles[0]['volume'], 100.5)
        self.assertEqual(candles[0]['currency_pair'], 'btcusd')
        self.assertEqual(candles[0]['exchange'], 'binance')
    
    @mock.patch('services.candle_ingestor.ccxt_client.ccxt')
    def test_get_historical_candles_filters_invalid(self, mock_ccxt):
        """Test filtering of invalid candles"""
        mock_exchange = mock.MagicMock()
        mock_ccxt.binance.return_value = mock_exchange
        
        # Mock OHLCV data with invalid candle (high < low)
        mock_ohlcv = [
            [1640995200000, 50000.0, 51000.0, 49000.0, 50500.0, 100.5],  # Valid
            [1640995260000, 50500.0, 50200.0, 50800.0, 50600.0, 85.2],   # Invalid: high < low
            [1640995320000, 0, 0, 0, 0, 0],  # Invalid: all zeros
        ]
        mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
        
        client = CCXTCandleClient('binance')
        candles = client.get_historical_candles('btcusd', '1m', 1640995200000, 100)
        
        # Should only return the valid candle
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]['timestamp_ms'], 1640995200000)


class TestMultiExchangeCandleClient(unittest.TestCase):
    
    @mock.patch('services.candle_ingestor.ccxt_client.CCXTCandleClient')
    def test_init_success(self, mock_ccxt_client):
        """Test successful multi-exchange initialization"""
        mock_client_instance = mock.MagicMock()
        mock_ccxt_client.return_value = mock_client_instance
        
        client = MultiExchangeCandleClient(['binance', 'coinbasepro'], min_exchanges_required=2)
        
        self.assertEqual(len(client.exchanges), 2)
        self.assertIn('binance', client.exchanges)
        self.assertIn('coinbasepro', client.exchanges)
        self.assertEqual(client.min_exchanges_required, 2)
    
    @mock.patch('services.candle_ingestor.ccxt_client.CCXTCandleClient')
    def test_get_aggregated_candles_success(self, mock_ccxt_client):
        """Test successful aggregated candle fetching"""
        # Create mock clients for different exchanges
        mock_binance = mock.MagicMock()
        mock_coinbase = mock.MagicMock()
        
        def mock_client_factory(exchange_name):
            if exchange_name == "binance":
                return mock_binance
            elif exchange_name == "coinbasepro":
                return mock_coinbase
        mock_ccxt_client.side_effect = mock_client_factory
        
        # Mock candle data from different exchanges
        binance_candles = [
            {
                'timestamp_ms': 1640995200000,
                'open': 50000.0,
                'high': 51000.0,
                'low': 49000.0,
                'close': 50500.0,
                'volume': 100.0,
                'currency_pair': 'btcusd',
                'exchange': 'binance'
            }
        ]
        
        coinbase_candles = [
            {
                'timestamp_ms': 1640995200000,
                'open': 50100.0,
                'high': 51100.0,
                'low': 49100.0,
                'close': 50600.0,
                'volume': 80.0,
                'currency_pair': 'btcusd',
                'exchange': 'coinbasepro'
            }
        ]
        
        mock_binance.get_historical_candles.return_value = binance_candles
        mock_coinbase.get_historical_candles.return_value = coinbase_candles
        
        client = MultiExchangeCandleClient(['binance', 'coinbasepro'], min_exchanges_required=2)
        candles = client.get_aggregated_candles('btcusd', '1m', 1640995200000, 100)
        
        self.assertEqual(len(candles), 1)
        
        # Verify aggregated candle (volume-weighted average)
        aggregated = candles[0]
        self.assertEqual(aggregated['timestamp_ms'], 1640995200000)
        self.assertEqual(aggregated['exchange'], 'aggregated')
        self.assertEqual(aggregated['volume'], 180.0)  # Sum of volumes
        
        # Check VWAP calculation: (50500*100 + 50600*80) / 180 = 50544.44...
        expected_vwap = (50500.0 * 100.0 + 50600.0 * 80.0) / 180.0
        self.assertAlmostEqual(aggregated['close'], expected_vwap, places=2)
    
    @mock.patch('services.candle_ingestor.ccxt_client.CCXTCandleClient')
    def test_get_aggregated_candles_insufficient_exchanges(self, mock_ccxt_client):
        """Test fallback when insufficient exchanges available"""
        mock_binance = mock.MagicMock()
        mock_ccxt_client.return_value = mock_binance
        
        binance_candles = [
            {
                'timestamp_ms': 1640995200000,
                'open': 50000.0,
                'high': 51000.0,
                'low': 49000.0,
                'close': 50500.0,
                'volume': 100.0,
                'currency_pair': 'btcusd',
                'exchange': 'binance'
            }
        ]
        
        mock_binance.get_historical_candles.return_value = binance_candles
        
        # Only one exchange available, but min_exchanges_required=2
        client = MultiExchangeCandleClient(['binance'], min_exchanges_required=2)
        candles = client.get_aggregated_candles('btcusd', '1m', 1640995200000, 100)
        
        # Should return candles from the single available exchange
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]['exchange'], 'binance')
    
    def test_volume_weighted_average(self):
        """Test volume-weighted average calculation"""
        client = MultiExchangeCandleClient.__new__(MultiExchangeCandleClient)  # Skip __init__
        
        candles = [
            {
                'timestamp_ms': 1640995200000,
                'open': 50000.0,
                'high': 51000.0,
                'low': 49000.0,
                'close': 50500.0,
                'volume': 100.0,
                'exchange': 'binance'
            },
            {
                'timestamp_ms': 1640995200000,
                'open': 50100.0,
                'high': 51100.0,
                'low': 49100.0,
                'close': 50600.0,
                'volume': 200.0,  # Higher volume
                'exchange': 'coinbasepro'
            }
        ]
        
        result = client._volume_weighted_average(candles, 'btcusd')
        
        # VWAP calculation: (50500*100 + 50600*200) / 300 = 50566.67
        expected_open_vwap = (50000.0 * 100.0 + 50100.0 * 200.0) / 300.0
        expected_close_vwap = (50500.0 * 100.0 + 50600.0 * 200.0) / 300.0
        
        self.assertAlmostEqual(result['open'], expected_open_vwap, places=2)
        self.assertAlmostEqual(result['close'], expected_close_vwap, places=2)
        self.assertEqual(result['high'], 51100.0)  # Max high
        self.assertEqual(result['low'], 49000.0)   # Min low
        self.assertEqual(result['volume'], 300.0)  # Sum volume
        self.assertEqual(result['exchange'], 'aggregated')
    
    def test_simple_average_zero_volume(self):
        """Test simple average when volume is zero"""
        client = MultiExchangeCandleClient.__new__(MultiExchangeCandleClient)  # Skip __init__
        
        candles = [
            {
                'timestamp_ms': 1640995200000,
                'open': 50000.0,
                'high': 51000.0,
                'low': 49000.0,
                'close': 50500.0,
                'volume': 0.0,  # Zero volume
                'exchange': 'binance'
            },
            {
                'timestamp_ms': 1640995200000,
                'open': 50100.0,
                'high': 51100.0,
                'low': 49100.0,
                'close': 50600.0,
                'volume': 0.0,  # Zero volume
                'exchange': 'coinbasepro'
            }
        ]
        
        result = client._volume_weighted_average(candles, 'btcusd')
        
        # Should fall back to simple average
        self.assertEqual(result['open'], 50050.0)   # (50000 + 50100) / 2
        self.assertEqual(result['close'], 50550.0)  # (50500 + 50600) / 2
        self.assertEqual(result['high'], 51100.0)   # Max high
        self.assertEqual(result['low'], 49000.0)    # Min low
        self.assertEqual(result['volume'], 0.0)     # Sum volume
        self.assertEqual(result['exchange'], 'averaged')


if __name__ == '__main__':
    unittest.main()