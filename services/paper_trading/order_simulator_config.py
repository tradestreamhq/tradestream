"""YAML configuration loader for the order execution simulator."""

import yaml

from services.paper_trading.order_simulator import SimulatorConfig

DEFAULT_CONFIG = {
    "slippage": {
        "model": "PERCENTAGE",
        "value": 0.001,
        "randomize": True,
    },
    "fees": {
        "maker_fee_rate": 0.001,
        "taker_fee_rate": 0.002,
        "min_fee": 0.0,
    },
    "partial_fill_enabled": False,
    "partial_fill_min_ratio": 0.5,
}


def load_config(path: str) -> SimulatorConfig:
    """Load simulator configuration from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return SimulatorConfig.from_dict(data.get("order_simulator", data))


def load_config_from_string(yaml_str: str) -> SimulatorConfig:
    """Load simulator configuration from a YAML string."""
    data = yaml.safe_load(yaml_str)
    return SimulatorConfig.from_dict(data.get("order_simulator", data))


def default_config() -> SimulatorConfig:
    """Return the default simulator configuration."""
    return SimulatorConfig.from_dict(DEFAULT_CONFIG)
