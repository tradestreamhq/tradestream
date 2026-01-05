"""Unit tests for strategy_registry module."""

import os
import unittest
from unittest import mock

from services.strategy_discovery_request_factory.strategy_registry import (
    get_supported_strategy_names,
    _DEFAULT_STRATEGY_NAMES,
)


class StrategyRegistryTest(unittest.TestCase):
    """Test strategy registry functionality."""

    def test_default_strategy_names_when_env_not_set(self):
        """Test that default strategy names are returned when env var is not set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            # Ensure STRATEGY_NAMES is not set
            os.environ.pop("STRATEGY_NAMES", None)
            names = get_supported_strategy_names()

        self.assertEqual(names, _DEFAULT_STRATEGY_NAMES)

    def test_env_var_overrides_defaults(self):
        """Test that STRATEGY_NAMES env var overrides default values."""
        env_value = "CUSTOM_STRATEGY_1,CUSTOM_STRATEGY_2,CUSTOM_STRATEGY_3"
        with mock.patch.dict(os.environ, {"STRATEGY_NAMES": env_value}):
            names = get_supported_strategy_names()

        self.assertEqual(
            names, ["CUSTOM_STRATEGY_1", "CUSTOM_STRATEGY_2", "CUSTOM_STRATEGY_3"]
        )

    def test_env_var_strips_whitespace(self):
        """Test that whitespace is stripped from strategy names."""
        env_value = "  STRATEGY_1  ,  STRATEGY_2  ,STRATEGY_3  "
        with mock.patch.dict(os.environ, {"STRATEGY_NAMES": env_value}):
            names = get_supported_strategy_names()

        self.assertEqual(names, ["STRATEGY_1", "STRATEGY_2", "STRATEGY_3"])

    def test_env_var_filters_empty_strings(self):
        """Test that empty strings are filtered out."""
        env_value = "STRATEGY_1,,STRATEGY_2,  ,STRATEGY_3"
        with mock.patch.dict(os.environ, {"STRATEGY_NAMES": env_value}):
            names = get_supported_strategy_names()

        self.assertEqual(names, ["STRATEGY_1", "STRATEGY_2", "STRATEGY_3"])

    def test_empty_env_var_returns_defaults(self):
        """Test that empty env var returns default values."""
        with mock.patch.dict(os.environ, {"STRATEGY_NAMES": ""}):
            names = get_supported_strategy_names()

        self.assertEqual(names, _DEFAULT_STRATEGY_NAMES)

    def test_single_strategy_in_env_var(self):
        """Test that single strategy name works."""
        with mock.patch.dict(os.environ, {"STRATEGY_NAMES": "SINGLE_STRATEGY"}):
            names = get_supported_strategy_names()

        self.assertEqual(names, ["SINGLE_STRATEGY"])

    def test_returns_copy_of_defaults(self):
        """Test that modifying returned list doesn't affect defaults."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("STRATEGY_NAMES", None)
            names = get_supported_strategy_names()
            original_defaults = _DEFAULT_STRATEGY_NAMES.copy()

            # Modify the returned list
            names.append("NEW_STRATEGY")

        # Verify defaults are unchanged
        self.assertEqual(_DEFAULT_STRATEGY_NAMES, original_defaults)

    def test_default_includes_expected_strategies(self):
        """Test that defaults include expected strategy types."""
        # Verify defaults contain known strategy types
        self.assertIn("MACD_CROSSOVER", _DEFAULT_STRATEGY_NAMES)
        self.assertIn("SMA_RSI", _DEFAULT_STRATEGY_NAMES)


if __name__ == "__main__":
    unittest.main()
