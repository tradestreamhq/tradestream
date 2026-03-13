"""Tests for the Strategy YAML Validator."""

import pytest

from services.strategy_yaml_validator.validator import (
    StrategyYamlValidator,
    ValidationError,
    ValidationResult,
)


VALID_STRATEGY = """\
name: TEST_EMA_CROSSOVER
version: "1.0.0"
description: Test EMA crossover strategy

asset_pairs:
  - BTC/USD
  - ETH/USD

timeframes:
  - 1h
  - 4h

indicators:
  - id: shortEma
    type: EMA
    input: close
    params:
      period: "${shortPeriod}"
  - id: longEma
    type: EMA
    input: close
    params:
      period: "${longPeriod}"

entry_conditions:
  - type: CROSSED_UP
    indicator: shortEma
    params:
      crosses: longEma

exit_conditions:
  - type: CROSSED_DOWN
    indicator: shortEma
    params:
      crosses: longEma

parameters:
  - name: shortPeriod
    type: INTEGER
    min: 5
    max: 20
    defaultValue: 10
  - name: longPeriod
    type: INTEGER
    min: 20
    max: 50
    defaultValue: 30

risk_params:
  max_position_pct: 10.0
  stop_loss_pct: 2.0
  take_profit_pct: 6.0
"""


class TestValidStrategy:
    def test_valid_strategy_passes(self):
        validator = StrategyYamlValidator()
        result = validator.validate(VALID_STRATEGY)
        assert result.is_valid
        assert len(result.errors) == 0


class TestYamlParseErrors:
    def test_invalid_yaml_syntax(self):
        validator = StrategyYamlValidator()
        result = validator.validate("name: test\n  bad_indent: here\n")
        assert not result.is_valid
        assert any("parse error" in str(e).lower() for e in result.errors)

    def test_yaml_list_instead_of_dict(self):
        validator = StrategyYamlValidator()
        result = validator.validate("- item1\n- item2\n")
        assert not result.is_valid
        assert any("mapping" in str(e).lower() for e in result.errors)


class TestRequiredFields:
    def test_missing_name(self):
        yaml_content = VALID_STRATEGY.replace("name: TEST_EMA_CROSSOVER\n", "")
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("name" in str(e).lower() for e in result.errors)

    def test_missing_version(self):
        yaml_content = VALID_STRATEGY.replace('version: "1.0.0"\n', "")
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("version" in str(e).lower() for e in result.errors)

    def test_missing_asset_pairs(self):
        # Remove asset_pairs section
        lines = VALID_STRATEGY.splitlines(keepends=True)
        filtered = []
        skip = False
        for line in lines:
            if line.startswith("asset_pairs:"):
                skip = True
                continue
            if skip and (line.startswith("  - ") or line.strip() == ""):
                if line.strip() == "":
                    skip = False
                continue
            skip = False
            filtered.append(line)
        yaml_content = "".join(filtered)
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("asset_pairs" in str(e) for e in result.errors)

    def test_missing_risk_params(self):
        # Remove risk_params section
        lines = VALID_STRATEGY.splitlines(keepends=True)
        idx = None
        for i, line in enumerate(lines):
            if line.startswith("risk_params:"):
                idx = i
                break
        if idx is not None:
            yaml_content = "".join(lines[:idx])
        else:
            yaml_content = VALID_STRATEGY
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("risk_params" in str(e) for e in result.errors)


class TestInvalidVersion:
    def test_bad_version_format(self):
        yaml_content = VALID_STRATEGY.replace('version: "1.0.0"', 'version: "v1"')
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid

    def test_valid_semver(self):
        yaml_content = VALID_STRATEGY.replace('version: "1.0.0"', 'version: "2.1.3"')
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert result.is_valid


class TestAssetPairs:
    def test_invalid_asset_pair_format(self):
        yaml_content = VALID_STRATEGY.replace("  - BTC/USD\n  - ETH/USD", "  - btcusd")
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid

    def test_empty_asset_pairs(self):
        yaml_content = VALID_STRATEGY.replace(
            "asset_pairs:\n  - BTC/USD\n  - ETH/USD",
            "asset_pairs: []",
        )
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid


class TestTimeframes:
    def test_invalid_timeframe(self):
        yaml_content = VALID_STRATEGY.replace("  - 1h\n  - 4h", "  - 7h")
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid

    def test_empty_timeframes(self):
        yaml_content = VALID_STRATEGY.replace(
            "timeframes:\n  - 1h\n  - 4h",
            "timeframes: []",
        )
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid


class TestCrossFieldConsistency:
    def test_undefined_indicator_in_entry(self):
        yaml_content = VALID_STRATEGY.replace(
            "indicator: shortEma\n    params:\n      crosses: longEma\n\nexit",
            "indicator: nonexistent\n    params:\n      crosses: longEma\n\nexit",
        )
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("undefined indicator" in str(e).lower() for e in result.errors)

    def test_undefined_crosses_ref(self):
        yaml_content = VALID_STRATEGY.replace(
            "crosses: longEma\n\nexit",
            "crosses: nonexistent\n\nexit",
        )
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("undefined indicator" in str(e).lower() for e in result.errors)

    def test_undefined_parameter_ref(self):
        yaml_content = VALID_STRATEGY.replace("${shortPeriod}", "${undefinedParam}")
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("undefined parameter" in str(e).lower() for e in result.errors)

    def test_take_profit_less_than_stop_loss(self):
        yaml_content = VALID_STRATEGY.replace(
            "stop_loss_pct: 2.0\n  take_profit_pct: 6.0",
            "stop_loss_pct: 10.0\n  take_profit_pct: 5.0",
        )
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("take_profit" in str(e).lower() for e in result.errors)


class TestRiskParams:
    def test_missing_max_position_pct(self):
        yaml_content = VALID_STRATEGY.replace(
            "risk_params:\n  max_position_pct: 10.0\n  stop_loss_pct: 2.0\n  take_profit_pct: 6.0",
            "risk_params:\n  stop_loss_pct: 2.0\n  take_profit_pct: 6.0",
        )
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid
        assert any("max_position_pct" in str(e) for e in result.errors)

    def test_position_pct_out_of_range(self):
        yaml_content = VALID_STRATEGY.replace(
            "max_position_pct: 10.0", "max_position_pct: 150.0"
        )
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid


class TestIndicatorTypes:
    def test_unknown_indicator_type(self):
        yaml_content = VALID_STRATEGY.replace("type: EMA", "type: UNKNOWN_IND")
        validator = StrategyYamlValidator()
        result = validator.validate(yaml_content)
        assert not result.is_valid


class TestValidationResult:
    def test_success_factory(self):
        result = ValidationResult.success()
        assert result.is_valid
        assert len(result.errors) == 0

    def test_failure_factory(self):
        errs = [ValidationError(message="test error", path="foo", line=1)]
        result = ValidationResult.failure(errs)
        assert not result.is_valid
        assert len(result.errors) == 1

    def test_error_str_with_line(self):
        err = ValidationError(message="bad value", path="name", line=5)
        assert "line 5" in str(err)
        assert "name" in str(err)
        assert "bad value" in str(err)

    def test_error_str_without_line(self):
        err = ValidationError(message="missing field")
        assert "missing field" in str(err)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
