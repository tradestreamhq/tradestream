"""
Migration scaffold tool for TradeStream strategy YAML files.

Generates a YAML template from a strategy name, with placeholder values
that can be filled in to complete the migration from Java strategy classes.
"""

import re


def _to_snake_case(name: str) -> str:
    """Convert CamelCase or UPPER_CASE to snake_case."""
    # Handle UPPER_CASE
    if "_" in name and name == name.upper():
        return name.lower()
    # Handle CamelCase
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


def scaffold_strategy_yaml(strategy_name: str) -> str:
    """
    Generate a YAML template for a strategy migration.

    Args:
        strategy_name: The strategy name (e.g. 'DoubleEmaCrossover' or 'DOUBLE_EMA_CROSSOVER')

    Returns:
        A YAML string template with placeholder values.
    """
    upper_name = _to_snake_case(strategy_name).upper()
    snake_name = _to_snake_case(strategy_name)

    return f"""\
# Strategy: {upper_name}
# Migrated from Java class. Fill in the TODO placeholders.
name: {upper_name}
version: "1.0.0"
description: "TODO: describe {snake_name} strategy"

asset_pairs:
  - BTC/USD  # TODO: specify trading pairs

timeframes:
  - 1h  # TODO: specify timeframes

indicators:
  - id: indicator1
    type: SMA  # TODO: choose indicator type
    input: close
    params:
      period: "${{period1}}"  # TODO: set parameter reference

entry_conditions:
  - type: CROSSED_UP  # TODO: choose condition type
    indicator: indicator1
    params:
      crosses: indicator1  # TODO: set cross reference

exit_conditions:
  - type: CROSSED_DOWN  # TODO: choose condition type
    indicator: indicator1
    params:
      crosses: indicator1  # TODO: set cross reference

parameters:
  - name: period1
    type: INTEGER
    min: 5
    max: 50
    defaultValue: 20  # TODO: set default

risk_params:
  max_position_pct: 10.0  # TODO: set max position size
  stop_loss_pct: 2.0  # TODO: set stop loss
  take_profit_pct: 5.0  # TODO: set take profit
"""
