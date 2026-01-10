"""
Strategy YAML Schema Definition and Validation.

This module defines the schema for TradeStream strategy YAML files and provides
validation functions to check if LLM-generated strategies are syntactically valid
and logically coherent.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import yaml


class IndicatorType(Enum):
    """Supported indicator types in TradeStream."""

    # Moving Averages
    SMA = "SMA"
    EMA = "EMA"
    DEMA = "DEMA"
    TEMA = "TEMA"

    # Oscillators
    RSI = "RSI"
    STOCHASTIC_K = "STOCHASTIC_K"
    CMO = "CMO"
    WILLIAMS_R = "WILLIAMS_R"
    CCI = "CCI"
    ROC = "ROC"
    MACD = "MACD"
    AWESOME_OSCILLATOR = "AWESOME_OSCILLATOR"
    CHAIKIN_OSCILLATOR = "CHAIKIN_OSCILLATOR"

    # Volume
    OBV = "OBV"
    CMF = "CMF"
    MFI = "MFI"
    KLINGER_VOLUME_OSCILLATOR = "KLINGER_VOLUME_OSCILLATOR"

    # Trend
    ADX = "ADX"
    PLUS_DI = "PLUS_DI"
    MINUS_DI = "MINUS_DI"
    AROON_UP = "AROON_UP"
    AROON_DOWN = "AROON_DOWN"
    MASS_INDEX = "MASS_INDEX"

    # Volatility
    ATR = "ATR"
    BOLLINGER_UPPER = "BOLLINGER_UPPER"
    BOLLINGER_LOWER = "BOLLINGER_LOWER"

    # Price
    CLOSE_PRICE = "CLOSE_PRICE"
    HIGH_PRICE = "HIGH_PRICE"
    LOW_PRICE = "LOW_PRICE"
    HIGHEST_HIGH = "HIGHEST_HIGH"
    LOWEST_LOW = "LOWEST_LOW"

    # Utility
    CONSTANT = "CONSTANT"
    DIFFERENCE = "DIFFERENCE"
    PREVIOUS = "PREVIOUS"


class ConditionType(Enum):
    """Supported condition types in TradeStream."""

    # Crossovers
    CROSSED_UP = "CROSSED_UP"
    CROSSED_DOWN = "CROSSED_DOWN"
    CROSSED_UP_CONSTANT = "CROSSED_UP_CONSTANT"
    CROSSED_DOWN_CONSTANT = "CROSSED_DOWN_CONSTANT"
    CROSSES_ABOVE = "CROSSES_ABOVE"
    CROSSES_BELOW = "CROSSES_BELOW"

    # Comparisons
    OVER_CONSTANT = "OVER_CONSTANT"
    UNDER_CONSTANT = "UNDER_CONSTANT"
    OVER_INDICATOR = "OVER_INDICATOR"
    UNDER_INDICATOR = "UNDER_INDICATOR"
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    OVER = "OVER"
    UNDER = "UNDER"


class ParameterType(Enum):
    """Supported parameter types."""

    INTEGER = "INTEGER"
    DOUBLE = "DOUBLE"


class Complexity(Enum):
    """Strategy complexity levels."""

    SIMPLE = "SIMPLE"
    MEDIUM = "MEDIUM"
    COMPLEX = "COMPLEX"


@dataclass
class ValidationResult:
    """Result of strategy validation."""

    is_valid: bool
    syntax_valid: bool = True
    logic_valid: bool = True
    is_novel: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def success(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def failure(
        cls, errors: list[str], syntax_valid: bool = False, logic_valid: bool = False
    ) -> "ValidationResult":
        return cls(
            is_valid=False,
            syntax_valid=syntax_valid,
            logic_valid=logic_valid,
            errors=errors,
        )


def validate_yaml_syntax(
    yaml_content: str,
) -> tuple[bool, dict[str, Any] | None, list[str]]:
    """
    Validate that the content is valid YAML and can be parsed.

    Returns:
        tuple of (is_valid, parsed_dict, errors)
    """
    errors = []
    try:
        parsed = yaml.safe_load(yaml_content)
        if not isinstance(parsed, dict):
            errors.append("YAML must parse to a dictionary, not a list or scalar")
            return False, None, errors
        return True, parsed, []
    except yaml.YAMLError as e:
        errors.append(f"YAML parse error: {e}")
        return False, None, errors


def validate_required_fields(strategy: dict[str, Any]) -> list[str]:
    """Check that all required top-level fields are present."""
    required = ["name", "indicators", "entryConditions", "exitConditions", "parameters"]
    errors = []

    for field_name in required:
        if field_name not in strategy:
            errors.append(f"Missing required field: {field_name}")

    return errors


def validate_indicator(indicator: dict[str, Any], idx: int) -> list[str]:
    """Validate a single indicator definition."""
    errors = []

    # Check required fields
    if "id" not in indicator:
        errors.append(f"Indicator {idx}: missing 'id' field")
    if "type" not in indicator:
        errors.append(f"Indicator {idx}: missing 'type' field")
    else:
        # Validate indicator type
        ind_type = indicator["type"]
        try:
            IndicatorType(ind_type)
        except ValueError:
            errors.append(f"Indicator {idx}: unknown type '{ind_type}'")

    return errors


def validate_condition(
    condition: dict[str, Any], idx: int, condition_type: str, indicator_ids: set[str]
) -> list[str]:
    """Validate a single condition (entry or exit)."""
    errors = []

    if "type" not in condition:
        errors.append(f"{condition_type} {idx}: missing 'type' field")
    else:
        cond_type = condition["type"]
        try:
            ConditionType(cond_type)
        except ValueError:
            errors.append(f"{condition_type} {idx}: unknown type '{cond_type}'")

    # Check indicator references
    if "indicator" in condition:
        ind_ref = condition["indicator"]
        if ind_ref not in indicator_ids:
            errors.append(
                f"{condition_type} {idx}: references undefined indicator '{ind_ref}'"
            )

    # Check 'crosses' references in params
    if "params" in condition and isinstance(condition["params"], dict):
        if "crosses" in condition["params"]:
            crosses_ref = condition["params"]["crosses"]
            if crosses_ref not in indicator_ids:
                errors.append(
                    f"{condition_type} {idx}: 'crosses' references undefined indicator '{crosses_ref}'"
                )

    return errors


def validate_parameter(param: dict[str, Any], idx: int) -> list[str]:
    """Validate a single parameter definition."""
    errors = []

    if "name" not in param:
        errors.append(f"Parameter {idx}: missing 'name' field")
    if "type" not in param:
        errors.append(f"Parameter {idx}: missing 'type' field")
    else:
        try:
            ParameterType(param["type"])
        except ValueError:
            errors.append(f"Parameter {idx}: unknown type '{param['type']}'")

    # Validate min/max/default for numeric types
    if "min" in param and "max" in param:
        if param["min"] > param["max"]:
            errors.append(
                f"Parameter {idx}: min ({param['min']}) > max ({param['max']})"
            )

    return errors


def validate_logic(strategy: dict[str, Any]) -> list[str]:
    """
    Validate logical coherence of the strategy.
    - At least one entry and one exit condition
    - At least 1 indicator (single-indicator strategies are valid)
    - Parameter references in indicators resolve
    """
    errors = []

    # Check indicator count (single-indicator strategies are valid)
    indicators = strategy.get("indicators", [])
    if len(indicators) < 1:
        errors.append("Strategy must have at least 1 indicator")

    # Check condition counts
    entry_conditions = strategy.get("entryConditions", [])
    exit_conditions = strategy.get("exitConditions", [])

    if len(entry_conditions) < 1:
        errors.append("Strategy must have at least 1 entry condition")
    if len(exit_conditions) < 1:
        errors.append("Strategy must have at least 1 exit condition")

    # Check parameter references in indicators
    param_names = {p.get("name") for p in strategy.get("parameters", []) if "name" in p}

    for idx, ind in enumerate(indicators):
        if "params" in ind and isinstance(ind["params"], dict):
            for key, value in ind["params"].items():
                if (
                    isinstance(value, str)
                    and value.startswith("${")
                    and value.endswith("}")
                ):
                    param_ref = value[2:-1]  # Extract parameter name from ${name}
                    if param_ref not in param_names:
                        errors.append(
                            f"Indicator {idx}: references undefined parameter '{param_ref}'"
                        )

    return errors


def check_novelty(
    strategy: dict[str, Any], existing_strategies: list[dict[str, Any]]
) -> bool:
    """
    Check if the strategy is novel (not a direct copy of existing strategies).

    A strategy is considered non-novel if:
    - Same name as an existing strategy
    - Same indicator types in same order
    - Same condition types in same order
    """
    strategy_name = strategy.get("name", "").upper()
    strategy_indicator_types = [
        ind.get("type") for ind in strategy.get("indicators", [])
    ]
    strategy_entry_types = [
        cond.get("type") for cond in strategy.get("entryConditions", [])
    ]
    strategy_exit_types = [
        cond.get("type") for cond in strategy.get("exitConditions", [])
    ]

    for existing in existing_strategies:
        # Check name similarity
        existing_name = existing.get("name", "").upper()
        if strategy_name == existing_name:
            return False

        # Check structural similarity
        existing_ind_types = [ind.get("type") for ind in existing.get("indicators", [])]
        existing_entry_types = [
            cond.get("type") for cond in existing.get("entryConditions", [])
        ]
        existing_exit_types = [
            cond.get("type") for cond in existing.get("exitConditions", [])
        ]

        if (
            strategy_indicator_types == existing_ind_types
            and strategy_entry_types == existing_entry_types
            and strategy_exit_types == existing_exit_types
        ):
            return False

    return True


def validate_strategy(
    yaml_content: str, existing_strategies: list[dict[str, Any]] | None = None
) -> ValidationResult:
    """
    Fully validate a strategy YAML.

    Args:
        yaml_content: The YAML content to validate
        existing_strategies: List of existing strategies to check novelty against

    Returns:
        ValidationResult with detailed validation outcome
    """
    all_errors = []

    # Step 1: Parse YAML
    syntax_valid, strategy, parse_errors = validate_yaml_syntax(yaml_content)
    if not syntax_valid:
        return ValidationResult.failure(
            parse_errors, syntax_valid=False, logic_valid=False
        )

    # Step 2: Check required fields
    field_errors = validate_required_fields(strategy)
    all_errors.extend(field_errors)

    if field_errors:
        return ValidationResult.failure(
            all_errors, syntax_valid=True, logic_valid=False
        )

    # Step 3: Validate indicators
    indicator_ids = set()
    for idx, ind in enumerate(strategy.get("indicators", [])):
        ind_errors = validate_indicator(ind, idx)
        all_errors.extend(ind_errors)
        if "id" in ind:
            indicator_ids.add(ind["id"])

    # Step 4: Validate conditions
    for idx, cond in enumerate(strategy.get("entryConditions", [])):
        cond_errors = validate_condition(cond, idx, "entryCondition", indicator_ids)
        all_errors.extend(cond_errors)

    for idx, cond in enumerate(strategy.get("exitConditions", [])):
        cond_errors = validate_condition(cond, idx, "exitCondition", indicator_ids)
        all_errors.extend(cond_errors)

    # Step 5: Validate parameters
    for idx, param in enumerate(strategy.get("parameters", [])):
        param_errors = validate_parameter(param, idx)
        all_errors.extend(param_errors)

    syntax_valid = len(all_errors) == 0

    # Step 6: Validate logic
    logic_errors = validate_logic(strategy)
    all_errors.extend(logic_errors)

    logic_valid = len(logic_errors) == 0

    # Step 7: Check novelty
    is_novel = True
    if existing_strategies:
        is_novel = check_novelty(strategy, existing_strategies)

    if all_errors:
        result = ValidationResult.failure(
            all_errors, syntax_valid=syntax_valid, logic_valid=logic_valid
        )
        result.is_novel = is_novel
        return result

    result = ValidationResult.success()
    result.is_novel = is_novel
    return result


def load_existing_strategies(directory: str) -> list[dict[str, Any]]:
    """Load all existing strategy YAML files from a directory."""
    import os

    strategies = []
    for filename in os.listdir(directory):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(directory, filename)
            with open(filepath) as f:
                try:
                    strategy = yaml.safe_load(f)
                    if isinstance(strategy, dict):
                        strategies.append(strategy)
                except yaml.YAMLError:
                    continue
    return strategies
