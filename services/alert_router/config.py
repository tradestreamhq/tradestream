"""Configuration for the alert router service."""

import os


def get_config():
    """Load configuration from environment variables."""
    return {
        "host": os.environ.get("ALERT_ROUTER_HOST", "0.0.0.0"),
        "port": int(os.environ.get("ALERT_ROUTER_PORT", "8080")),
    }
