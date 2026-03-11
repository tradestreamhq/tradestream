"""Tests for strategy_parameter_registry."""

import pytest
from google.protobuf import any_pb2

from protos import strategies_pb2
from services.shared.strategy_parameter_registry import (
    PARAMETER_REGISTRY,
    SCHEMA_FINGERPRINT,
    compute_schema_fingerprint,
    get_parameter_class,
    unpack_strategy_parameters,
)


class TestParameterRegistry:
    """Tests for the auto-discovered parameter registry."""

    def test_registry_discovers_sma_rsi_parameters(self):
        type_url = "type.googleapis.com/strategies.SmaRsiParameters"
        assert type_url in PARAMETER_REGISTRY
        assert PARAMETER_REGISTRY[type_url] is strategies_pb2.SmaRsiParameters

    def test_registry_discovers_ema_macd_parameters(self):
        type_url = "type.googleapis.com/strategies.EmaMacdParameters"
        assert type_url in PARAMETER_REGISTRY
        assert PARAMETER_REGISTRY[type_url] is strategies_pb2.EmaMacdParameters

    def test_registry_discovers_configurable_strategy_parameters(self):
        type_url = "type.googleapis.com/strategies.ConfigurableStrategyParameters"
        assert type_url in PARAMETER_REGISTRY

    def test_registry_does_not_include_non_parameter_messages(self):
        """Strategy message itself should not appear in the registry."""
        type_url = "type.googleapis.com/strategies.Strategy"
        assert type_url not in PARAMETER_REGISTRY

    def test_registry_has_many_entries(self):
        """Sanity check: there should be a large number of parameter types."""
        assert len(PARAMETER_REGISTRY) > 40

    def test_all_registry_entries_end_with_parameters(self):
        for type_url in PARAMETER_REGISTRY:
            assert type_url.endswith("Parameters"), f"Unexpected entry: {type_url}"


class TestGetParameterClass:
    def test_known_type(self):
        cls = get_parameter_class("type.googleapis.com/strategies.SmaRsiParameters")
        assert cls is strategies_pb2.SmaRsiParameters

    def test_unknown_type_returns_none(self):
        cls = get_parameter_class(
            "type.googleapis.com/strategies.NonExistentParameters"
        )
        assert cls is None


class TestUnpackStrategyParameters:
    def test_unpack_sma_rsi(self):
        params = strategies_pb2.SmaRsiParameters(
            movingAveragePeriod=20,
            rsiPeriod=14,
            overboughtThreshold=70.0,
            oversoldThreshold=30.0,
        )
        any_msg = any_pb2.Any()
        any_msg.Pack(params)

        strategy = strategies_pb2.Strategy(
            strategy_name="SMA_RSI",
            parameters=any_msg,
        )

        result = unpack_strategy_parameters(strategy)
        assert result["movingAveragePeriod"] == 20
        assert result["rsiPeriod"] == 14
        assert result["overboughtThreshold"] == 70.0
        assert result["oversoldThreshold"] == 30.0

    def test_unpack_empty_strategy(self):
        strategy = strategies_pb2.Strategy(strategy_name="SMA_RSI")
        result = unpack_strategy_parameters(strategy)
        assert result == {}

    def test_unpack_unknown_type_returns_empty(self):
        """If the Any contains an unrecognized type, return empty dict."""
        any_msg = any_pb2.Any()
        any_msg.type_url = "type.googleapis.com/strategies.FakeParameters"
        any_msg.value = b"\x00"

        strategy = strategies_pb2.Strategy(
            strategy_name="FAKE",
            parameters=any_msg,
        )
        result = unpack_strategy_parameters(strategy)
        assert result == {}


class TestSchemaFingerprint:
    def test_fingerprint_is_stable(self):
        """Calling compute twice should return the same value."""
        assert compute_schema_fingerprint() == SCHEMA_FINGERPRINT

    def test_fingerprint_is_hex_string(self):
        assert len(SCHEMA_FINGERPRINT) == 16
        int(SCHEMA_FINGERPRINT, 16)  # Should not raise
