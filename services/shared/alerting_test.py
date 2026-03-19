"""Tests for the alerting rules engine."""

import time

import pytest

from services.shared.alerting import (
    Alert,
    AlertEvaluator,
    AlertRule,
    AlertSeverity,
    _check_delivery_failure_rate,
    _check_dlq_buildup,
    _check_signal_generation_stopped,
    _check_stripe_webhook_failures,
    _check_telegram_circuit_open,
)


class TestAlertRuleChecks:
    def test_signal_generation_stopped_fires_when_zero(self):
        result = _check_signal_generation_stopped(
            {"signal_generation": {"total": 0}}
        )
        assert result == (0, 1)

    def test_signal_generation_ok(self):
        result = _check_signal_generation_stopped(
            {"signal_generation": {"total": 10}}
        )
        assert result is None

    def test_delivery_failure_rate_fires(self):
        result = _check_delivery_failure_rate(
            {"delivery": {"attempted": 100, "success_rate": 0.90}}
        )
        assert result is not None
        metric_value, threshold = result
        assert metric_value == 0.1  # 10% failure rate
        assert threshold == 0.05

    def test_delivery_failure_rate_ok(self):
        result = _check_delivery_failure_rate(
            {"delivery": {"attempted": 100, "success_rate": 0.98}}
        )
        assert result is None

    def test_delivery_failure_rate_insufficient_samples(self):
        result = _check_delivery_failure_rate(
            {"delivery": {"attempted": 5, "success_rate": 0.5}}
        )
        assert result is None

    def test_stripe_webhook_failures_fires(self):
        result = _check_stripe_webhook_failures(
            {"stripe_webhooks": {"received": 20, "failed": 5}}
        )
        assert result is not None
        metric_value, threshold = result
        assert metric_value == 0.25

    def test_stripe_webhook_failures_ok(self):
        result = _check_stripe_webhook_failures(
            {"stripe_webhooks": {"received": 100, "failed": 2}}
        )
        assert result is None

    def test_stripe_webhook_insufficient_samples(self):
        result = _check_stripe_webhook_failures(
            {"stripe_webhooks": {"received": 3, "failed": 1}}
        )
        assert result is None

    def test_telegram_circuit_open_fires(self):
        result = _check_telegram_circuit_open(
            {"telegram": {"circuit_breaker_trips": 2}}
        )
        assert result == (2, 0)

    def test_telegram_circuit_ok(self):
        result = _check_telegram_circuit_open(
            {"telegram": {"circuit_breaker_trips": 0}}
        )
        assert result is None

    def test_dlq_buildup_fires(self):
        result = _check_dlq_buildup(
            {"dead_letter_queue": {"enqueued": 100, "retried": 10}}
        )
        assert result is not None
        assert result[0] == 90

    def test_dlq_buildup_ok(self):
        result = _check_dlq_buildup(
            {"dead_letter_queue": {"enqueued": 30, "retried": 20}}
        )
        assert result is None


class TestAlert:
    def test_to_dict(self):
        alert = Alert(
            rule_name="test_rule",
            severity=AlertSeverity.CRITICAL,
            message="Test alert",
            metric_value=0.15,
            threshold=0.05,
            fired_at=1000.0,
        )
        d = alert.to_dict()
        assert d["rule"] == "test_rule"
        assert d["severity"] == "critical"
        assert d["metric_value"] == 0.15
        assert d["threshold"] == 0.05

    def test_to_json(self):
        alert = Alert(
            rule_name="test",
            severity=AlertSeverity.WARNING,
            message="warn",
            metric_value=1,
            threshold=0,
        )
        j = alert.to_json()
        assert '"rule": "test"' in j


class TestAlertRule:
    def test_evaluate_fires(self):
        rule = AlertRule(
            name="test",
            severity=AlertSeverity.CRITICAL,
            message_template="Value {value} exceeds {threshold}",
            evaluate_fn=lambda snap: (10, 5),
        )
        alert = rule.evaluate({})
        assert alert is not None
        assert alert.rule_name == "test"
        assert alert.metric_value == 10

    def test_evaluate_no_fire(self):
        rule = AlertRule(
            name="test",
            severity=AlertSeverity.WARNING,
            message_template="",
            evaluate_fn=lambda snap: None,
        )
        assert rule.evaluate({}) is None

    def test_cooldown(self):
        rule = AlertRule(
            name="test",
            severity=AlertSeverity.CRITICAL,
            message_template="{value} > {threshold}",
            evaluate_fn=lambda snap: (10, 5),
        )
        rule._cooldown = 300
        alert1 = rule.evaluate({})
        assert alert1 is not None
        alert2 = rule.evaluate({})
        assert alert2 is None  # In cooldown


class TestAlertEvaluator:
    def test_evaluates_all_rules(self):
        evaluator = AlertEvaluator()
        snapshot = {
            "signal_generation": {"total": 0},
            "delivery": {"attempted": 100, "success_rate": 0.90},
            "stripe_webhooks": {"received": 20, "failed": 5},
            "telegram": {"circuit_breaker_trips": 1},
            "dead_letter_queue": {"enqueued": 100, "retried": 10},
        }
        alerts = evaluator.evaluate(snapshot)
        rule_names = {a.rule_name for a in alerts}
        assert "signal_generation_stopped" in rule_names
        assert "delivery_failure_rate_high" in rule_names
        assert "stripe_webhook_failures" in rule_names
        assert "telegram_circuit_breaker_tripped" in rule_names
        assert "dlq_buildup" in rule_names

    def test_no_alerts_when_healthy(self):
        evaluator = AlertEvaluator()
        snapshot = {
            "signal_generation": {"total": 50},
            "delivery": {"attempted": 100, "success_rate": 0.99},
            "stripe_webhooks": {"received": 50, "failed": 0},
            "telegram": {"circuit_breaker_trips": 0},
            "dead_letter_queue": {"enqueued": 10, "retried": 5},
        }
        alerts = evaluator.evaluate(snapshot)
        assert len(alerts) == 0

    def test_custom_rules(self):
        custom_rule = AlertRule(
            name="custom",
            severity=AlertSeverity.WARNING,
            message_template="Custom: {value}",
            evaluate_fn=lambda snap: (1, 0) if snap.get("custom") else None,
        )
        evaluator = AlertEvaluator(rules=[custom_rule])
        alerts = evaluator.evaluate({"custom": True})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "custom"

    def test_handles_evaluation_error(self):
        def bad_fn(snap):
            raise ValueError("boom")

        rule = AlertRule(
            name="bad",
            severity=AlertSeverity.CRITICAL,
            message_template="",
            evaluate_fn=bad_fn,
        )
        evaluator = AlertEvaluator(rules=[rule])
        alerts = evaluator.evaluate({})
        assert len(alerts) == 0  # Error is caught, no alert
