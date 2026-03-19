"""Tests for the Parameter Adapter."""

from unittest import mock

import pytest

from services.learning_engine.parameter_adapter import (
    DEFAULT_ADAPTATION_RULES,
    ParameterAdapter,
)


class TestAdaptParameters:
    def setup_method(self):
        self.adapter = ParameterAdapter()

    def test_volatile_regime_widens_stops(self):
        params = {
            "stop_loss_percent": 2.0,
            "take_profit_percent": 4.0,
            "position_size_percent": 10.0,
            "lookback_period": 14,
            "other_param": "untouched",
        }
        result = self.adapter.adapt_parameters(
            "spec-1", params, "volatile", "BTC-USD"
        )
        adapted = result["adapted_parameters"]

        # Stop loss should be wider (multiplied by 1.5)
        assert adapted["stop_loss_percent"] == 3.0
        # Take profit also wider
        assert adapted["take_profit_percent"] == 5.2
        # Position size reduced
        assert adapted["position_size_percent"] == 7.0
        # Lookback shortened
        assert adapted["lookback_period"] == 11.2
        # Non-adaptable param untouched
        assert adapted["other_param"] == "untouched"
        assert len(result["rules_applied"]) == 4

    def test_quiet_regime_tightens_stops(self):
        params = {"stop_loss_percent": 2.0, "position_size_percent": 10.0}
        result = self.adapter.adapt_parameters(
            "spec-1", params, "quiet", "BTC-USD"
        )
        adapted = result["adapted_parameters"]
        assert adapted["stop_loss_percent"] < 2.0
        assert adapted["position_size_percent"] > 10.0

    def test_trending_up_extends_targets(self):
        params = {"take_profit_percent": 4.0, "stop_loss_percent": 2.0}
        result = self.adapter.adapt_parameters(
            "spec-1", params, "trending_up", "ETH-USD"
        )
        adapted = result["adapted_parameters"]
        assert adapted["take_profit_percent"] == 6.0  # 4.0 * 1.5

    def test_unknown_regime_no_change(self):
        params = {"stop_loss_percent": 2.0}
        result = self.adapter.adapt_parameters(
            "spec-1", params, "unknown_regime", "BTC-USD"
        )
        assert result["adapted_parameters"] == params
        assert result["rules_applied"] == []

    def test_non_numeric_param_skipped(self):
        params = {"stop_loss": "dynamic", "take_profit": 5.0}
        result = self.adapter.adapt_parameters(
            "spec-1", params, "volatile", "BTC-USD"
        )
        adapted = result["adapted_parameters"]
        assert adapted["stop_loss"] == "dynamic"
        assert adapted["take_profit"] == 7.5

    def test_stores_adaptation_with_db(self):
        conn = mock.Mock()
        cur = mock.Mock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        adapter = ParameterAdapter(db_connection=conn)
        params = {"stop_loss_percent": 2.0}
        adapter.adapt_parameters("spec-1", params, "volatile", "BTC-USD")

        assert cur.execute.call_count == 2  # UPDATE + INSERT
        conn.commit.assert_called_once()

    def test_no_store_without_changes(self):
        conn = mock.Mock()
        adapter = ParameterAdapter(db_connection=conn)
        params = {"unmatchable_key": 42}
        adapter.adapt_parameters("spec-1", params, "volatile", "BTC-USD")
        conn.cursor.assert_not_called()


class TestCustomRules:
    def test_custom_multipliers(self):
        rules = {
            "volatile": {
                "stop_loss_multiplier": 2.0,
                "take_profit_multiplier": 2.0,
                "description": "Double everything",
            }
        }
        adapter = ParameterAdapter(rules=rules)
        params = {"stop_loss": 1.0, "take_profit": 2.0}
        result = adapter.adapt_parameters("spec-1", params, "volatile", "BTC-USD")
        assert result["adapted_parameters"]["stop_loss"] == 2.0
        assert result["adapted_parameters"]["take_profit"] == 4.0


class TestAdaptableKeys:
    def setup_method(self):
        self.adapter = ParameterAdapter()

    def test_all_adaptable_key_variants(self):
        params = {
            "stop_loss": 1.0,
            "stop_loss_percent": 2.0,
            "take_profit": 3.0,
            "take_profit_percent": 4.0,
            "position_size": 5.0,
            "position_size_percent": 6.0,
            "lookback_period": 7,
            "lookback": 8,
            "period": 9,
            "window": 10,
        }
        result = self.adapter.adapt_parameters("spec-1", params, "volatile", "BTC-USD")
        # All 10 keys should be adapted
        assert len(result["rules_applied"]) == 10


class TestRevert:
    def test_revert_no_connection(self):
        adapter = ParameterAdapter()
        assert adapter.revert_adaptation("spec-1", "BTC-USD") is False

    def test_revert_with_connection(self):
        conn = mock.Mock()
        cur = mock.Mock()
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        adapter = ParameterAdapter(db_connection=conn)
        result = adapter.revert_adaptation("spec-1", "BTC-USD")
        assert result is True
        conn.commit.assert_called_once()


class TestGetAdaptedParameters:
    def test_no_connection(self):
        adapter = ParameterAdapter()
        assert adapter.get_adapted_parameters("spec-1", "BTC-USD") is None

    def test_no_active_adaptation(self):
        conn = mock.Mock()
        cur = mock.Mock()
        cur.fetchone.return_value = None
        conn.cursor.return_value.__enter__ = mock.Mock(return_value=cur)
        conn.cursor.return_value.__exit__ = mock.Mock(return_value=False)

        adapter = ParameterAdapter(db_connection=conn)
        assert adapter.get_adapted_parameters("spec-1", "BTC-USD") is None
