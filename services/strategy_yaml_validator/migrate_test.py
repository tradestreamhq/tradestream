"""Tests for the strategy migration scaffold tool."""

import pytest

from services.strategy_yaml_validator.migrate import scaffold_strategy_yaml, _to_snake_case
from services.strategy_yaml_validator.validator import StrategyYamlValidator


class TestToSnakeCase:
    def test_camel_case(self):
        assert _to_snake_case("DoubleEmaCrossover") == "double_ema_crossover"

    def test_upper_case(self):
        assert _to_snake_case("DOUBLE_EMA_CROSSOVER") == "double_ema_crossover"

    def test_single_word(self):
        assert _to_snake_case("Strategy") == "strategy"

    def test_already_snake(self):
        assert _to_snake_case("my_strategy") == "my_strategy"


class TestScaffoldStrategyYaml:
    def test_generates_yaml_string(self):
        result = scaffold_strategy_yaml("DoubleEmaCrossover")
        assert isinstance(result, str)
        assert "DOUBLE_EMA_CROSSOVER" in result

    def test_includes_required_sections(self):
        result = scaffold_strategy_yaml("TestStrategy")
        assert "name:" in result
        assert "version:" in result
        assert "asset_pairs:" in result
        assert "timeframes:" in result
        assert "indicators:" in result
        assert "entry_conditions:" in result
        assert "exit_conditions:" in result
        assert "risk_params:" in result
        assert "parameters:" in result

    def test_upper_case_input(self):
        result = scaffold_strategy_yaml("OBV_EMA")
        assert "OBV_EMA" in result

    def test_scaffold_is_valid_yaml(self):
        import yaml
        result = scaffold_strategy_yaml("TestStrategy")
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)
        assert parsed["name"] == "TEST_STRATEGY"
        assert parsed["version"] == "1.0.0"

    def test_scaffold_has_todo_markers(self):
        result = scaffold_strategy_yaml("TestStrategy")
        assert "TODO" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
