"""
Strategy Registry Module.

Provides access to available strategy names from configuration.
This module decouples strategy enumeration from the StrategyType proto enum,
enabling string-based strategy identification.
"""

import os
from typing import List


# Default strategy names matching current StrategyType enum values
# (excluding UNSPECIFIED)
_DEFAULT_STRATEGY_NAMES = [
    "MACD_CROSSOVER",
    "SMA_RSI",
]


def get_supported_strategy_names() -> List[str]:
    """
    Get the list of supported strategy names.

    Reads strategy names from the STRATEGY_NAMES environment variable.
    If not set, falls back to default strategy names.

    Environment variable format: comma-separated list of strategy names.
    Example: STRATEGY_NAMES=MACD_CROSSOVER,SMA_RSI,BOLLINGER_BREAKOUT

    Returns:
        List of strategy name strings.
    """
    env_value = os.environ.get("STRATEGY_NAMES", "")

    if env_value:
        # Parse comma-separated list, strip whitespace, filter empty strings
        names = [name.strip() for name in env_value.split(",")]
        return [name for name in names if name]

    return _DEFAULT_STRATEGY_NAMES.copy()
