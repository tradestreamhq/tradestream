"""
Unit tests for symbol validation across exchanges.
"""

import unittest
from unittest import mock
from services.candle_ingestor.main import (
    validate_symbol_availability,
    _validate_symbols_single_exchange,
    _validate_symbols_multi_exchange,
)


class TestSymbolValidation(unittest.TestCase):

    def test_validate_symbols_single_exchange_success(self):
        """Test symbol validation for single exchange mode."""
        # Mock single exchange client
        mock_client = mock.MagicMock()
        mock_client.exchange_name = "binance"
        mock_client._normalize_symbol.side_effect = (
            lambda x: f"{x.upper().replace('USD', '/USDT')}"
        )

        # Mock exchange markets
        mock_client.exchange.load_markets.return_value = {
            "BTC/USDT": {"symbol": "BTC/USDT"},
            "ETH/USDT": {"symbol": "ETH/USDT"},
            "ADA/USDT": {"symbol": "ADA/USDT"},
        }

        symbols = ["btcusd", "ethusd", "xrpusd"]  # XRP not available
        result = _validate_symbols_single_exchange(mock_client, symbols)

        # Should return only available symbols
        self.assertEqual(len(result), 2)
        self.assertIn("btcusd", result)
        self.assertIn("ethusd", result)
        self.assertNotIn("xrpusd", result)

    def test_validate_symbols_multi_exchange_sufficient(self):
        """Test symbol validation for multi-exchange mode with sufficient exchanges."""
        # Mock multi-exchange client
        mock_client = mock.MagicMock()

        # Mock exchange clients
        mock_binance = mock.MagicMock()
        mock_binance.exchange_name = "binance"
        mock_binance._normalize_symbol.side_effect = (
            lambda x: f"{x.upper().replace('USD', '/USDT')}"
        )
        mock_binance.exchange.load_markets.return_value = {
            "BTC/USDT": {},
            "ETH/USDT": {},
            "ADA/USDT": {},
        }

        mock_coinbase = mock.MagicMock()
        mock_coinbase.exchange_name = "coinbasepro"
        mock_coinbase._normalize_symbol.side_effect = (
            lambda x: f"{x.upper().replace('USD', '/USD')}"
        )
        mock_coinbase.exchange.load_markets.return_value = {
            "BTC/USD": {},
            "ETH/USD": {},
            # ADA not available on Coinbase
        }

        mock_client.exchanges = {
            "binance": mock_binance,
            "coinbasepro": mock_coinbase,
        }

        symbols = ["btcusd", "ethusd", "adausd"]
        min_exchanges = 2

        result = _validate_symbols_multi_exchange(mock_client, symbols, min_exchanges)

        # BTC and ETH available on 2 exchanges, ADA only on 1
        self.assertEqual(len(result), 2)
        self.assertIn("btcusd", result)
        self.assertIn("ethusd", result)
        self.assertNotIn("adausd", result)

    def test_validate_symbols_multi_exchange_insufficient(self):
        """Test symbol validation when no symbols meet minimum requirement."""
        mock_client = mock.MagicMock()

        # Mock single exchange that has limited symbols
        mock_binance = mock.MagicMock()
        mock_binance.exchange_name = "binance"
        mock_binance._normalize_symbol.side_effect = (
            lambda x: f"{x.upper().replace('USD', '/USDT')}"
        )
        mock_binance.exchange.load_markets.return_value = {
            "BTC/USDT": {},
            "ETH/USDT": {},
        }

        mock_client.exchanges = {
            "binance": mock_binance,
        }

        symbols = ["btcusd", "ethusd"]
        min_exchanges = 2  # Require 2 exchanges but only have 1

        result = _validate_symbols_multi_exchange(mock_client, symbols, min_exchanges)

        # No symbols should meet the requirement
        self.assertEqual(len(result), 0)

    def test_validate_symbol_availability_single_strategy(self):
        """Test main validation function for single exchange strategy."""
        mock_client = mock.MagicMock()
        mock_client.exchange_name = "binance"
        mock_client._normalize_symbol.side_effect = lambda x: f"{x.upper()}/USDT"
        mock_client.exchange.load_markets.return_value = {
            "BTC/USDT": {},
            "ETH/USDT": {},
        }

        symbols = ["btcusd", "ethusd", "adausd"]
        result = validate_symbol_availability(mock_client, symbols, "single", 2)

        # Should validate against single exchange
        self.assertEqual(len(result), 2)  # Only BTC and ETH available

    def test_validate_symbol_availability_multi_strategy(self):
        """Test main validation function for multi-exchange strategy."""
        mock_client = mock.MagicMock()
        mock_client.exchanges = {
            "binance": mock.MagicMock(),
            "coinbasepro": mock.MagicMock(),
        }

        # Mock the exchange clients
        for name, exchange_client in mock_client.exchanges.items():
            exchange_client.exchange_name = name
            exchange_client._normalize_symbol.side_effect = (
                lambda x: f"{x.upper()}/USDT"
            )
            exchange_client.exchange.load_markets.return_value = {
                "BTC/USDT": {},
                "ETH/USDT": {},
            }

        symbols = ["btcusd", "ethusd"]
        result = validate_symbol_availability(mock_client, symbols, "multi", 2)

        # Should validate against multiple exchanges
        self.assertEqual(len(result), 2)  # Both symbols available on 2 exchanges

    def test_exchange_market_loading_error(self):
        """Test handling of exchange market loading errors."""
        mock_client = mock.MagicMock()
        mock_client.exchange_name = "binance"
        mock_client.exchange.load_markets.side_effect = Exception(
            "Market loading failed"
        )

        symbols = ["btcusd", "ethusd"]
        result = _validate_symbols_single_exchange(mock_client, symbols)

        # Should fallback to processing all symbols on error
        self.assertEqual(result, symbols)

    def test_normalize_symbol_edge_cases(self):
        """Test symbol normalization for various formats."""
        mock_client = mock.MagicMock()
        mock_client.exchange_name = "binance"

        # Test various symbol formats
        def normalize_symbol(symbol):
            if "/" in symbol:
                return symbol.upper()
            if symbol.lower().endswith("usd"):
                base = symbol[:-3].upper()
                return f"{base}/USDT"
            return symbol.upper()

        mock_client._normalize_symbol.side_effect = normalize_symbol
        mock_client.exchange.load_markets.return_value = {
            "BTC/USDT": {},
            "ETH/USDT": {},
            "BTC/USD": {},
        }

        symbols = ["btcusd", "BTC/USD", "ethusd", "INVALID"]
        result = _validate_symbols_single_exchange(mock_client, symbols)

        # Should handle various formats correctly
        expected_available = ["btcusd", "BTC/USD", "ethusd"]  # INVALID not available
        self.assertEqual(len(result), 3)
        for symbol in expected_available:
            self.assertIn(symbol, result)


class TestSymbolValidationIntegration(unittest.TestCase):
    """Integration tests for symbol validation with real-world scenarios."""

    def test_common_crypto_pairs(self):
        """Test validation with common cryptocurrency pairs."""
        # This would test with actual exchange market data
        # Mock realistic market structures
        common_pairs = [
            "btcusd",
            "ethusd",
            "adausd",
            "solusd",
            "dogeusd",
            "ltcusd",
            "linkusd",
            "dotusd",
            "uniusd",
            "maticusd",
        ]

        # Mock Binance markets (comprehensive)
        binance_markets = {f"{pair[:-3].upper()}/USDT": {} for pair in common_pairs}

        # Mock Coinbase markets (more limited)
        coinbase_limited = ["btcusd", "ethusd", "adausd", "solusd", "ltcusd", "linkusd"]
        coinbase_markets = {f"{pair[:-3].upper()}/USD": {} for pair in coinbase_limited}

        # Mock clients
        mock_multi_client = mock.MagicMock()

        mock_binance = mock.MagicMock()
        mock_binance.exchange_name = "binance"
        mock_binance._normalize_symbol.side_effect = lambda x: f"{x[:-3].upper()}/USDT"
        mock_binance.exchange.load_markets.return_value = binance_markets

        mock_coinbase = mock.MagicMock()
        mock_coinbase.exchange_name = "coinbasepro"
        mock_coinbase._normalize_symbol.side_effect = lambda x: f"{x[:-3].upper()}/USD"
        mock_coinbase.exchange.load_markets.return_value = coinbase_markets

        mock_multi_client.exchanges = {
            "binance": mock_binance,
            "coinbasepro": mock_coinbase,
        }

        result = _validate_symbols_multi_exchange(mock_multi_client, common_pairs, 2)

        # Should return only pairs available on both exchanges
        expected_count = len(coinbase_limited)  # Limited by Coinbase availability
        self.assertEqual(len(result), expected_count)

        # Verify all returned symbols are in the Coinbase-supported list
        for symbol in result:
            self.assertIn(symbol, coinbase_limited)


if __name__ == "__main__":
    unittest.main()
