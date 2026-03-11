"""Tests for shared.config module."""

import os
import unittest
from unittest import mock

from shared.config import require_env, validate_env_vars


class RequireEnvTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {"MY_VAR": "my_value"})
    def test_returns_value_when_set(self):
        self.assertEqual(require_env("MY_VAR"), "my_value")

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_exits_when_missing(self):
        with self.assertRaises(SystemExit):
            require_env("MISSING_VAR")

    @mock.patch.dict(os.environ, {"EMPTY_VAR": ""})
    def test_exits_when_empty(self):
        with self.assertRaises(SystemExit):
            require_env("EMPTY_VAR")


class ValidateEnvVarsTest(unittest.TestCase):
    @mock.patch.dict(os.environ, {"A": "1", "B": "2"})
    def test_passes_when_all_set(self):
        validate_env_vars(["A", "B"])  # Should not raise

    @mock.patch.dict(os.environ, {"A": "1"}, clear=True)
    def test_exits_when_some_missing(self):
        with self.assertRaises(SystemExit):
            validate_env_vars(["A", "B"])

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_exits_when_all_missing(self):
        with self.assertRaises(SystemExit):
            validate_env_vars(["X", "Y"])

    def test_passes_with_empty_list(self):
        validate_env_vars([])  # Should not raise


if __name__ == "__main__":
    unittest.main()
