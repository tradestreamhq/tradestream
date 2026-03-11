"""Tests for the shared config module."""

import os
import unittest
from unittest import mock


class GetPostgresConfigTest(unittest.TestCase):
    """Tests for get_postgres_config."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_defaults(self):
        from services.shared.config import get_postgres_config

        cfg = get_postgres_config()
        self.assertEqual(cfg["host"], "localhost")
        self.assertEqual(cfg["port"], 5432)
        self.assertEqual(cfg["database"], "tradestream")
        self.assertEqual(cfg["user"], "postgres")
        self.assertEqual(cfg["password"], "")

    @mock.patch.dict(
        os.environ,
        {
            "POSTGRES_HOST": "db.example.com",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DATABASE": "mydb",
            "POSTGRES_USERNAME": "admin",
            "POSTGRES_PASSWORD": "secret",
        },
    )
    def test_env_override(self):
        from services.shared.config import get_postgres_config

        cfg = get_postgres_config()
        self.assertEqual(cfg["host"], "db.example.com")
        self.assertEqual(cfg["port"], 5433)
        self.assertEqual(cfg["database"], "mydb")
        self.assertEqual(cfg["user"], "admin")
        self.assertEqual(cfg["password"], "secret")


class GetPostgresDsnTest(unittest.TestCase):
    """Tests for get_postgres_dsn."""

    @mock.patch.dict(
        os.environ,
        {
            "POSTGRES_HOST": "host",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DATABASE": "db",
            "POSTGRES_USERNAME": "user",
            "POSTGRES_PASSWORD": "pass",
        },
    )
    def test_dsn_format(self):
        from services.shared.config import get_postgres_dsn

        self.assertEqual(get_postgres_dsn(), "postgresql://user:pass@host:5432/db")


class GetRedisConfigTest(unittest.TestCase):
    """Tests for get_redis_config."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_defaults(self):
        from services.shared.config import get_redis_config

        cfg = get_redis_config()
        self.assertEqual(cfg["host"], "localhost")
        self.assertEqual(cfg["port"], 6379)
        self.assertIsNone(cfg["password"])

    @mock.patch.dict(
        os.environ,
        {"REDIS_HOST": "redis.local", "REDIS_PORT": "6380", "REDIS_PASSWORD": "rp"},
    )
    def test_env_override(self):
        from services.shared.config import get_redis_config

        cfg = get_redis_config()
        self.assertEqual(cfg["host"], "redis.local")
        self.assertEqual(cfg["port"], 6380)
        self.assertEqual(cfg["password"], "rp")


class GetInfluxdbConfigTest(unittest.TestCase):
    """Tests for get_influxdb_config."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_defaults(self):
        from services.shared.config import get_influxdb_config

        cfg = get_influxdb_config()
        self.assertEqual(cfg["url"], "http://localhost:8086")
        self.assertEqual(cfg["token"], "")
        self.assertEqual(cfg["org"], "")
        self.assertEqual(cfg["bucket"], "tradestream-data")


class RequireEnvTest(unittest.TestCase):
    """Tests for require_env."""

    @mock.patch.dict(os.environ, {"MY_VAR": "hello"})
    def test_present(self):
        from services.shared.config import require_env

        self.assertEqual(require_env("MY_VAR"), "hello")

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_missing_exits(self):
        from services.shared.config import require_env

        with self.assertRaises(SystemExit):
            require_env("MISSING_VAR")


if __name__ == "__main__":
    unittest.main()
