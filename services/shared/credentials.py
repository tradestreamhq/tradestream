"""Centralized credential and infrastructure configuration.

All services should use the helpers in this module to access credentials
and connection parameters instead of reading os.environ / FLAGS directly.

Every value is sourced from an environment variable.  Required credentials
(passwords, tokens, API keys) cause an immediate ``SystemExit`` when missing
so that misconfigurations surface at startup rather than at runtime.
"""

import os
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    """Return the value of *name* or exit if it is unset / empty."""
    value = os.environ.get(name, "").strip()
    if not value:
        print(
            f"FATAL: required environment variable {name} is not set",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def _optional_env(name: str, default: str = "") -> str:
    """Return the value of *name*, falling back to *default*."""
    return os.environ.get(name, default)


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


class PostgresConfig:
    """PostgreSQL connection parameters from environment variables.

    Required env vars: ``POSTGRES_PASSWORD``
    Optional env vars (with defaults):
        ``POSTGRES_HOST`` (localhost), ``POSTGRES_PORT`` (5432),
        ``POSTGRES_DATABASE`` (tradestream), ``POSTGRES_USERNAME`` (postgres)
    """

    def __init__(self) -> None:
        self.host: str = _optional_env("POSTGRES_HOST", "localhost")
        self.port: int = int(_optional_env("POSTGRES_PORT", "5432"))
        self.database: str = _optional_env("POSTGRES_DATABASE", "tradestream")
        self.username: str = _optional_env("POSTGRES_USERNAME", "postgres")
        self.password: str = _require_env("POSTGRES_PASSWORD")

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def as_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": self.password,
        }


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


class RedisConfig:
    """Redis connection parameters from environment variables.

    Optional env vars (with defaults):
        ``REDIS_HOST`` (localhost), ``REDIS_PORT`` (6379),
        ``REDIS_PASSWORD`` (empty)
    """

    def __init__(self) -> None:
        self.host: str = _optional_env("REDIS_HOST", "localhost")
        self.port: int = int(_optional_env("REDIS_PORT", "6379"))
        self.password: Optional[str] = os.environ.get("REDIS_PASSWORD") or None

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/0"
        return f"redis://{self.host}:{self.port}/0"


# ---------------------------------------------------------------------------
# InfluxDB
# ---------------------------------------------------------------------------


class InfluxDBConfig:
    """InfluxDB connection parameters from environment variables.

    Required env vars: ``INFLUXDB_TOKEN``
    Optional env vars (with defaults):
        ``INFLUXDB_URL`` (http://localhost:8086),
        ``INFLUXDB_ORG`` (tradestream-org),
        ``INFLUXDB_BUCKET`` (tradestream-data)
    """

    def __init__(self) -> None:
        self.url: str = _optional_env("INFLUXDB_URL", "http://localhost:8086")
        self.token: str = _require_env("INFLUXDB_TOKEN")
        self.org: str = _optional_env("INFLUXDB_ORG", "tradestream-org")
        self.bucket: str = _optional_env("INFLUXDB_BUCKET", "tradestream-data")


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


def openrouter_api_key() -> str:
    """Return the OpenRouter API key (required)."""
    return _require_env("OPENROUTER_API_KEY")


def cmc_api_key() -> str:
    """Return the CoinMarketCap API key (required)."""
    return _require_env("CMC_API_KEY")


# ---------------------------------------------------------------------------
# Kafka
# ---------------------------------------------------------------------------


def kafka_bootstrap_servers() -> str:
    """Return Kafka bootstrap servers."""
    return _optional_env("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
