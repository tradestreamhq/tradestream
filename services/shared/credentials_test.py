"""Tests for services.shared.credentials."""

import os
import pytest


class TestRequireEnv:
    """Tests for _require_env helper."""

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_CRED", "secret123")
        from services.shared.credentials import _require_env

        assert _require_env("TEST_CRED") == "secret123"

    def test_exits_when_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_CRED_MISSING", raising=False)
        from services.shared.credentials import _require_env

        with pytest.raises(SystemExit):
            _require_env("TEST_CRED_MISSING")

    def test_exits_when_empty(self, monkeypatch):
        monkeypatch.setenv("TEST_CRED_EMPTY", "")
        from services.shared.credentials import _require_env

        with pytest.raises(SystemExit):
            _require_env("TEST_CRED_EMPTY")

    def test_exits_when_whitespace_only(self, monkeypatch):
        monkeypatch.setenv("TEST_CRED_WS", "   ")
        from services.shared.credentials import _require_env

        with pytest.raises(SystemExit):
            _require_env("TEST_CRED_WS")


class TestPostgresConfig:
    """Tests for PostgresConfig."""

    def test_reads_all_env_vars(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_HOST", "db.example.com")
        monkeypatch.setenv("POSTGRES_PORT", "5433")
        monkeypatch.setenv("POSTGRES_DATABASE", "mydb")
        monkeypatch.setenv("POSTGRES_USERNAME", "admin")
        monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret")

        from services.shared.credentials import PostgresConfig

        cfg = PostgresConfig()
        assert cfg.host == "db.example.com"
        assert cfg.port == 5433
        assert cfg.database == "mydb"
        assert cfg.username == "admin"
        assert cfg.password == "s3cret"

    def test_dsn_property(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_HOST", "host")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("POSTGRES_DATABASE", "db")
        monkeypatch.setenv("POSTGRES_USERNAME", "user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "pw")

        from services.shared.credentials import PostgresConfig

        cfg = PostgresConfig()
        assert cfg.dsn == "postgresql://user:pw@host:5432/db"

    def test_as_dict(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_PASSWORD", "pw")

        from services.shared.credentials import PostgresConfig

        cfg = PostgresConfig()
        d = cfg.as_dict()
        assert d["password"] == "pw"
        assert "host" in d
        assert "port" in d
        assert "database" in d
        assert "username" in d

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.delenv("POSTGRES_PORT", raising=False)
        monkeypatch.delenv("POSTGRES_DATABASE", raising=False)
        monkeypatch.delenv("POSTGRES_USERNAME", raising=False)
        monkeypatch.setenv("POSTGRES_PASSWORD", "pw")

        from services.shared.credentials import PostgresConfig

        cfg = PostgresConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 5432
        assert cfg.database == "tradestream"
        assert cfg.username == "postgres"

    def test_exits_without_password(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

        from services.shared.credentials import PostgresConfig

        with pytest.raises(SystemExit):
            PostgresConfig()


class TestRedisConfig:
    """Tests for RedisConfig."""

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("REDIS_HOST", raising=False)
        monkeypatch.delenv("REDIS_PORT", raising=False)
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)

        from services.shared.credentials import RedisConfig

        cfg = RedisConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 6379
        assert cfg.password is None

    def test_url_without_password(self, monkeypatch):
        monkeypatch.delenv("REDIS_PASSWORD", raising=False)
        monkeypatch.setenv("REDIS_HOST", "redis.local")
        monkeypatch.setenv("REDIS_PORT", "6380")

        from services.shared.credentials import RedisConfig

        cfg = RedisConfig()
        assert cfg.url == "redis://redis.local:6380/0"

    def test_url_with_password(self, monkeypatch):
        monkeypatch.setenv("REDIS_HOST", "redis.local")
        monkeypatch.setenv("REDIS_PORT", "6380")
        monkeypatch.setenv("REDIS_PASSWORD", "redispw")

        from services.shared.credentials import RedisConfig

        cfg = RedisConfig()
        assert cfg.url == "redis://:redispw@redis.local:6380/0"


class TestInfluxDBConfig:
    """Tests for InfluxDBConfig."""

    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("INFLUXDB_URL", "http://influx:8086")
        monkeypatch.setenv("INFLUXDB_TOKEN", "mytoken")
        monkeypatch.setenv("INFLUXDB_ORG", "myorg")
        monkeypatch.setenv("INFLUXDB_BUCKET", "mybucket")

        from services.shared.credentials import InfluxDBConfig

        cfg = InfluxDBConfig()
        assert cfg.url == "http://influx:8086"
        assert cfg.token == "mytoken"
        assert cfg.org == "myorg"
        assert cfg.bucket == "mybucket"

    def test_exits_without_token(self, monkeypatch):
        monkeypatch.delenv("INFLUXDB_TOKEN", raising=False)

        from services.shared.credentials import InfluxDBConfig

        with pytest.raises(SystemExit):
            InfluxDBConfig()


class TestAPIKeyHelpers:
    """Tests for API key helper functions."""

    def test_openrouter_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-123")

        from services.shared.credentials import openrouter_api_key

        assert openrouter_api_key() == "or-key-123"

    def test_openrouter_api_key_exits_when_missing(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        from services.shared.credentials import openrouter_api_key

        with pytest.raises(SystemExit):
            openrouter_api_key()

    def test_cmc_api_key(self, monkeypatch):
        monkeypatch.setenv("CMC_API_KEY", "cmc-key-456")

        from services.shared.credentials import cmc_api_key

        assert cmc_api_key() == "cmc-key-456"

    def test_cmc_api_key_exits_when_missing(self, monkeypatch):
        monkeypatch.delenv("CMC_API_KEY", raising=False)

        from services.shared.credentials import cmc_api_key

        with pytest.raises(SystemExit):
            cmc_api_key()


class TestKafkaBootstrapServers:
    """Tests for kafka_bootstrap_servers."""

    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "kafka1:9092,kafka2:9092")

        from services.shared.credentials import kafka_bootstrap_servers

        assert kafka_bootstrap_servers() == "kafka1:9092,kafka2:9092"

    def test_defaults_to_localhost(self, monkeypatch):
        monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)

        from services.shared.credentials import kafka_bootstrap_servers

        assert kafka_bootstrap_servers() == "localhost:9092"
