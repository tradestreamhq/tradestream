"""Tests for the alert evaluation engine."""

from decimal import Decimal

import pytest

from services.alert_api.engine import (
    AlertEvent,
    AlertRule,
    TriggeredAlert,
    evaluate_rule,
    evaluate_rules,
)


def _rule(
    condition_type="drawdown_exceeded",
    threshold=Decimal("10"),
    strategy_id=None,
    implementation_id=None,
    is_active=True,
    name="test-rule",
):
    return AlertRule(
        id="rule-1",
        name=name,
        condition_type=condition_type,
        threshold=threshold,
        strategy_id=strategy_id,
        implementation_id=implementation_id,
        notification_channels=["in_app"],
        is_active=is_active,
    )


class TestEvaluateRule:
    def test_inactive_rule_never_triggers(self):
        rule = _rule(is_active=False)
        event = AlertEvent(event_type="drawdown_exceeded", value=Decimal("20"))
        assert evaluate_rule(rule, event) is None

    def test_mismatched_event_type_does_not_trigger(self):
        rule = _rule(condition_type="drawdown_exceeded")
        event = AlertEvent(event_type="pnl_target", value=Decimal("20"))
        assert evaluate_rule(rule, event) is None

    def test_drawdown_exceeded_triggers_at_threshold(self):
        rule = _rule(condition_type="drawdown_exceeded", threshold=Decimal("10"))
        event = AlertEvent(event_type="drawdown_exceeded", value=Decimal("10"))
        result = evaluate_rule(rule, event)
        assert result is not None
        assert result.triggered_value == Decimal("10")
        assert "Drawdown" in result.message

    def test_drawdown_exceeded_triggers_above_threshold(self):
        rule = _rule(condition_type="drawdown_exceeded", threshold=Decimal("10"))
        event = AlertEvent(event_type="drawdown_exceeded", value=Decimal("15"))
        result = evaluate_rule(rule, event)
        assert result is not None

    def test_drawdown_below_threshold_does_not_trigger(self):
        rule = _rule(condition_type="drawdown_exceeded", threshold=Decimal("10"))
        event = AlertEvent(event_type="drawdown_exceeded", value=Decimal("5"))
        assert evaluate_rule(rule, event) is None

    def test_pnl_target_triggers(self):
        rule = _rule(condition_type="pnl_target", threshold=Decimal("1000"))
        event = AlertEvent(event_type="pnl_target", value=Decimal("1500"))
        result = evaluate_rule(rule, event)
        assert result is not None
        assert "PnL" in result.message

    def test_pnl_target_below_threshold_does_not_trigger(self):
        rule = _rule(condition_type="pnl_target", threshold=Decimal("1000"))
        event = AlertEvent(event_type="pnl_target", value=Decimal("500"))
        assert evaluate_rule(rule, event) is None

    def test_signal_generated_always_triggers(self):
        rule = _rule(condition_type="signal_generated", threshold=None)
        event = AlertEvent(
            event_type="signal_generated",
            metadata={"signal_type": "BUY", "instrument": "BTC/USD"},
        )
        result = evaluate_rule(rule, event)
        assert result is not None
        assert "signal" in result.message.lower()

    def test_consecutive_losses_triggers(self):
        rule = _rule(condition_type="consecutive_losses", threshold=Decimal("5"))
        event = AlertEvent(event_type="consecutive_losses", value=Decimal("7"))
        result = evaluate_rule(rule, event)
        assert result is not None
        assert "consecutive losses" in result.message.lower()

    def test_consecutive_losses_below_threshold(self):
        rule = _rule(condition_type="consecutive_losses", threshold=Decimal("5"))
        event = AlertEvent(event_type="consecutive_losses", value=Decimal("3"))
        assert evaluate_rule(rule, event) is None

    def test_strategy_id_filter_matches(self):
        rule = _rule(strategy_id="strat-1")
        event = AlertEvent(
            event_type="drawdown_exceeded",
            value=Decimal("20"),
            strategy_id="strat-1",
        )
        assert evaluate_rule(rule, event) is not None

    def test_strategy_id_filter_rejects(self):
        rule = _rule(strategy_id="strat-1")
        event = AlertEvent(
            event_type="drawdown_exceeded",
            value=Decimal("20"),
            strategy_id="strat-2",
        )
        assert evaluate_rule(rule, event) is None

    def test_implementation_id_filter_matches(self):
        rule = _rule(implementation_id="impl-1")
        event = AlertEvent(
            event_type="drawdown_exceeded",
            value=Decimal("20"),
            implementation_id="impl-1",
        )
        assert evaluate_rule(rule, event) is not None

    def test_implementation_id_filter_rejects(self):
        rule = _rule(implementation_id="impl-1")
        event = AlertEvent(
            event_type="drawdown_exceeded",
            value=Decimal("20"),
            implementation_id="impl-2",
        )
        assert evaluate_rule(rule, event) is None

    def test_metadata_is_passed_through(self):
        rule = _rule(condition_type="signal_generated")
        event = AlertEvent(
            event_type="signal_generated",
            metadata={"instrument": "ETH/USD"},
        )
        result = evaluate_rule(rule, event)
        assert result is not None
        assert result.metadata == {"instrument": "ETH/USD"}


class TestEvaluateRules:
    def test_multiple_rules_multiple_triggers(self):
        rules = [
            _rule(
                name="dd-rule",
                condition_type="drawdown_exceeded",
                threshold=Decimal("5"),
            ),
            _rule(
                name="pnl-rule", condition_type="pnl_target", threshold=Decimal("100")
            ),
            _rule(name="sig-rule", condition_type="signal_generated"),
        ]
        # Drawdown event should only match the drawdown rule
        event = AlertEvent(event_type="drawdown_exceeded", value=Decimal("10"))
        triggered = evaluate_rules(rules, event)
        assert len(triggered) == 1
        assert triggered[0].rule.name == "dd-rule"

    def test_no_rules_no_triggers(self):
        triggered = evaluate_rules([], AlertEvent(event_type="drawdown_exceeded"))
        assert triggered == []

    def test_all_inactive_no_triggers(self):
        rules = [_rule(is_active=False), _rule(is_active=False)]
        event = AlertEvent(event_type="drawdown_exceeded", value=Decimal("20"))
        assert evaluate_rules(rules, event) == []
