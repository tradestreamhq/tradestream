"""
Strategy YAML Validator for TradeStream.

Validates YAML strategy definitions against a JSON Schema and performs
cross-field consistency checks.
"""

import re
from dataclasses import dataclass, field
from typing import Any

import jsonschema
import yaml

from services.strategy_yaml_validator.schema import STRATEGY_SCHEMA, VALID_TIMEFRAMES


@dataclass
class ValidationError:
    """A single validation error with location info."""

    message: str
    path: str = ""
    line: int | None = None

    def __str__(self) -> str:
        parts = []
        if self.line is not None:
            parts.append(f"line {self.line}")
        if self.path:
            parts.append(self.path)
        parts.append(self.message)
        return ": ".join(parts)


@dataclass
class ValidationResult:
    """Result of strategy YAML validation."""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def success(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def failure(cls, errors: list[ValidationError]) -> "ValidationResult":
        return cls(is_valid=False, errors=errors)


def _find_line_number(yaml_content: str, path: list[str | int]) -> int | None:
    """Best-effort line number lookup for a JSON path in YAML content."""
    lines = yaml_content.splitlines()
    if not path:
        return None

    # Try to find the top-level key
    key = str(path[0])
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if stripped.startswith(f"{key}:") or stripped.startswith(f"- {key}:"):
            return i
    return None


class StrategyYamlValidator:
    """Validates strategy YAML files against schema and cross-field rules."""

    def __init__(self, schema: dict[str, Any] | None = None):
        self.schema = schema or STRATEGY_SCHEMA

    def validate(self, yaml_content: str) -> ValidationResult:
        """
        Validate a YAML strategy string.

        Returns a ValidationResult with structured errors including line numbers.
        """
        errors: list[ValidationError] = []

        # Step 1: Parse YAML
        try:
            strategy = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            line = None
            if hasattr(e, "problem_mark") and e.problem_mark is not None:
                line = e.problem_mark.line + 1
            errors.append(ValidationError(
                message=f"YAML parse error: {e}",
                line=line,
            ))
            return ValidationResult.failure(errors)

        if not isinstance(strategy, dict):
            errors.append(ValidationError(
                message="YAML must parse to a mapping, not a list or scalar",
            ))
            return ValidationResult.failure(errors)

        # Step 2: JSON Schema validation
        validator = jsonschema.Draft202012Validator(self.schema)
        for error in sorted(validator.iter_errors(strategy), key=lambda e: list(e.path)):
            path_str = ".".join(str(p) for p in error.absolute_path)
            line = _find_line_number(yaml_content, list(error.absolute_path))
            errors.append(ValidationError(
                message=error.message,
                path=path_str,
                line=line,
            ))

        # Step 3: Cross-field consistency checks
        errors.extend(self._check_cross_field(strategy, yaml_content))

        if errors:
            return ValidationResult.failure(errors)
        return ValidationResult.success()

    def validate_file(self, filepath: str) -> ValidationResult:
        """Validate a strategy YAML file by path."""
        with open(filepath) as f:
            return self.validate(f.read())

    def _check_cross_field(
        self, strategy: dict[str, Any], yaml_content: str
    ) -> list[ValidationError]:
        """Check cross-field consistency."""
        errors: list[ValidationError] = []

        # Collect indicator IDs
        indicator_ids: set[str] = set()
        for ind in strategy.get("indicators", []):
            if "id" in ind:
                indicator_ids.add(ind["id"])

        # Check that entry/exit conditions reference defined indicators
        for section in ("entry_conditions", "exit_conditions"):
            for idx, cond in enumerate(strategy.get(section, [])):
                ind_ref = cond.get("indicator")
                if ind_ref and ind_ref not in indicator_ids:
                    line = _find_line_number(yaml_content, [section])
                    errors.append(ValidationError(
                        message=f"references undefined indicator '{ind_ref}'",
                        path=f"{section}.{idx}.indicator",
                        line=line,
                    ))

                # Check crosses references in params
                params = cond.get("params", {})
                if isinstance(params, dict):
                    crosses = params.get("crosses")
                    if crosses and crosses not in indicator_ids:
                        errors.append(ValidationError(
                            message=f"'crosses' references undefined indicator '{crosses}'",
                            path=f"{section}.{idx}.params.crosses",
                            line=_find_line_number(yaml_content, [section]),
                        ))

        # Check parameter references in indicator params
        param_names: set[str] = set()
        for p in strategy.get("parameters", []):
            if "name" in p:
                param_names.add(p["name"])

        for idx, ind in enumerate(strategy.get("indicators", [])):
            params = ind.get("params", {})
            if isinstance(params, dict):
                for key, value in params.items():
                    if isinstance(value, str) and re.fullmatch(r"\$\{\w+\}", value):
                        param_ref = value[2:-1]
                        if param_ref not in param_names:
                            errors.append(ValidationError(
                                message=f"references undefined parameter '{param_ref}'",
                                path=f"indicators.{idx}.params.{key}",
                                line=_find_line_number(yaml_content, ["indicators"]),
                            ))

        # Check risk_params consistency
        risk = strategy.get("risk_params", {})
        if isinstance(risk, dict):
            stop_loss = risk.get("stop_loss_pct")
            take_profit = risk.get("take_profit_pct")
            if (
                stop_loss is not None
                and take_profit is not None
                and take_profit <= stop_loss
            ):
                errors.append(ValidationError(
                    message="take_profit_pct should be greater than stop_loss_pct",
                    path="risk_params",
                    line=_find_line_number(yaml_content, ["risk_params"]),
                ))

        return errors
