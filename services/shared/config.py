"""Shared configuration module for loading credentials from environment variables.

All credentials and connection parameters MUST be loaded from environment
variables. This module provides helpers that each service can use to build
its connection config dicts in a consistent way.

Environment variables
---------------------
PostgreSQL : POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE,
             POSTGRES_USERNAME, POSTGRES_PASSWORD
Redis      : REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
InfluxDB   : INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET
API keys   : OPENROUTER_API_KEY, CMC_API_KEY, ANTHROPIC_API_KEY
"""

import os
import sys

from absl import logging


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


def get_postgres_config() -> dict:
    """Return a PostgreSQL connection config dict from environment variables."""
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "database": os.environ.get("POSTGRES_DATABASE", "tradestream"),
        "user": os.environ.get("POSTGRES_USERNAME", "postgres"),
        "password": os.environ.get("POSTGRES_PASSWORD", ""),
    }


def get_postgres_dsn() -> str:
    """Return a PostgreSQL DSN string from environment variables."""
    cfg = get_postgres_config()
    return (
        f"postgresql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


def get_redis_config() -> dict:
    """Return a Redis connection config dict from environment variables."""
    return {
        "host": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", "6379")),
        "password": os.environ.get("REDIS_PASSWORD"),
    }


def get_redis_url() -> str:
    """Return a Redis URL string from environment variables."""
    host = os.environ.get("REDIS_HOST", "localhost")
    port = os.environ.get("REDIS_PORT", "6379")
    return f"redis://{host}:{port}/0"


# ---------------------------------------------------------------------------
# InfluxDB
# ---------------------------------------------------------------------------


def get_influxdb_config() -> dict:
    """Return an InfluxDB config dict from environment variables."""
    return {
        "url": os.environ.get("INFLUXDB_URL", "http://localhost:8086"),
        "token": os.environ.get("INFLUXDB_TOKEN", ""),
        "org": os.environ.get("INFLUXDB_ORG", ""),
        "bucket": os.environ.get("INFLUXDB_BUCKET", "tradestream-data"),
    }


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


def get_openrouter_api_key() -> str:
    """Return the OpenRouter API key from the environment."""
    return os.environ.get("OPENROUTER_API_KEY", "")


def get_cmc_api_key() -> str:
    """Return the CoinMarketCap API key from the environment."""
    return os.environ.get("CMC_API_KEY", "")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def require_env(name: str) -> str:
    """Return the value of an environment variable or exit if unset/empty."""
    value = os.environ.get(name, "")
    if not value:
        logging.error("Required environment variable %s is not set", name)
        sys.exit(1)
    return value
