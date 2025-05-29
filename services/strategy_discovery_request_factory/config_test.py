"""Unit tests for config module."""

import unittest
from services.strategy_discovery_request_factory import config


class ConfigTest(unittest.TestCase):
    """Test configuration constants and validation functions."""

    def test_fibonacci_windows_values(self):
        """Test that Fibonacci window values are reasonable."""
        windows = config.FIBONACCI_WINDOWS_MINUTES
        
        # Should have multiple windows
        self.assertGreater(len(windows), 5)
        
        # Should be sorted in ascending order
        self.assertEqual(windows, sorted(windows))
        
        # All values should be positive integers
        for window in windows:
            self.assertIsInstance(window, int)
            self.assertGreater(window, 0)
        
        # Should be reasonable time periods (at least 1 day, less than 1 year)
        min_expected = 1440  # 1 day in minutes
        max_expected = 365 * 24 * 60  # 1 year in minutes
        
        for window in windows:
            self.assertGreaterEqual(window, min_expected)
            self.assertLess(window, max_expected)

    def test_deque_maxlen_sufficient(self):
        """Test that deque max length is sufficient for largest window."""
        max_window = max(config.FIBONACCI_WINDOWS_MINUTES)
        
        self.assertGreater(config.DEQUE_MAXLEN, max_window)
        self.assertIsInstance(config.DEQUE_MAXLEN, int)

    def test_default_parameters(self):
        """Test default parameter values are reasonable."""
        # GA parameters
        self.assertIsInstance(config.DEFAULT_TOP_N, int)
        self.assertGreater(config.DEFAULT_TOP_N, 0)
        self.assertLessEqual(config.DEFAULT_TOP_N, 100)
        
        self.assertIsInstance(config.DEFAULT_MAX_GENERATIONS, int)
        self.assertGreater(config.DEFAULT_MAX_GENERATIONS, 0)
        self.assertLessEqual(config.DEFAULT_MAX_GENERATIONS, 1000)
        
        self.assertIsInstance(config.DEFAULT_POPULATION_SIZE, int)
        self.assertGreater(config.DEFAULT_POPULATION_SIZE, 0)
        self.assertLessEqual(config.DEFAULT_POPULATION_SIZE, 10000)
        
        # Candle granularity
        self.assertIsInstance(config.CANDLE_GRANULARITY_MINUTES, int)
        self.assertGreater(config.CANDLE_GRANULARITY_MINUTES, 0)
        
        # Lookback window
        self.assertIsInstance(config.DEFAULT_LOOKBACK_MINUTES, int)
        self.assertGreater(config.DEFAULT_LOOKBACK_MINUTES, 0)

    def test_validate_fibonacci_windows_valid(self):
        """Test validation with valid Fibonacci windows."""
        valid_windows = [5, 8, 13, 21, 34]
        self.assertTrue(config.validate_fibonacci_windows(valid_windows))

    def test_validate_fibonacci_windows_invalid(self):
        """Test validation with invalid Fibonacci windows."""
        # Empty list
        self.assertFalse(config.validate_fibonacci_windows([]))
        
        # Non-integer values
        self.assertFalse(config.validate_fibonacci_windows([5, 8.5, 13]))
        
        # Too small values
        self.assertFalse(config.validate_fibonacci_windows([1, 2, 3]))
        
        # Too large values
        self.assertFalse(config.validate_fibonacci_windows([600000, 700000]))
        
        # Unsorted
        self.assertFalse(config.validate_fibonacci_windows([13, 8, 21]))

    def test_validate_deque_maxlen_valid(self):
        """Test validation with valid deque maxlen."""
        # Should be larger than max Fibonacci window
        valid_maxlen = max(config.FIBONACCI_WINDOWS_MINUTES) + 100
        self.assertTrue(config.validate_deque_maxlen(valid_maxlen))

    def test_validate_deque_maxlen_invalid(self):
        """Test validation with invalid deque maxlen."""
        # Too small
        self.assertFalse(config.validate_deque_maxlen(50))
        
        # Smaller than max Fibonacci window
        max_window = max(config.FIBONACCI_WINDOWS_MINUTES)
        self.assertFalse(config.validate_deque_maxlen(max_window - 1))
        
        # Too large
        self.assertFalse(config.validate_deque_maxlen(2000000))
        
        # Non-integer
        self.assertFalse(config.validate_deque_maxlen(1000.5))

    def test_validate_ga_parameters_valid(self):
        """Test validation with valid GA parameters."""
        self.assertTrue(config.validate_ga_parameters(30, 50))
        self.assertTrue(config.validate_ga_parameters(1, 1))
        self.assertTrue(config.validate_ga_parameters(1000, 10000))

    def test_validate_ga_parameters_invalid(self):
        """Test validation with invalid GA parameters."""
        # Zero or negative values
        self.assertFalse(config.validate_ga_parameters(0, 50))
        self.assertFalse(config.validate_ga_parameters(30, 0))
        self.assertFalse(config.validate_ga_parameters(-1, 50))
        self.assertFalse(config.validate_ga_parameters(30, -1))
        
        # Too large values
        self.assertFalse(config.validate_ga_parameters(2000, 50))
        self.assertFalse(config.validate_ga_parameters(30, 20000))
        
        # Non-integer values
        self.assertFalse(config.validate_ga_parameters(30.5, 50))
        self.assertFalse(config.validate_ga_parameters(30, 50.5))

    def test_constants_consistency(self):
        """Test that constants are consistent with each other."""
        # Deque maxlen should be validated by its own function
        self.assertTrue(config.validate_deque_maxlen(config.DEQUE_MAXLEN))
        
        # Fibonacci windows should be validated by their function
        self.assertTrue(config.validate_fibonacci_windows(config.FIBONACCI_WINDOWS_MINUTES))
        
        # GA parameters should be validated
        self.assertTrue(config.validate_ga_parameters(
            config.DEFAULT_MAX_GENERATIONS,
            config.DEFAULT_POPULATION_SIZE
        ))

    def test_service_identifier_default(self):
        """Test default service identifier."""
        self.assertIsInstance(config.DEFAULT_SERVICE_IDENTIFIER, str)
        self.assertGreater(len(config.DEFAULT_SERVICE_IDENTIFIER), 0)

    def test_validation_constants(self):
        """Test validation constant values."""
        # Min/max window constants
        self.assertIsInstance(config.MIN_FIBONACCI_WINDOW_MINUTES, int)
        self.assertIsInstance(config.MAX_FIBONACCI_WINDOW_MINUTES, int)
        self.assertGreater(config.MAX_FIBONACCI_WINDOW_MINUTES, config.MIN_FIBONACCI_WINDOW_MINUTES)
        
        # Min/max deque constants
        self.assertIsInstance(config.MIN_DEQUE_MAXLEN, int)
        self.assertIsInstance(config.MAX_DEQUE_MAXLEN, int)
        self.assertGreater(config.MAX_DEQUE_MAXLEN, config.MIN_DEQUE_MAXLEN)


if __name__ == "__main__":
    unittest.main()
