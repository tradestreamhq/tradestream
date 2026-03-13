"""
Configuration schemas for TradeStream namespaces.

Each namespace has a schema defining field types, constraints, and defaults.
"""

NAMESPACE_SCHEMAS = {
    "exchange": {
        "default_exchange": {
            "type": "str",
            "description": "Default exchange to use",
            "choices": [
                "binance",
                "coinbase",
                "kraken",
                "bitfinex",
                "bybit",
                "okx",
            ],
        },
        "sandbox_mode": {
            "type": "bool",
            "description": "Use exchange sandbox/testnet",
        },
        "rate_limit": {
            "type": "int",
            "description": "Max API requests per minute",
            "min": 1,
            "max": 10000,
        },
        "timeout_ms": {
            "type": "int",
            "description": "Request timeout in milliseconds",
            "min": 1000,
            "max": 120000,
        },
        "retry_count": {
            "type": "int",
            "description": "Number of retries on failure",
            "min": 0,
            "max": 10,
        },
        "api_key": {
            "type": "str",
            "description": "Exchange API key",
        },
        "api_secret": {
            "type": "str",
            "description": "Exchange API secret",
        },
    },
    "strategy": {
        "max_concurrent_strategies": {
            "type": "int",
            "description": "Maximum strategies running concurrently",
            "min": 1,
            "max": 100,
        },
        "evaluation_interval_seconds": {
            "type": "int",
            "description": "How often to evaluate strategies (seconds)",
            "min": 1,
            "max": 86400,
        },
        "default_timeframe": {
            "type": "str",
            "description": "Default candle timeframe",
            "choices": [
                "1m",
                "5m",
                "15m",
                "30m",
                "1h",
                "2h",
                "4h",
                "6h",
                "12h",
                "1d",
                "3d",
                "1w",
                "1M",
            ],
        },
        "backtest_days": {
            "type": "int",
            "description": "Days of historical data for backtesting",
            "min": 1,
            "max": 3650,
        },
    },
    "risk": {
        "max_position_pct": {
            "type": "float",
            "description": "Maximum position size as % of portfolio",
            "min": 0.1,
            "max": 100.0,
        },
        "stop_loss_pct": {
            "type": "float",
            "description": "Default stop loss percentage",
            "min": 0.1,
            "max": 50.0,
        },
        "take_profit_pct": {
            "type": "float",
            "description": "Default take profit percentage",
            "min": 0.1,
            "max": 100.0,
        },
        "max_drawdown_pct": {
            "type": "float",
            "description": "Maximum allowed drawdown percentage",
            "min": 1.0,
            "max": 100.0,
        },
        "max_open_positions": {
            "type": "int",
            "description": "Maximum number of open positions",
            "min": 1,
            "max": 100,
        },
        "daily_loss_limit_pct": {
            "type": "float",
            "description": "Daily loss limit as % of portfolio",
            "min": 0.1,
            "max": 100.0,
        },
    },
    "notification": {
        "enabled": {
            "type": "bool",
            "description": "Enable notifications",
        },
        "channels": {
            "type": "list",
            "description": "Notification channels",
        },
        "min_severity": {
            "type": "str",
            "description": "Minimum severity level for notifications",
            "choices": ["debug", "info", "warning", "error", "critical"],
        },
        "throttle_seconds": {
            "type": "int",
            "description": "Minimum seconds between duplicate notifications",
            "min": 0,
            "max": 86400,
        },
    },
}


CONFIG_SCHEMA = {
    "description": "TradeStream configuration schema",
    "namespaces": {
        ns: {
            "fields": {
                field_name: field_def for field_name, field_def in fields.items()
            }
        }
        for ns, fields in NAMESPACE_SCHEMAS.items()
    },
}
