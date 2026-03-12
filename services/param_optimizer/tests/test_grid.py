"""Tests for parameter grid generation."""

import unittest

from services.param_optimizer.grid import ParameterGrid
from services.param_optimizer.models import ParameterRange


class TestParameterGrid(unittest.TestCase):
    def test_single_param(self):
        grid = ParameterGrid([ParameterRange("a", [1, 2, 3])])
        combos = grid.generate()
        self.assertEqual(combos, [{"a": 1}, {"a": 2}, {"a": 3}])
        self.assertEqual(grid.size, 3)

    def test_two_params_cartesian(self):
        grid = ParameterGrid([
            ParameterRange("x", [1, 2]),
            ParameterRange("y", [10, 20]),
        ])
        combos = grid.generate()
        self.assertEqual(len(combos), 4)
        self.assertEqual(grid.size, 4)
        self.assertIn({"x": 1, "y": 10}, combos)
        self.assertIn({"x": 1, "y": 20}, combos)
        self.assertIn({"x": 2, "y": 10}, combos)
        self.assertIn({"x": 2, "y": 20}, combos)

    def test_three_params(self):
        grid = ParameterGrid([
            ParameterRange("a", [1, 2]),
            ParameterRange("b", [3, 4]),
            ParameterRange("c", [5, 6]),
        ])
        self.assertEqual(grid.size, 8)
        self.assertEqual(len(grid.generate()), 8)

    def test_single_value_params(self):
        grid = ParameterGrid([
            ParameterRange("a", [1]),
            ParameterRange("b", [2]),
        ])
        self.assertEqual(grid.generate(), [{"a": 1, "b": 2}])

    def test_param_names(self):
        grid = ParameterGrid([
            ParameterRange("lookback", [10]),
            ParameterRange("threshold", [0.5]),
        ])
        self.assertEqual(grid.param_names, ["lookback", "threshold"])

    def test_empty_ranges_raises(self):
        with self.assertRaises(ValueError):
            ParameterGrid([])

    def test_float_values(self):
        grid = ParameterGrid([ParameterRange("t", [0.5, 1.0, 1.5])])
        self.assertEqual(grid.generate(), [{"t": 0.5}, {"t": 1.0}, {"t": 1.5}])

    def test_large_grid_size(self):
        grid = ParameterGrid([
            ParameterRange("a", list(range(10))),
            ParameterRange("b", list(range(10))),
            ParameterRange("c", list(range(10))),
        ])
        self.assertEqual(grid.size, 1000)


if __name__ == "__main__":
    unittest.main()
