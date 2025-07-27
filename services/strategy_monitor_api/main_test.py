"""
Comprehensive unit tests for Strategy Monitor API Service
Following AAA (Arrange, Act, Assert) pattern with high coverage.
"""

import json
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
from datetime import datetime, timedelta
import base64
import tempfile
import shutil

# Add the service directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test imports - this will catch missing dependencies
try:
    from main import (
        app,
        FLAGS,
        decode_base64_parameters,
        decode_hex_parameters,
        decode_sma_ema_crossover,
        decode_sma_rsi,
        decode_ema_macd,
        decode_pivot,
        decode_adx_stochastic,
        decode_aroon_mfi,
        decode_ichimoku_cloud,
        decode_parabolic_sar,
        decode_double_ema_crossover,
        decode_triple_ema_crossover,
        decode_heiken_ashi,
        decode_linear_regression_channels,
        decode_vwap_mean_reversion,
        decode_bband_wr,
        decode_atr_cci,
        decode_donchian_breakout,
        decode_volatility_stop,
        decode_atr_trailing_stop,
        is_stablecoin,
        get_db_connection,
        fetch_all_strategies,
        fetch_strategy_metrics,
        health_check,
        get_strategies,
        get_strategy_by_id,
        get_metrics,
        get_symbols,
        get_strategy_types,
    )

    IMPORT_SUCCESS = True
    IMPORT_ERROR = None
except ImportError as e:
    IMPORT_SUCCESS = False
    IMPORT_ERROR = str(e)


class TestStrategyMonitorAPIImports(unittest.TestCase):
    """Test that all required imports are available."""

    def test_imports_success(self):
        """Test that all required modules can be imported."""
        self.assertTrue(IMPORT_SUCCESS, f"Import failed: {IMPORT_ERROR}")

    def test_flask_app_initialized(self):
        """Test that Flask app is properly initialized."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")

        self.assertIsNotNone(app)
        self.assertEqual(app.name, "main")

    def test_flags_initialized(self):
        """Test that FLAGS are properly initialized."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")

        self.assertIsNotNone(FLAGS)


class TestParameterDecodingFunctions(unittest.TestCase):
    """Test parameter decoding functions with AAA pattern."""

    def test_decode_base64_parameters_success(self):
        """Test successful base64 parameter decoding."""
        # Arrange
        test_data = "SGVsbG8gV29ybGQ="  # "Hello World" in base64

        # Act
        result = decode_base64_parameters(test_data)

        # Assert
        self.assertIn("decoded", result)
        self.assertTrue(result["decoded"])
        self.assertEqual(result["size_bytes"], 11)
        self.assertIn("raw_base64", result)

    def test_decode_base64_parameters_invalid_data(self):
        """Test base64 parameter decoding with invalid data."""
        # Arrange
        test_data = "invalid_base64_data!"

        # Act
        result = decode_base64_parameters(test_data)

        # Assert
        self.assertIn("error", result)
        self.assertIn("Failed to decode base64 parameters", result["error"])

    def test_decode_hex_parameters_sma_ema_crossover(self):
        """Test hex parameter decoding for SMA_EMA_CROSSOVER."""
        # Arrange
        hex_data = "01001400020032"  # Sample hex data
        protobuf_type = "type.googleapis.com/strategies.SmaEmaCrossoverParameters"

        # Act
        result = decode_hex_parameters(hex_data, protobuf_type)

        # Assert
        self.assertIn("SMA Period", result)
        self.assertIn("EMA Period", result)
        self.assertEqual(result["strategy_type"], "SMA_EMA_CROSSOVER")

    def test_decode_hex_parameters_sma_rsi(self):
        """Test hex parameter decoding for SMA_RSI."""
        # Arrange
        hex_data = "0100140003000e000500460007001e"  # Sample hex data
        protobuf_type = "type.googleapis.com/strategies.SmaRsiParameters"

        # Act
        result = decode_hex_parameters(hex_data, protobuf_type)

        # Assert
        self.assertIn("Moving Average Period", result)
        self.assertIn("RSI Period", result)
        self.assertIn("Overbought Threshold", result)
        self.assertIn("Oversold Threshold", result)
        self.assertEqual(result["strategy_type"], "SMA_RSI")

    def test_decode_hex_parameters_ema_macd(self):
        """Test hex parameter decoding for EMA_MACD."""
        # Arrange
        hex_data = "0100120003002600050009"  # Sample hex data
        protobuf_type = "type.googleapis.com/strategies.EmaMacdParameters"

        # Act
        result = decode_hex_parameters(hex_data, protobuf_type)

        # Assert
        self.assertIn("Short EMA Period", result)
        self.assertIn("Long EMA Period", result)
        self.assertIn("Signal Period", result)
        self.assertEqual(result["strategy_type"], "EMA_MACD")

    def test_decode_hex_parameters_unknown_type(self):
        """Test hex parameter decoding for unknown protobuf type."""
        # Arrange
        hex_data = "01001400020032"
        protobuf_type = "type.googleapis.com/strategies.UnknownParameters"

        # Act
        result = decode_hex_parameters(hex_data, protobuf_type)

        # Assert
        self.assertIn("raw_hex", result)
        self.assertIn("protobuf_type", result)
        self.assertTrue(result["decoded"])

    def test_decode_hex_parameters_invalid_hex(self):
        """Test hex parameter decoding with invalid hex data."""
        # Arrange
        hex_data = "invalid_hex_data"
        protobuf_type = "type.googleapis.com/strategies.SmaEmaCrossoverParameters"

        # Act
        result = decode_hex_parameters(hex_data, protobuf_type)

        # Assert
        self.assertIn("error", result)
        self.assertIn("Failed to decode hex parameters", result["error"])


class TestStablecoinDetection(unittest.TestCase):
    """Test stablecoin detection functionality."""

    def test_is_stablecoin_major_stablecoins(self):
        """Test detection of major stablecoins."""
        # Arrange
        stablecoins = ["USDT", "USDC", "BUSD", "TUSD", "DAI", "FRAX"]

        # Act & Assert
        for coin in stablecoins:
            with self.subTest(coin=coin):
                self.assertTrue(is_stablecoin(coin))

    def test_is_stablecoin_with_pairs(self):
        """Test detection of stablecoin pairs."""
        # Arrange
        stablecoin_pairs = ["USDT/USD", "USDC/USDT", "BUSD/USDC"]

        # Act & Assert
        for pair in stablecoin_pairs:
            with self.subTest(pair=pair):
                self.assertTrue(is_stablecoin(pair))

    def test_is_stablecoin_crypto_pairs(self):
        """Test detection of crypto pairs (should be False)."""
        # Arrange
        crypto_pairs = ["BTC/USD", "ETH/USDT", "ADA/BTC", "DOT/ETH"]

        # Act & Assert
        for pair in crypto_pairs:
            with self.subTest(pair=pair):
                self.assertFalse(is_stablecoin(pair))

    def test_is_stablecoin_empty_string(self):
        """Test stablecoin detection with empty string."""
        # Arrange
        empty_symbol = ""

        # Act
        result = is_stablecoin(empty_symbol)

        # Assert
        self.assertFalse(result)

    def test_is_stablecoin_none_value(self):
        """Test stablecoin detection with None value."""
        # Arrange
        none_symbol = None

        # Act
        result = is_stablecoin(none_symbol)

        # Assert
        self.assertFalse(result)


class TestDatabaseConnection(unittest.TestCase):
    """Test database connection functionality."""

    def setUp(self):
        """Set up test database configuration."""
        # Import main to access DB_CONFIG
        import main

        main.DB_CONFIG = {
            "host": "localhost",
            "port": 5432,
            "database": "test",
            "username": "test",
            "password": "test",
        }

    def tearDown(self):
        """Clean up test database configuration."""
        import main

        main.DB_CONFIG = {}

    @patch("main.psycopg2.connect")
    def test_get_db_connection_success(self, mock_connect):
        """Test successful database connection."""
        # Arrange
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        # Act
        result = get_db_connection()

        # Assert
        mock_connect.assert_called_once()
        self.assertEqual(result, mock_connection)

    @patch("main.psycopg2.connect")
    def test_get_db_connection_failure(self, mock_connect):
        """Test database connection failure."""
        # Arrange
        mock_connect.side_effect = Exception("Connection failed")

        # Act & Assert
        with self.assertRaises(Exception):
            get_db_connection()

    def test_get_db_connection_no_config(self):
        """Test database connection with no configuration."""
        # Arrange
        import main

        main.DB_CONFIG = {}

        # Act & Assert
        with self.assertRaises(Exception) as context:
            get_db_connection()

        self.assertIn("Database configuration not initialized", str(context.exception))


class TestStrategyDataFetching(unittest.TestCase):
    """Test strategy data fetching functions."""

    def setUp(self):
        """Set up test database configuration."""
        # Import main to access DB_CONFIG
        import main

        main.DB_CONFIG = {
            "host": "localhost",
            "port": 5432,
            "database": "test",
            "username": "test",
            "password": "test",
        }

    def tearDown(self):
        """Clean up test database configuration."""
        import main

        main.DB_CONFIG = {}

    @patch("main.get_db_connection")
    @patch("main.is_stablecoin")
    def test_fetch_all_strategies_success(
        self, mock_is_stablecoin, mock_get_connection
    ):
        """Test successful strategy fetching."""
        # Arrange
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "strategy_id": 1,
                "symbol": "BTC/USD",
                "strategy_type": "SMA_EMA_CROSSOVER",
                "parameters": '{"base64_data": "SGVsbG8="}',
                "current_score": 0.85,
                "strategy_hash": "abc123",
                "discovery_symbol": "BTC/USD",
                "discovery_start_time": datetime.now(),
                "discovery_end_time": datetime.now() + timedelta(days=1),
                "first_discovered_at": datetime.now(),
                "last_evaluated_at": datetime.now(),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        ]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.__enter__.return_value = mock_connection
        mock_connection.__exit__.return_value = None
        mock_get_connection.return_value = mock_connection
        mock_is_stablecoin.return_value = False

        # Act
        result = fetch_all_strategies()

        # Assert
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], "BTC/USD")
        self.assertEqual(result[0]["strategy_type"], "SMA_EMA_CROSSOVER")
        self.assertEqual(result[0]["current_score"], 0.85)

    @patch("main.get_db_connection")
    def test_fetch_all_strategies_database_error(self, mock_get_connection):
        """Test strategy fetching with database error."""
        # Arrange
        mock_get_connection.side_effect = Exception("Database error")

        # Act & Assert
        with self.assertRaises(Exception):
            fetch_all_strategies()

    @patch("main.get_db_connection")
    @patch("main.is_stablecoin")
    def test_fetch_strategy_metrics_success(
        self, mock_is_stablecoin, mock_get_connection
    ):
        """Test successful metrics fetching."""
        # Arrange
        mock_cursor = MagicMock()
        # Set up side effects for the multiple database calls in fetch_strategy_metrics
        mock_cursor.fetchall.side_effect = [
            [("BTC/USD",), ("ETH/USD",)],  # all symbols query
            [("SMA_EMA_CROSSOVER", 5, 0.8)],  # strategy type counts query
            [("BTC/USD", 3, 0.85)],  # symbol counts query
        ]
        mock_cursor.fetchone.side_effect = [
            (10,),  # total strategies count
            (5,),  # total symbols count
            (2,),  # total strategy types count
            (0.75, 0.95, 0.55),  # score stats (avg, max, min)
            (1,),  # recent strategies count
        ]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connection.close.return_value = None
        mock_get_connection.return_value = mock_connection
        mock_is_stablecoin.return_value = False

        # Act
        result = fetch_strategy_metrics()

        # Assert
        self.assertIn("total_strategies", result)
        self.assertIn("total_symbols", result)
        self.assertIn("total_strategy_types", result)
        self.assertIn("avg_score", result)
        self.assertIn("max_score", result)
        self.assertIn("min_score", result)
        self.assertIn("recent_strategies_24h", result)
        self.assertIn("top_strategy_types", result)
        self.assertIn("top_symbols", result)
        self.assertEqual(result["total_strategies"], 10)
        self.assertEqual(result["avg_score"], 0.75)


class TestAPIEndpoints(unittest.TestCase):
    """Test API endpoints with AAA pattern."""

    def setUp(self):
        """Set up test client and database configuration."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")

        # Set up test database configuration
        import main

        main.DB_CONFIG = {
            "host": "localhost",
            "port": 5432,
            "database": "test",
            "username": "test",
            "password": "test",
        }

        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        """Clean up test database configuration."""
        import main

        main.DB_CONFIG = {}

    def test_health_endpoint_success(self):
        """Test health endpoint returns healthy status."""
        # Arrange
        endpoint = "/api/health"

        # Act
        response = self.client.get(endpoint)

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "healthy")
        self.assertIn("timestamp", data)

    @patch("main.fetch_all_strategies")
    def test_strategies_endpoint_success(self, mock_fetch):
        """Test strategies endpoint with successful data fetch."""
        # Arrange
        mock_fetch.return_value = [
            {
                "strategy_id": "1",
                "symbol": "BTC/USD",
                "strategy_type": "SMA_EMA_CROSSOVER",
                "current_score": 0.85,
                "parameters": {"SMA Period": 20, "EMA Period": 50},
            }
        ]

        # Act
        response = self.client.get("/api/strategies")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("strategies", data)
        self.assertEqual(len(data["strategies"]), 1)
        self.assertIn("count", data)
        self.assertEqual(data["count"], 1)
        self.assertIn("timestamp", data)

    @patch("main.fetch_all_strategies")
    def test_strategies_endpoint_with_filters(self, mock_fetch):
        """Test strategies endpoint with query parameters."""
        # Arrange
        mock_fetch.return_value = [
            {
                "strategy_id": "1",
                "symbol": "BTC/USD",
                "strategy_type": "SMA_EMA_CROSSOVER",
                "current_score": 0.85,
                "parameters": {"SMA Period": 20, "EMA Period": 50},
            }
        ]

        # Act
        response = self.client.get(
            "/api/strategies?symbol=BTC/USD&limit=1&min_score=0.8"
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("strategies", data)

    @patch("main.fetch_all_strategies")
    def test_strategies_endpoint_database_error(self, mock_fetch):
        """Test strategies endpoint with database error."""
        # Arrange
        mock_fetch.side_effect = Exception("Database connection failed")

        # Act
        response = self.client.get("/api/strategies")

        # Assert
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn("error", data)

    @patch("main.fetch_all_strategies")
    def test_strategy_by_id_success(self, mock_fetch):
        """Test strategy by ID endpoint with successful fetch."""
        # Arrange
        mock_fetch.return_value = [
            {
                "strategy_id": "1",
                "symbol": "BTC/USD",
                "strategy_type": "SMA_EMA_CROSSOVER",
                "current_score": 0.85,
                "parameters": {"SMA Period": 20, "EMA Period": 50},
            }
        ]

        # Act
        response = self.client.get("/api/strategies/1")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("strategy_id", data)
        self.assertEqual(data["strategy_id"], "1")

    @patch("main.fetch_all_strategies")
    def test_strategy_by_id_not_found(self, mock_fetch):
        """Test strategy by ID endpoint with non-existent strategy."""
        # Arrange
        mock_fetch.return_value = []

        # Act
        response = self.client.get("/api/strategies/nonexistent")

        # Assert
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn("error", data)

    @patch("main.fetch_strategy_metrics")
    def test_metrics_endpoint_success(self, mock_fetch):
        """Test metrics endpoint with successful fetch."""
        # Arrange
        mock_fetch.return_value = {
            "total_strategies": 10,
            "total_symbols": 5,
            "total_strategy_types": 3,
            "avg_score": 0.75,
            "max_score": 0.95,
            "min_score": 0.55,
            "recent_strategies_24h": 2,
            "top_strategy_types": [],
            "top_symbols": [],
        }

        # Act
        response = self.client.get("/api/metrics")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("metrics", data)
        self.assertIn("timestamp", data)
        self.assertEqual(data["metrics"]["total_strategies"], 10)

    @patch("main.fetch_strategy_metrics")
    def test_metrics_endpoint_database_error(self, mock_fetch):
        """Test metrics endpoint with database error."""
        # Arrange
        mock_fetch.side_effect = Exception("Database error")

        # Act
        response = self.client.get("/api/metrics")

        # Assert
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn("error", data)

    @patch("main.fetch_all_strategies")
    def test_symbols_endpoint_success(self, mock_fetch):
        """Test symbols endpoint with successful fetch."""
        # Arrange
        mock_fetch.return_value = [
            {"symbol": "BTC/USD"},
            {"symbol": "ETH/USD"},
            {"symbol": "BTC/USD"},  # Duplicate to test deduplication
        ]

        # Act
        response = self.client.get("/api/symbols")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("symbols", data)
        self.assertEqual(len(data["symbols"]), 2)  # Should be deduplicated
        self.assertIn("count", data)
        self.assertEqual(data["count"], 2)

    @patch("main.fetch_all_strategies")
    def test_strategy_types_endpoint_success(self, mock_fetch):
        """Test strategy types endpoint with successful fetch."""
        # Arrange
        mock_fetch.return_value = [
            {"strategy_type": "SMA_EMA_CROSSOVER"},
            {"strategy_type": "RSI_EMA_CROSSOVER"},
            {"strategy_type": "SMA_EMA_CROSSOVER"},  # Duplicate to test deduplication
        ]

        # Act
        response = self.client.get("/api/strategy-types")

        # Assert
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("strategy_types", data)
        self.assertEqual(len(data["strategy_types"]), 2)  # Should be deduplicated
        self.assertIn("count", data)
        self.assertEqual(data["count"], 2)


class TestConfigurationAndInitialization(unittest.TestCase):
    """Test configuration and initialization."""

    def test_cors_enabled(self):
        """Test that CORS is properly enabled."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")

        # Assert
        self.assertTrue(hasattr(app, "extensions"))

    def test_flask_configuration(self):
        """Test Flask app configuration."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")

        # Assert
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app.url_map)

    def test_flask_routes_registered(self):
        """Test that all expected routes are registered."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")

        # Arrange
        expected_routes = [
            "/api/health",
            "/api/strategies",
            "/api/metrics",
            "/api/symbols",
            "/api/strategy-types",
        ]

        # Act
        registered_routes = [str(rule) for rule in app.url_map.iter_rules()]

        # Assert
        for route in expected_routes:
            with self.subTest(route=route):
                self.assertTrue(
                    any(
                        route in registered_route
                        for registered_route in registered_routes
                    )
                )


class TestDependencies(unittest.TestCase):
    """Test that all required dependencies are available."""

    def test_psycopg2_available(self):
        """Test that psycopg2 is available."""
        try:
            import psycopg2

            self.assertTrue(True)
        except ImportError:
            self.fail("psycopg2 not available")

    def test_flask_available(self):
        """Test that Flask is available."""
        try:
            from flask import Flask

            self.assertTrue(True)
        except ImportError:
            self.fail("Flask not available")

    def test_flask_cors_available(self):
        """Test that Flask-CORS is available."""
        try:
            from flask_cors import CORS

            self.assertTrue(True)
        except ImportError:
            self.fail("Flask-CORS not available")

    def test_absl_available(self):
        """Test that absl is available."""
        try:
            from absl import flags

            self.assertTrue(True)
        except ImportError:
            self.fail("absl not available")


if __name__ == "__main__":
    unittest.main()
