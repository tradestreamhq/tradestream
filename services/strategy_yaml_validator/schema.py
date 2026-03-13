"""
JSON Schema definition for TradeStream strategy YAML files.
"""

from experiments.llm_validation.strategy_schema import ConditionType, IndicatorType

VALID_INDICATOR_TYPES = [e.value for e in IndicatorType]
VALID_CONDITION_TYPES = [e.value for e in ConditionType]

VALID_TIMEFRAMES = [
    "1m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "12h",
    "1d", "3d", "1w", "1M",
]

STRATEGY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "TradeStream Strategy",
    "type": "object",
    "required": [
        "name",
        "version",
        "asset_pairs",
        "timeframes",
        "entry_conditions",
        "exit_conditions",
        "risk_params",
    ],
    "properties": {
        "name": {
            "type": "string",
            "minLength": 1,
            "description": "Unique strategy name",
        },
        "version": {
            "type": "string",
            "pattern": r"^\d+\.\d+\.\d+$",
            "description": "Semantic version string (e.g. 1.0.0)",
        },
        "description": {
            "type": "string",
        },
        "complexity": {
            "type": "string",
            "enum": ["SIMPLE", "MEDIUM", "COMPLEX"],
        },
        "asset_pairs": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "string",
                "pattern": r"^[A-Z0-9]+/[A-Z0-9]+$",
            },
            "description": "Trading pairs (e.g. BTC/USD)",
        },
        "timeframes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "string",
                "enum": VALID_TIMEFRAMES,
            },
        },
        "indicators": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "type": {"type": "string", "enum": VALID_INDICATOR_TYPES},
                    "input": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
        },
        "entry_conditions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "indicator"],
                "properties": {
                    "type": {"type": "string", "enum": VALID_CONDITION_TYPES},
                    "indicator": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
        },
        "exit_conditions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "indicator"],
                "properties": {
                    "type": {"type": "string", "enum": VALID_CONDITION_TYPES},
                    "indicator": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
        },
        "parameters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "type": {"type": "string", "enum": ["INTEGER", "DOUBLE"]},
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                    "defaultValue": {"type": "number"},
                },
            },
        },
        "risk_params": {
            "type": "object",
            "required": ["max_position_pct"],
            "properties": {
                "max_position_pct": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                },
                "stop_loss_pct": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                },
                "take_profit_pct": {
                    "type": "number",
                    "minimum": 0,
                },
                "max_drawdown_pct": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
        },
    },
    "additionalProperties": True,
}
