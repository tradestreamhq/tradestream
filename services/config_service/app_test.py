"""Tests for the Config Service and API endpoints."""

import os
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.config_service.app import create_app
from services.config_service.config_service import (
    ConfigService,
    ConfigValidationError,
    _coerce_value,
    _mask_secrets_flat,
    validate_namespace,
)


# --- ConfigService unit tests ---


class TestConfigServiceDefaults:
    """Test default config loading."""

    def test_defaults_loaded(self):
        svc = ConfigService()
        config = svc.get_all(mask_secrets=False)
        assert "exchange" in config
        assert "strategy" in config
        assert "risk" in config
        assert "notification" in config

    def test_default_exchange_values(self):
        svc = ConfigService()
        exchange = svc.get_namespace("exchange", mask_secrets=False)
        assert exchange["default_exchange"] == "binance"
        assert exchange["sandbox_mode"] is True
        assert exchange["rate_limit"] == 1200

    def test_default_risk_values(self):
        svc = ConfigService()
        risk = svc.get_namespace("risk", mask_secrets=False)
        assert risk["max_position_pct"] == 10.0
        assert risk["stop_loss_pct"] == 5.0
        assert risk["take_profit_pct"] == 15.0

    def test_invalid_namespace_returns_none(self):
        svc = ConfigService()
        assert svc.get_namespace("nonexistent") is None


class TestConfigServiceYaml:
    """Test YAML file loading."""

    def test_load_yaml_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "risk.yaml"
            yaml_file.write_text(
                textwrap.dedent("""\
                    max_position_pct: 25.0
                    stop_loss_pct: 3.0
                """)
            )
            svc = ConfigService(config_dir=tmpdir)
            svc.load()

            risk = svc.get_namespace("risk", mask_secrets=False)
            assert risk["max_position_pct"] == 25.0
            assert risk["stop_loss_pct"] == 3.0
            # Default still present
            assert risk["take_profit_pct"] == 15.0

    def test_load_yaml_multiple_namespaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "exchange.yaml").write_text("default_exchange: kraken\n")
            (Path(tmpdir) / "strategy.yaml").write_text("backtest_days: 180\n")

            svc = ConfigService(config_dir=tmpdir)
            svc.load()

            assert svc.get_namespace("exchange", mask_secrets=False)["default_exchange"] == "kraken"
            assert svc.get_namespace("strategy", mask_secrets=False)["backtest_days"] == 180

    def test_load_yaml_invalid_file_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "risk.yaml"
            yaml_file.write_text(": invalid: yaml: {{")

            svc = ConfigService(config_dir=tmpdir)
            svc.load()
            # Defaults still loaded
            risk = svc.get_namespace("risk", mask_secrets=False)
            assert risk["max_position_pct"] == 10.0


class TestConfigServiceEnv:
    """Test environment variable loading."""

    def test_env_overrides_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "risk.yaml").write_text("max_position_pct: 25.0\n")

            env_vars = {"TRADESTREAM_RISK_MAXPOSITIONPCT": "50.0"}
            with patch.dict(os.environ, env_vars, clear=False):
                svc = ConfigService(config_dir=tmpdir)
                svc.load()

            risk = svc.get_namespace("risk", mask_secrets=False)
            assert risk["maxpositionpct"] == 50.0

    def test_env_bool_coercion(self):
        env_vars = {"TRADESTREAM_EXCHANGE_SANDBOXMODE": "false"}
        with patch.dict(os.environ, env_vars, clear=False):
            svc = ConfigService()
            svc.load()

        exchange = svc.get_namespace("exchange", mask_secrets=False)
        assert exchange["sandboxmode"] is False

    def test_env_int_coercion(self):
        env_vars = {"TRADESTREAM_STRATEGY_BACKTESTDAYS": "365"}
        with patch.dict(os.environ, env_vars, clear=False):
            svc = ConfigService()
            svc.load()

        strategy = svc.get_namespace("strategy", mask_secrets=False)
        assert strategy["backtestdays"] == 365


class TestConfigServiceUpdate:
    """Test runtime config updates."""

    def test_update_namespace(self):
        svc = ConfigService()
        result = svc.update_namespace("risk", {"max_position_pct": 30.0})
        assert result["max_position_pct"] == 30.0

    def test_update_invalid_namespace_raises(self):
        svc = ConfigService()
        with pytest.raises(ValueError):
            svc.update_namespace("bogus", {"key": "val"})

    def test_update_invalid_value_raises(self):
        svc = ConfigService()
        with pytest.raises(ConfigValidationError):
            svc.update_namespace("risk", {"max_position_pct": "not_a_number"})

    def test_update_notifies_watchers(self):
        svc = ConfigService()
        notified = []
        svc.on_change(lambda ns: notified.append(ns))
        svc.update_namespace("risk", {"max_position_pct": 30.0})
        assert notified == ["risk"]


class TestConfigServiceValidation:
    """Test config validation."""

    def test_validate_valid_config(self):
        svc = ConfigService()
        result = svc.validate_config({"risk": {"max_position_pct": 20.0}})
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_invalid_type(self):
        svc = ConfigService()
        result = svc.validate_config({"risk": {"max_position_pct": "bad"}})
        assert result["valid"] is False
        assert len(result["errors"]) == 1

    def test_validate_out_of_range(self):
        svc = ConfigService()
        result = svc.validate_config({"risk": {"max_position_pct": 200.0}})
        assert result["valid"] is False
        assert "above maximum" in result["errors"][0]["message"]

    def test_validate_below_minimum(self):
        svc = ConfigService()
        result = svc.validate_config({"risk": {"max_position_pct": -1.0}})
        assert result["valid"] is False
        assert "below minimum" in result["errors"][0]["message"]

    def test_validate_invalid_choice(self):
        svc = ConfigService()
        result = svc.validate_config(
            {"notification": {"min_severity": "apocalypse"}}
        )
        assert result["valid"] is False
        assert "Invalid value" in result["errors"][0]["message"]

    def test_validate_unknown_namespace(self):
        svc = ConfigService()
        result = svc.validate_config({"bogus": {"key": "val"}})
        assert result["valid"] is False
        assert "Unknown namespace" in result["errors"][0]["message"]

    def test_validate_non_dict_namespace(self):
        svc = ConfigService()
        result = svc.validate_config({"risk": "not_a_dict"})
        assert result["valid"] is False

    def test_validate_multiple_errors(self):
        svc = ConfigService()
        result = svc.validate_config(
            {
                "risk": {"max_position_pct": "bad", "stop_loss_pct": 999.0},
            }
        )
        assert result["valid"] is False
        assert len(result["errors"]) == 2


class TestSecretMasking:
    """Test secret masking."""

    def test_mask_api_key(self):
        svc = ConfigService()
        svc.update_namespace("exchange", {"api_key": "my_secret_key_123"})
        config = svc.get_namespace("exchange", mask_secrets=True)
        assert config["api_key"] == "********"

    def test_no_mask_when_disabled(self):
        svc = ConfigService()
        svc.update_namespace("exchange", {"api_key": "my_secret_key_123"})
        config = svc.get_namespace("exchange", mask_secrets=False)
        assert config["api_key"] == "my_secret_key_123"

    def test_mask_secrets_flat(self):
        data = {"api_key": "secret", "name": "public", "password": "hidden"}
        _mask_secrets_flat(data)
        assert data["api_key"] == "********"
        assert data["name"] == "public"
        assert data["password"] == "********"


class TestConfigInheritance:
    """Test config inheritance: default -> YAML -> env."""

    def test_full_inheritance_chain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "risk.yaml").write_text("max_position_pct: 25.0\n")
            env_vars = {"TRADESTREAM_RISK_STOPLOSS": "7.5"}
            with patch.dict(os.environ, env_vars, clear=False):
                svc = ConfigService(config_dir=tmpdir)
                svc.load()

            risk = svc.get_namespace("risk", mask_secrets=False)
            # From YAML
            assert risk["max_position_pct"] == 25.0
            # From env
            assert risk["stoploss"] == 7.5
            # From default
            assert risk["take_profit_pct"] == 15.0


class TestHotReload:
    """Test hot-reload functionality."""

    def test_reload_on_file_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "risk.yaml"
            yaml_file.write_text("max_position_pct: 25.0\n")

            svc = ConfigService(config_dir=tmpdir)
            svc.load()
            assert svc.get_namespace("risk", mask_secrets=False)["max_position_pct"] == 25.0

            # Modify the file and reload
            yaml_file.write_text("max_position_pct: 50.0\n")
            svc.load()
            assert svc.get_namespace("risk", mask_secrets=False)["max_position_pct"] == 50.0

    def test_start_stop_watching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            svc = ConfigService(config_dir=tmpdir)
            svc.start_watching(interval=0.1)
            assert svc._watching is True
            svc.stop_watching()
            assert svc._watching is False


class TestCoerceValue:
    """Test value coercion utility."""

    def test_coerce_bool_true(self):
        assert _coerce_value("true") is True
        assert _coerce_value("yes") is True

    def test_coerce_bool_false(self):
        assert _coerce_value("false") is False
        assert _coerce_value("no") is False

    def test_coerce_int(self):
        assert _coerce_value("42") == 42

    def test_coerce_float(self):
        assert _coerce_value("3.14") == 3.14

    def test_coerce_string(self):
        assert _coerce_value("hello") == "hello"


# --- API endpoint tests ---


@pytest.fixture
def client():
    svc = ConfigService()
    app = create_app(svc)
    return TestClient(app, raise_server_exceptions=False), svc


class TestGetAllConfig:
    def test_get_all_config(self, client):
        tc, _ = client
        resp = tc.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "config"
        attrs = body["data"]["attributes"]
        assert "exchange" in attrs
        assert "strategy" in attrs
        assert "risk" in attrs
        assert "notification" in attrs


class TestGetNamespaceConfig:
    def test_get_existing_namespace(self, client):
        tc, _ = client
        resp = tc.get("/risk")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "risk"
        assert body["data"]["attributes"]["max_position_pct"] == 10.0

    def test_get_nonexistent_namespace(self, client):
        tc, _ = client
        resp = tc.get("/bogus")
        assert resp.status_code == 404


class TestUpdateConfig:
    def test_update_valid_config(self, client):
        tc, _ = client
        resp = tc.put("/risk", json={"values": {"max_position_pct": 30.0}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["max_position_pct"] == 30.0

    def test_update_invalid_namespace(self, client):
        tc, _ = client
        resp = tc.put("/bogus", json={"values": {"key": "val"}})
        assert resp.status_code == 404

    def test_update_invalid_value(self, client):
        tc, _ = client
        resp = tc.put("/risk", json={"values": {"max_position_pct": "bad"}})
        assert resp.status_code == 422


class TestValidateConfig:
    def test_validate_valid(self, client):
        tc, _ = client
        resp = tc.post("/validate", json={"config": {"risk": {"max_position_pct": 20.0}}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["valid"] is True

    def test_validate_invalid(self, client):
        tc, _ = client
        resp = tc.post("/validate", json={"config": {"risk": {"max_position_pct": "bad"}}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["attributes"]["valid"] is False
        assert len(body["data"]["attributes"]["errors"]) > 0


class TestGetSchema:
    def test_get_schema(self, client):
        tc, _ = client
        resp = tc.get("/schema")
        assert resp.status_code == 200
        body = resp.json()
        schema = body["data"]["attributes"]
        assert "namespaces" in schema
        assert "exchange" in schema["namespaces"]
        assert "risk" in schema["namespaces"]


class TestHealthEndpoint:
    def test_health(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
