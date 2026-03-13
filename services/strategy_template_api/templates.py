"""
Built-in strategy templates for TradeStream.

Each template is a valid YAML strategy config with sensible defaults,
documentation, and parameter descriptions.
"""

from typing import Any

TEMPLATES: dict[str, dict[str, Any]] = {
    "ma-crossover": {
        "id": "ma-crossover",
        "name": "Moving Average Crossover",
        "description": (
            "Classic trend-following strategy that generates buy signals when a "
            "fast moving average crosses above a slow moving average, and sell "
            "signals on the reverse crossover. Supports both SMA and EMA variants."
        ),
        "category": "trend-following",
        "complexity": "SIMPLE",
        "recommended_markets": ["crypto", "equities", "forex"],
        "risk_profile": "moderate",
        "strategy_config": {
            "name": "Moving Average Crossover",
            "indicators": [
                {
                    "id": "fast_ma",
                    "type": "EMA",
                    "params": {"period": "${fastPeriod}"},
                },
                {
                    "id": "slow_ma",
                    "type": "EMA",
                    "params": {"period": "${slowPeriod}"},
                },
            ],
            "entryConditions": [
                {
                    "type": "CROSSED_UP",
                    "indicator": "fast_ma",
                    "params": {"other": "slow_ma"},
                },
            ],
            "exitConditions": [
                {
                    "type": "CROSSED_DOWN",
                    "indicator": "fast_ma",
                    "params": {"other": "slow_ma"},
                },
            ],
            "parameters": [
                {
                    "name": "fastPeriod",
                    "type": "INTEGER",
                    "min": 5,
                    "max": 50,
                    "defaultValue": 12,
                    "description": "Period for the fast moving average",
                },
                {
                    "name": "slowPeriod",
                    "type": "INTEGER",
                    "min": 20,
                    "max": 200,
                    "defaultValue": 26,
                    "description": "Period for the slow moving average",
                },
            ],
        },
        "parameter_docs": {
            "fastPeriod": {
                "description": "Period for the fast moving average",
                "recommended_range": "5-50",
                "impact": "Lower values react faster to price changes but produce more false signals",
            },
            "slowPeriod": {
                "description": "Period for the slow moving average",
                "recommended_range": "20-200",
                "impact": "Higher values filter noise but delay entries and exits",
            },
        },
        "variants": {
            "SMA": "Change indicator types from EMA to SMA for smoother signals",
            "EMA": "Default — uses exponential moving averages for faster response",
        },
    },
    "rsi-mean-reversion": {
        "id": "rsi-mean-reversion",
        "name": "RSI Mean Reversion",
        "description": (
            "Mean reversion strategy that buys when RSI indicates oversold "
            "conditions and sells when RSI indicates overbought conditions. "
            "Best suited for range-bound markets."
        ),
        "category": "mean-reversion",
        "complexity": "SIMPLE",
        "recommended_markets": ["crypto", "equities"],
        "risk_profile": "moderate",
        "strategy_config": {
            "name": "RSI Mean Reversion",
            "indicators": [
                {
                    "id": "rsi",
                    "type": "RSI",
                    "params": {"period": "${rsiPeriod}"},
                },
            ],
            "entryConditions": [
                {
                    "type": "CROSSED_UP",
                    "indicator": "rsi",
                    "params": {"value": "${oversoldLevel}"},
                },
            ],
            "exitConditions": [
                {
                    "type": "CROSSED_DOWN",
                    "indicator": "rsi",
                    "params": {"value": "${overboughtLevel}"},
                },
            ],
            "parameters": [
                {
                    "name": "rsiPeriod",
                    "type": "INTEGER",
                    "min": 2,
                    "max": 30,
                    "defaultValue": 14,
                    "description": "RSI calculation period",
                },
                {
                    "name": "oversoldLevel",
                    "type": "DOUBLE",
                    "min": 10.0,
                    "max": 40.0,
                    "defaultValue": 30.0,
                    "description": "RSI level below which the asset is considered oversold",
                },
                {
                    "name": "overboughtLevel",
                    "type": "DOUBLE",
                    "min": 60.0,
                    "max": 90.0,
                    "defaultValue": 70.0,
                    "description": "RSI level above which the asset is considered overbought",
                },
            ],
        },
        "parameter_docs": {
            "rsiPeriod": {
                "description": "Number of periods for RSI calculation",
                "recommended_range": "2-30",
                "impact": "Shorter periods increase sensitivity; longer periods reduce noise",
            },
            "oversoldLevel": {
                "description": "RSI threshold for buy signals",
                "recommended_range": "20-35",
                "impact": "Lower values produce fewer but higher-conviction entries",
            },
            "overboughtLevel": {
                "description": "RSI threshold for sell signals",
                "recommended_range": "65-80",
                "impact": "Higher values let winners run longer but risk giving back profits",
            },
        },
    },
    "bollinger-breakout": {
        "id": "bollinger-breakout",
        "name": "Bollinger Band Breakout",
        "description": (
            "Volatility breakout strategy that enters when price breaks above "
            "the upper Bollinger Band and exits when price falls below the lower "
            "band. Captures strong momentum moves after periods of low volatility."
        ),
        "category": "breakout",
        "complexity": "MEDIUM",
        "recommended_markets": ["crypto", "commodities", "forex"],
        "risk_profile": "aggressive",
        "strategy_config": {
            "name": "Bollinger Band Breakout",
            "indicators": [
                {
                    "id": "bb_upper",
                    "type": "BOLLINGER_UPPER",
                    "params": {"period": "${bbPeriod}"},
                },
                {
                    "id": "bb_lower",
                    "type": "BOLLINGER_LOWER",
                    "params": {"period": "${bbPeriod}"},
                },
                {
                    "id": "close",
                    "type": "CLOSE_PRICE",
                    "params": {},
                },
            ],
            "entryConditions": [
                {
                    "type": "CROSSED_UP",
                    "indicator": "close",
                    "params": {"other": "bb_upper"},
                },
            ],
            "exitConditions": [
                {
                    "type": "CROSSED_DOWN",
                    "indicator": "close",
                    "params": {"other": "bb_lower"},
                },
            ],
            "parameters": [
                {
                    "name": "bbPeriod",
                    "type": "INTEGER",
                    "min": 10,
                    "max": 50,
                    "defaultValue": 20,
                    "description": "Bollinger Band calculation period",
                },
            ],
        },
        "parameter_docs": {
            "bbPeriod": {
                "description": "Lookback period for Bollinger Band calculation",
                "recommended_range": "10-50",
                "impact": "Shorter periods tighten bands and trigger more breakout signals",
            },
        },
    },
    "macd-momentum": {
        "id": "macd-momentum",
        "name": "MACD Momentum",
        "description": (
            "Momentum strategy using the MACD indicator. Enters on MACD line "
            "crossing above zero (bullish momentum shift) and exits on MACD "
            "crossing below zero. Effective for identifying trend changes."
        ),
        "category": "momentum",
        "complexity": "MEDIUM",
        "recommended_markets": ["crypto", "equities", "futures"],
        "risk_profile": "moderate",
        "strategy_config": {
            "name": "MACD Momentum",
            "indicators": [
                {
                    "id": "macd",
                    "type": "MACD",
                    "params": {
                        "fastPeriod": "${macdFast}",
                        "slowPeriod": "${macdSlow}",
                    },
                },
            ],
            "entryConditions": [
                {
                    "type": "CROSSED_UP",
                    "indicator": "macd",
                    "params": {"value": 0},
                },
            ],
            "exitConditions": [
                {
                    "type": "CROSSED_DOWN",
                    "indicator": "macd",
                    "params": {"value": 0},
                },
            ],
            "parameters": [
                {
                    "name": "macdFast",
                    "type": "INTEGER",
                    "min": 5,
                    "max": 20,
                    "defaultValue": 12,
                    "description": "Fast EMA period for MACD calculation",
                },
                {
                    "name": "macdSlow",
                    "type": "INTEGER",
                    "min": 20,
                    "max": 50,
                    "defaultValue": 26,
                    "description": "Slow EMA period for MACD calculation",
                },
            ],
        },
        "parameter_docs": {
            "macdFast": {
                "description": "Fast EMA period for MACD",
                "recommended_range": "8-15",
                "impact": "Smaller values make MACD more responsive to recent price changes",
            },
            "macdSlow": {
                "description": "Slow EMA period for MACD",
                "recommended_range": "20-35",
                "impact": "Larger values smooth the signal but increase lag",
            },
        },
    },
    "volume-weighted-trend": {
        "id": "volume-weighted-trend",
        "name": "Volume-Weighted Trend Following",
        "description": (
            "Trend-following strategy that combines EMA crossover with volume "
            "confirmation via On-Balance Volume (OBV). Only enters when both "
            "price trend and volume trend align, reducing false signals."
        ),
        "category": "trend-following",
        "complexity": "COMPLEX",
        "recommended_markets": ["crypto", "equities"],
        "risk_profile": "conservative",
        "strategy_config": {
            "name": "Volume-Weighted Trend Following",
            "indicators": [
                {
                    "id": "fast_ema",
                    "type": "EMA",
                    "params": {"period": "${fastPeriod}"},
                },
                {
                    "id": "slow_ema",
                    "type": "EMA",
                    "params": {"period": "${slowPeriod}"},
                },
                {
                    "id": "obv",
                    "type": "OBV",
                    "params": {},
                },
                {
                    "id": "obv_ema",
                    "type": "EMA",
                    "params": {"period": "${obvEmaPeriod}"},
                },
            ],
            "entryConditions": [
                {
                    "type": "OVER",
                    "indicator": "fast_ema",
                    "params": {"other": "slow_ema"},
                },
                {
                    "type": "OVER",
                    "indicator": "obv",
                    "params": {"other": "obv_ema"},
                },
            ],
            "exitConditions": [
                {
                    "type": "CROSSED_DOWN",
                    "indicator": "fast_ema",
                    "params": {"other": "slow_ema"},
                },
            ],
            "parameters": [
                {
                    "name": "fastPeriod",
                    "type": "INTEGER",
                    "min": 5,
                    "max": 30,
                    "defaultValue": 10,
                    "description": "Fast EMA period for price trend",
                },
                {
                    "name": "slowPeriod",
                    "type": "INTEGER",
                    "min": 20,
                    "max": 100,
                    "defaultValue": 30,
                    "description": "Slow EMA period for price trend",
                },
                {
                    "name": "obvEmaPeriod",
                    "type": "INTEGER",
                    "min": 10,
                    "max": 50,
                    "defaultValue": 20,
                    "description": "EMA period applied to OBV for volume trend smoothing",
                },
            ],
        },
        "parameter_docs": {
            "fastPeriod": {
                "description": "Fast EMA period for price trend detection",
                "recommended_range": "5-20",
                "impact": "Controls how quickly the strategy responds to price trend changes",
            },
            "slowPeriod": {
                "description": "Slow EMA period for price trend baseline",
                "recommended_range": "20-60",
                "impact": "Defines the longer-term trend direction",
            },
            "obvEmaPeriod": {
                "description": "EMA smoothing period for On-Balance Volume",
                "recommended_range": "10-30",
                "impact": "Smooths volume signal; higher values require more sustained volume confirmation",
            },
        },
    },
}


def get_template(template_id: str) -> dict[str, Any] | None:
    """Return a template by ID, or None if not found."""
    return TEMPLATES.get(template_id)


def list_templates(category: str | None = None) -> list[dict[str, Any]]:
    """Return all templates, optionally filtered by category."""
    templates = list(TEMPLATES.values())
    if category:
        templates = [t for t in templates if t["category"] == category]
    return templates


def instantiate_template(
    template_id: str,
    overrides: dict[str, Any] | None = None,
    name_override: str | None = None,
) -> dict[str, Any] | None:
    """
    Create a strategy config from a template with optional parameter overrides.

    Returns the strategy config dict ready for insertion into strategy_specs,
    or None if the template is not found.
    """
    template = get_template(template_id)
    if template is None:
        return None

    import copy

    config = copy.deepcopy(template["strategy_config"])

    if name_override:
        config["name"] = name_override

    if overrides:
        for param in config.get("parameters", []):
            if param["name"] in overrides:
                param["defaultValue"] = overrides[param["name"]]

    return config
