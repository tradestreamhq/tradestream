"""
Tests for strategy_schema.py validation functions.
"""

import pytest
from experiments.llm_validation.strategy_schema import (
    validate_yaml_syntax,
    validate_required_fields,
    validate_indicator,
    validate_condition,
    validate_parameter,
    validate_logic,
    check_novelty,
    validate_strategy,
    ValidationResult,
)


class TestYamlSyntax:
    """Test YAML parsing validation."""

    def test_valid_yaml(self):
        yaml_content = """
name: TEST_STRATEGY
indicators: []
entryConditions: []
exitConditions: []
parameters: []
"""
        is_valid, parsed, errors = validate_yaml_syntax(yaml_content)
        assert is_valid
        assert parsed is not None
        assert len(errors) == 0

    def test_invalid_yaml(self):
        yaml_content = """
name: TEST_STRATEGY
  invalid_indent: here
"""
        is_valid, parsed, errors = validate_yaml_syntax(yaml_content)
        assert not is_valid
        assert parsed is None
        assert len(errors) > 0

    def test_yaml_list_not_dict(self):
        yaml_content = """
- item1
- item2
"""
        is_valid, parsed, errors = validate_yaml_syntax(yaml_content)
        assert not is_valid
        assert "dictionary" in errors[0].lower()


class TestRequiredFields:
    """Test required field validation."""

    def test_all_fields_present(self):
        strategy = {
            "name": "TEST",
            "indicators": [],
            "entryConditions": [],
            "exitConditions": [],
            "parameters": [],
        }
        errors = validate_required_fields(strategy)
        assert len(errors) == 0

    def test_missing_name(self):
        strategy = {
            "indicators": [],
            "entryConditions": [],
            "exitConditions": [],
            "parameters": [],
        }
        errors = validate_required_fields(strategy)
        assert len(errors) == 1
        assert "name" in errors[0]

    def test_missing_multiple_fields(self):
        strategy = {"name": "TEST"}
        errors = validate_required_fields(strategy)
        assert (
            len(errors) == 4
        )  # indicators, entryConditions, exitConditions, parameters


class TestIndicatorValidation:
    """Test indicator validation."""

    def test_valid_indicator(self):
        indicator = {"id": "sma", "type": "SMA", "params": {"period": "${smaPeriod}"}}
        errors = validate_indicator(indicator, 0)
        assert len(errors) == 0

    def test_missing_id(self):
        indicator = {"type": "SMA"}
        errors = validate_indicator(indicator, 0)
        assert len(errors) == 1
        assert "id" in errors[0]

    def test_missing_type(self):
        indicator = {"id": "sma"}
        errors = validate_indicator(indicator, 0)
        assert len(errors) == 1
        assert "type" in errors[0]

    def test_unknown_type(self):
        indicator = {"id": "test", "type": "UNKNOWN_INDICATOR"}
        errors = validate_indicator(indicator, 0)
        assert len(errors) == 1
        assert "unknown type" in errors[0].lower()


class TestConditionValidation:
    """Test condition validation."""

    def test_valid_condition(self):
        condition = {
            "type": "CROSSED_UP",
            "indicator": "sma",
            "params": {"crosses": "ema"},
        }
        indicator_ids = {"sma", "ema"}
        errors = validate_condition(condition, 0, "entryCondition", indicator_ids)
        assert len(errors) == 0

    def test_missing_type(self):
        condition = {"indicator": "sma"}
        errors = validate_condition(condition, 0, "entryCondition", {"sma"})
        assert len(errors) == 1
        assert "type" in errors[0]

    def test_unknown_type(self):
        condition = {"type": "UNKNOWN_CONDITION", "indicator": "sma"}
        errors = validate_condition(condition, 0, "entryCondition", {"sma"})
        assert len(errors) == 1
        assert "unknown type" in errors[0].lower()

    def test_undefined_indicator_reference(self):
        condition = {"type": "CROSSED_UP", "indicator": "undefined"}
        errors = validate_condition(condition, 0, "entryCondition", {"sma", "ema"})
        assert len(errors) == 1
        assert "undefined indicator" in errors[0].lower()

    def test_undefined_crosses_reference(self):
        condition = {
            "type": "CROSSED_UP",
            "indicator": "sma",
            "params": {"crosses": "undefined"},
        }
        errors = validate_condition(condition, 0, "entryCondition", {"sma"})
        assert len(errors) == 1
        assert "undefined indicator" in errors[0].lower()


class TestParameterValidation:
    """Test parameter validation."""

    def test_valid_parameter(self):
        param = {
            "name": "smaPeriod",
            "type": "INTEGER",
            "min": 5,
            "max": 50,
            "defaultValue": 20,
        }
        errors = validate_parameter(param, 0)
        assert len(errors) == 0

    def test_missing_name(self):
        param = {"type": "INTEGER"}
        errors = validate_parameter(param, 0)
        assert len(errors) == 1
        assert "name" in errors[0]

    def test_missing_type(self):
        param = {"name": "smaPeriod"}
        errors = validate_parameter(param, 0)
        assert len(errors) == 1
        assert "type" in errors[0]

    def test_unknown_type(self):
        param = {"name": "test", "type": "STRING"}
        errors = validate_parameter(param, 0)
        assert len(errors) == 1
        assert "unknown type" in errors[0].lower()

    def test_min_greater_than_max(self):
        param = {"name": "test", "type": "INTEGER", "min": 50, "max": 5}
        errors = validate_parameter(param, 0)
        assert len(errors) == 1
        assert "min" in errors[0] and "max" in errors[0]


class TestLogicValidation:
    """Test logical coherence validation."""

    def test_valid_logic(self):
        strategy = {
            "indicators": [{"id": "a"}, {"id": "b"}],
            "entryConditions": [{"type": "CROSSED_UP"}],
            "exitConditions": [{"type": "CROSSED_DOWN"}],
            "parameters": [{"name": "period"}],
        }
        errors = validate_logic(strategy)
        assert len(errors) == 0

    def test_no_indicators(self):
        strategy = {
            "indicators": [],
            "entryConditions": [{"type": "CROSSED_UP"}],
            "exitConditions": [{"type": "CROSSED_DOWN"}],
            "parameters": [],
        }
        errors = validate_logic(strategy)
        assert any("at least 1 indicator" in e.lower() for e in errors)

    def test_single_indicator_valid(self):
        # Single-indicator strategies should be valid
        strategy = {
            "indicators": [{"id": "a"}],
            "entryConditions": [{"type": "CROSSED_UP"}],
            "exitConditions": [{"type": "CROSSED_DOWN"}],
            "parameters": [],
        }
        errors = validate_logic(strategy)
        assert not any("indicator" in e.lower() for e in errors)

    def test_no_entry_conditions(self):
        strategy = {
            "indicators": [{"id": "a"}, {"id": "b"}],
            "entryConditions": [],
            "exitConditions": [{"type": "CROSSED_DOWN"}],
            "parameters": [],
        }
        errors = validate_logic(strategy)
        assert any("entry condition" in e.lower() for e in errors)

    def test_no_exit_conditions(self):
        strategy = {
            "indicators": [{"id": "a"}, {"id": "b"}],
            "entryConditions": [{"type": "CROSSED_UP"}],
            "exitConditions": [],
            "parameters": [],
        }
        errors = validate_logic(strategy)
        assert any("exit condition" in e.lower() for e in errors)

    def test_undefined_parameter_reference(self):
        strategy = {
            "indicators": [
                {"id": "a", "params": {"period": "${undefined}"}},
                {"id": "b"},
            ],
            "entryConditions": [{"type": "CROSSED_UP"}],
            "exitConditions": [{"type": "CROSSED_DOWN"}],
            "parameters": [{"name": "definedParam"}],
        }
        errors = validate_logic(strategy)
        assert any("undefined parameter" in e.lower() for e in errors)


class TestNoveltyCheck:
    """Test novelty checking."""

    def test_novel_strategy(self):
        strategy = {
            "name": "NEW_STRATEGY",
            "indicators": [{"type": "RSI"}, {"type": "ATR"}],
            "entryConditions": [{"type": "OVER_CONSTANT"}],
            "exitConditions": [{"type": "UNDER_CONSTANT"}],
        }
        existing = [
            {
                "name": "OLD_STRATEGY",
                "indicators": [{"type": "SMA"}, {"type": "EMA"}],
                "entryConditions": [{"type": "CROSSED_UP"}],
                "exitConditions": [{"type": "CROSSED_DOWN"}],
            }
        ]
        assert check_novelty(strategy, existing)

    def test_duplicate_name(self):
        strategy = {
            "name": "EXISTING_STRATEGY",
            "indicators": [{"type": "NEW"}],
            "entryConditions": [{"type": "NEW"}],
            "exitConditions": [{"type": "NEW"}],
        }
        existing = [
            {
                "name": "EXISTING_STRATEGY",
                "indicators": [{"type": "OLD"}],
                "entryConditions": [{"type": "OLD"}],
                "exitConditions": [{"type": "OLD"}],
            }
        ]
        assert not check_novelty(strategy, existing)

    def test_same_structure(self):
        strategy = {
            "name": "DIFFERENT_NAME",
            "indicators": [{"type": "SMA"}, {"type": "EMA"}],
            "entryConditions": [{"type": "CROSSED_UP"}],
            "exitConditions": [{"type": "CROSSED_DOWN"}],
        }
        existing = [
            {
                "name": "OLD_STRATEGY",
                "indicators": [{"type": "SMA"}, {"type": "EMA"}],
                "entryConditions": [{"type": "CROSSED_UP"}],
                "exitConditions": [{"type": "CROSSED_DOWN"}],
            }
        ]
        assert not check_novelty(strategy, existing)


class TestFullValidation:
    """Test full strategy validation."""

    def test_valid_strategy(self):
        yaml_content = """
name: VALID_TEST_STRATEGY
description: A valid test strategy
complexity: SIMPLE

indicators:
  - id: sma
    type: SMA
    input: close
    params:
      period: "${smaPeriod}"
  - id: ema
    type: EMA
    input: close
    params:
      period: "${emaPeriod}"

entryConditions:
  - type: CROSSED_UP
    indicator: sma
    params:
      crosses: ema

exitConditions:
  - type: CROSSED_DOWN
    indicator: sma
    params:
      crosses: ema

parameters:
  - name: smaPeriod
    type: INTEGER
    min: 5
    max: 50
    defaultValue: 20
  - name: emaPeriod
    type: INTEGER
    min: 5
    max: 50
    defaultValue: 10
"""
        result = validate_strategy(yaml_content)
        assert result.is_valid
        assert result.syntax_valid
        assert result.logic_valid

    def test_invalid_yaml_syntax(self):
        yaml_content = """
name: INVALID
  bad_indent: here
"""
        result = validate_strategy(yaml_content)
        assert not result.is_valid
        assert not result.syntax_valid

    def test_missing_fields(self):
        yaml_content = """
name: MISSING_FIELDS
description: Missing required fields
"""
        result = validate_strategy(yaml_content)
        assert not result.is_valid
        assert result.syntax_valid  # YAML parses fine
        assert not result.logic_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
