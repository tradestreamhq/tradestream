"""
YAML Strategy Loader for VectorBT Backtesting.

Reads YAML strategy definitions and generates entry/exit signals
for use with the VectorBT backtesting runner.
"""

import os
import re
from typing import Any, Dict, List, Tuple

import pandas as pd
import yaml

from services.backtesting.indicator_registry import (
    IndicatorRegistry,
    get_default_registry,
)


class YamlStrategyLoader:
    """Loads YAML strategy specs and generates trading signals."""

    def __init__(self, indicator_registry: IndicatorRegistry | None = None):
        self.registry = indicator_registry or get_default_registry()

    def load_strategy(self, yaml_path: str) -> Dict[str, Any]:
        """Load a strategy definition from a YAML file."""
        with open(yaml_path, "r") as f:
            return yaml.safe_load(f)

    def generate_signals(
        self,
        ohlcv: pd.DataFrame,
        strategy_spec: Dict[str, Any],
        parameter_overrides: Dict[str, Any] | None = None,
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Generate entry/exit signals from a YAML strategy spec.

        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume]
            strategy_spec: Parsed YAML strategy definition
            parameter_overrides: Optional parameter values to override defaults

        Returns:
            Tuple of (entry_signals, exit_signals) as boolean Series
        """
        # Resolve parameters (use overrides or defaults)
        params = self._resolve_parameters(strategy_spec, parameter_overrides)

        # Compute all indicators
        indicators = self._compute_indicators(ohlcv, strategy_spec, params)

        # Evaluate entry conditions
        entry_signals = self._evaluate_conditions(
            ohlcv, strategy_spec.get("entryConditions", []), indicators, params
        )

        # Evaluate exit conditions
        exit_signals = self._evaluate_conditions(
            ohlcv, strategy_spec.get("exitConditions", []), indicators, params
        )

        return entry_signals, exit_signals

    def _resolve_parameters(
        self,
        strategy_spec: Dict[str, Any],
        overrides: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        """Resolve parameter values from defaults and overrides."""
        params = {}
        for param_def in strategy_spec.get("parameters", []):
            name = param_def["name"]
            default = param_def.get("defaultValue")
            if overrides and name in overrides:
                params[name] = overrides[name]
            elif default is not None:
                params[name] = default
        return params

    def _substitute_param(self, value: Any, params: Dict[str, Any]) -> Any:
        """Substitute ${paramName} placeholders with actual values."""
        if not isinstance(value, str):
            return value
        match = re.fullmatch(r"\$\{(\w+)\}", value)
        if match:
            param_name = match.group(1)
            return params.get(param_name, value)
        return value

    def _compute_indicators(
        self,
        ohlcv: pd.DataFrame,
        strategy_spec: Dict[str, Any],
        params: Dict[str, Any],
    ) -> Dict[str, pd.Series]:
        """Compute all indicators defined in the strategy spec."""
        indicators = {}
        close = ohlcv["close"]

        for ind_def in strategy_spec.get("indicators", []):
            ind_id = ind_def["id"]
            ind_type = ind_def["type"]

            # Resolve indicator parameters
            ind_params = {}
            for key, val in ind_def.get("params", {}).items():
                ind_params[key] = self._substitute_param(val, params)

            indicators[ind_id] = self.registry.create(
                ind_type, close, ohlcv, ind_params
            )

        return indicators

    def _evaluate_conditions(
        self,
        ohlcv: pd.DataFrame,
        conditions: List[Dict[str, Any]],
        indicators: Dict[str, pd.Series],
        params: Dict[str, Any],
    ) -> pd.Series:
        """Evaluate a list of conditions and combine with AND logic."""
        if not conditions:
            return pd.Series(False, index=ohlcv.index)

        result = pd.Series(True, index=ohlcv.index)
        for cond in conditions:
            signal = self._evaluate_single_condition(ohlcv, cond, indicators, params)
            result = result & signal

        return result

    def _evaluate_single_condition(
        self,
        ohlcv: pd.DataFrame,
        condition: Dict[str, Any],
        indicators: Dict[str, pd.Series],
        params: Dict[str, Any],
    ) -> pd.Series:
        """Evaluate a single entry/exit condition."""
        cond_type = condition["type"]
        indicator_id = condition["indicator"]
        cond_params = condition.get("params", {})

        indicator = indicators.get(indicator_id)
        if indicator is None:
            return pd.Series(False, index=ohlcv.index)

        if cond_type == "OVER":
            other_id = cond_params.get("other")
            if other_id and other_id in indicators:
                return indicator > indicators[other_id]
            value = self._substitute_param(cond_params.get("value"), params)
            if value is not None:
                return indicator > float(value)

        elif cond_type == "UNDER":
            other_id = cond_params.get("other")
            if other_id and other_id in indicators:
                return indicator < indicators[other_id]
            value = self._substitute_param(cond_params.get("value"), params)
            if value is not None:
                return indicator < float(value)

        elif cond_type == "CROSSED_UP":
            other_id = cond_params.get("other")
            if other_id and other_id in indicators:
                other = indicators[other_id]
                return (indicator.shift(1) <= other.shift(1)) & (indicator > other)
            value = self._substitute_param(cond_params.get("value"), params)
            if value is not None:
                v = float(value)
                return (indicator.shift(1) <= v) & (indicator > v)

        elif cond_type == "CROSSED_DOWN":
            other_id = cond_params.get("other")
            if other_id and other_id in indicators:
                other = indicators[other_id]
                return (indicator.shift(1) >= other.shift(1)) & (indicator < other)
            value = self._substitute_param(cond_params.get("value"), params)
            if value is not None:
                v = float(value)
                return (indicator.shift(1) >= v) & (indicator < v)

        elif cond_type == "OVER_CONSTANT":
            value = self._substitute_param(cond_params.get("value"), params)
            if value is not None:
                return indicator > float(value)

        elif cond_type == "UNDER_CONSTANT":
            value = self._substitute_param(cond_params.get("value"), params)
            if value is not None:
                return indicator < float(value)

        elif cond_type == "IS_RISING":
            return indicator > indicator.shift(1)

        elif cond_type == "IS_FALLING":
            return indicator < indicator.shift(1)

        return pd.Series(False, index=ohlcv.index)
