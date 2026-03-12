"""Configuration for the alert rules engine."""

import os


def get_config():
    """Load configuration from environment variables."""
    return {
        # Redis
        "redis_host": os.environ.get("REDIS_HOST", "localhost"),
        "redis_port": int(os.environ.get("REDIS_PORT", "6379")),
        # Evaluation loop
        "eval_interval_seconds": int(os.environ.get("EVAL_INTERVAL_SECONDS", "30")),
        # Service endpoints
        "portfolio_url": os.environ.get("PORTFOLIO_URL", "http://localhost:8095"),
        "market_data_url": os.environ.get("MARKET_DATA_URL", "http://localhost:8081"),
        # HTTP API
        "api_port": int(os.environ.get("ALERT_API_PORT", "8098")),
    }
