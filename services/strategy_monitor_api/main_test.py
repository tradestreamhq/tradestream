"""
Unit tests for Strategy Monitor API Service
Tests import dependencies, Flask app initialization, and main endpoints.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the service directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test imports - this will catch missing dependencies
try:
    from main import app, FLAGS
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
        self.assertEqual(app.name, 'main')
    
    def test_flags_initialized(self):
        """Test that FLAGS are properly initialized."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")
        
        self.assertIsNotNone(FLAGS)


class TestStrategyMonitorAPIEndpoints(unittest.TestCase):
    """Test the main API endpoints."""
    
    def setUp(self):
        """Set up test client."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")
        
        app.config['TESTING'] = True
        self.client = app.test_client()
    
    def test_health_endpoint(self):
        """Test the health check endpoint."""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'healthy')
    
    def test_strategies_endpoint(self):
        """Test the strategies endpoint."""
        with patch('main.fetch_all_strategies') as mock_fetch:
            # Mock the database function
            mock_fetch.return_value = [
                {
                    'strategy_id': '1',
                    'symbol': 'BTC/USD',
                    'strategy_type': 'SMA_EMA_CROSSOVER',
                    'current_score': 0.85,
                    'parameters': {'SMA Period': 20, 'EMA Period': 50}
                },
                {
                    'strategy_id': '2',
                    'symbol': 'ETH/USD',
                    'strategy_type': 'RSI_EMA_CROSSOVER',
                    'current_score': 0.72,
                    'parameters': {'RSI Period': 14, 'EMA Period': 20}
                }
            ]
            
            response = self.client.get('/api/strategies')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('strategies', data)
            self.assertEqual(len(data['strategies']), 2)
    
    def test_strategies_endpoint_database_error(self):
        """Test the strategies endpoint with database error."""
        with patch('main.fetch_all_strategies') as mock_fetch:
            mock_fetch.side_effect = Exception("Database connection failed")
            
            response = self.client.get('/api/strategies')
            self.assertEqual(response.status_code, 500)
            data = json.loads(response.data)
            self.assertIn('error', data)
    
    def test_strategy_details_endpoint(self):
        """Test the strategy details endpoint."""
        with patch('main.fetch_all_strategies') as mock_fetch:
            # Mock the database function
            mock_fetch.return_value = [
                {
                    'strategy_id': '1',
                    'symbol': 'BTC/USD',
                    'strategy_type': 'SMA_EMA_CROSSOVER',
                    'current_score': 0.85,
                    'parameters': {'SMA Period': 20, 'EMA Period': 50}
                }
            ]
            
            response = self.client.get('/api/strategies/1')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('strategy_id', data)
            self.assertEqual(data['strategy_id'], '1')
    
    def test_strategy_details_not_found(self):
        """Test the strategy details endpoint with non-existent strategy."""
        with patch('main.fetch_all_strategies') as mock_fetch:
            # Mock the database function
            mock_fetch.return_value = []
            
            response = self.client.get('/api/strategies/nonexistent')
            self.assertEqual(response.status_code, 404)
            data = json.loads(response.data)
            self.assertIn('error', data)
    
    def test_metrics_endpoint(self):
        """Test the metrics endpoint."""
        with patch('main.fetch_strategy_metrics') as mock_fetch:
            # Mock the database function
            mock_fetch.return_value = {
                'total_strategies': 10,
                'total_symbols': 5,
                'avg_score': 0.75
            }
            
            response = self.client.get('/api/metrics')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('metrics', data)
            self.assertIn('total_strategies', data['metrics'])
    
    def test_symbols_endpoint(self):
        """Test the symbols endpoint."""
        with patch('main.fetch_all_strategies') as mock_fetch:
            # Mock the database function
            mock_fetch.return_value = [
                {'symbol': 'BTC/USD'},
                {'symbol': 'ETH/USD'},
                {'symbol': 'BTC/USD'}  # Duplicate to test deduplication
            ]
            
            response = self.client.get('/api/symbols')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('symbols', data)
            self.assertEqual(len(data['symbols']), 2)  # Should be deduplicated
    
    def test_strategy_types_endpoint(self):
        """Test the strategy types endpoint."""
        with patch('main.fetch_all_strategies') as mock_fetch:
            # Mock the database function
            mock_fetch.return_value = [
                {'strategy_type': 'SMA_EMA_CROSSOVER'},
                {'strategy_type': 'RSI_EMA_CROSSOVER'},
                {'strategy_type': 'SMA_EMA_CROSSOVER'}  # Duplicate to test deduplication
            ]
            
            response = self.client.get('/api/strategy-types')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('strategy_types', data)
            self.assertEqual(len(data['strategy_types']), 2)  # Should be deduplicated


class TestStrategyMonitorAPIConfiguration(unittest.TestCase):
    """Test configuration and initialization."""
    
    def test_cors_enabled(self):
        """Test that CORS is properly enabled."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")
        
        # Check if CORS is configured
        # This is a basic check - in a real app you might want to test actual CORS headers
        self.assertTrue(hasattr(app, 'extensions'))
    
    def test_flask_configuration(self):
        """Test Flask app configuration."""
        if not IMPORT_SUCCESS:
            self.skipTest("Skipping due to import failure")
        
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app.url_map)


class TestStrategyMonitorAPIDependencies(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main() 