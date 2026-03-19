"""Alerting rules for the signal pipeline.

Evaluates pipeline metrics against thresholds and emits structured alerts.
Designed to be called periodically (e.g., every 60 seconds) by a monitoring loop.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    rule_name: str
    severity: AlertSeverity
    message: str
    metric_value: float
    threshold: float
    fired_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "rule": self.rule_name,
            "severity": self.severity.value,
            "message": self.message,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "fired_at": self.fired_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class AlertRule:
    """A single alerting rule that evaluates a condition against pipeline metrics."""

    def __init__(
        self,
        name: str,
        severity: AlertSeverity,
        message_template: str,
        evaluate_fn,
    ):
        self.name = name
        self.severity = severity
        self.message_template = message_template
        self.evaluate_fn = evaluate_fn
        self._last_fired = 0.0
        self._cooldown = 300.0  # 5 min cooldown between repeated alerts

    def evaluate(self, metrics_snapshot: dict) -> Alert | None:
        """Evaluate this rule against a metrics snapshot.

        Returns an Alert if the rule fires, None otherwise.
        """
        result = self.evaluate_fn(metrics_snapshot)
        if result is None:
            return None

        metric_value, threshold = result
        now = time.time()
        if now - self._last_fired < self._cooldown:
            return None  # Still in cooldown

        self._last_fired = now
        return Alert(
            rule_name=self.name,
            severity=self.severity,
            message=self.message_template.format(
                value=metric_value, threshold=threshold
            ),
            metric_value=metric_value,
            threshold=threshold,
        )


def _check_signal_generation_stopped(snapshot: dict):
    """Alert if no signals have been generated (total == 0 after startup)."""
    total = snapshot.get("signal_generation", {}).get("total", 0)
    # Only meaningful after the system has had time to generate signals
    if total == 0:
        return (0, 1)
    return None


def _check_delivery_failure_rate(snapshot: dict):
    """Alert if delivery failure rate exceeds 5%."""
    delivery = snapshot.get("delivery", {})
    attempted = delivery.get("attempted", 0)
    if attempted < 10:  # Need minimum sample size
        return None
    success_rate = delivery.get("success_rate", 1.0)
    failure_rate = 1.0 - success_rate
    threshold = 0.05
    if failure_rate > threshold:
        return (round(failure_rate, 4), threshold)
    return None


def _check_stripe_webhook_failures(snapshot: dict):
    """Alert if Stripe webhook processing has failures."""
    webhooks = snapshot.get("stripe_webhooks", {})
    failed = webhooks.get("failed", 0)
    received = webhooks.get("received", 0)
    if received < 5:
        return None
    failure_rate = failed / received if received > 0 else 0
    threshold = 0.1
    if failure_rate > threshold:
        return (round(failure_rate, 4), threshold)
    return None


def _check_telegram_circuit_open(snapshot: dict):
    """Alert if the Telegram circuit breaker has tripped."""
    trips = snapshot.get("telegram", {}).get("circuit_breaker_trips", 0)
    if trips > 0:
        return (trips, 0)
    return None


def _check_dlq_buildup(snapshot: dict):
    """Alert if the dead letter queue is growing."""
    enqueued = snapshot.get("dead_letter_queue", {}).get("enqueued", 0)
    retried = snapshot.get("dead_letter_queue", {}).get("retried", 0)
    pending = enqueued - retried
    threshold = 50
    if pending > threshold:
        return (pending, threshold)
    return None


# Default pipeline alert rules
DEFAULT_ALERT_RULES = [
    AlertRule(
        name="signal_generation_stopped",
        severity=AlertSeverity.CRITICAL,
        message_template="Signal generation stopped: {value} signals generated (expected > {threshold})",
        evaluate_fn=_check_signal_generation_stopped,
    ),
    AlertRule(
        name="delivery_failure_rate_high",
        severity=AlertSeverity.CRITICAL,
        message_template="Delivery failure rate {value} exceeds threshold {threshold}",
        evaluate_fn=_check_delivery_failure_rate,
    ),
    AlertRule(
        name="stripe_webhook_failures",
        severity=AlertSeverity.WARNING,
        message_template="Stripe webhook failure rate {value} exceeds threshold {threshold}",
        evaluate_fn=_check_stripe_webhook_failures,
    ),
    AlertRule(
        name="telegram_circuit_breaker_tripped",
        severity=AlertSeverity.CRITICAL,
        message_template="Telegram circuit breaker has tripped {value} times",
        evaluate_fn=_check_telegram_circuit_open,
    ),
    AlertRule(
        name="dlq_buildup",
        severity=AlertSeverity.WARNING,
        message_template="Dead letter queue has {value} pending items (threshold: {threshold})",
        evaluate_fn=_check_dlq_buildup,
    ),
]


class AlertEvaluator:
    """Evaluates all alert rules against pipeline metrics.

    Usage:
        evaluator = AlertEvaluator()
        alerts = evaluator.evaluate(metrics.snapshot())
        for alert in alerts:
            logger.error(alert.to_json())
    """

    def __init__(self, rules: list[AlertRule] | None = None):
        self.rules = rules if rules is not None else list(DEFAULT_ALERT_RULES)

    def evaluate(self, metrics_snapshot: dict) -> list[Alert]:
        """Evaluate all rules and return fired alerts."""
        fired = []
        for rule in self.rules:
            try:
                alert = rule.evaluate(metrics_snapshot)
                if alert is not None:
                    fired.append(alert)
                    logger.warning(
                        "ALERT [%s] %s: %s",
                        alert.severity.value,
                        alert.rule_name,
                        alert.message,
                    )
            except Exception as e:
                logger.error("Error evaluating alert rule '%s': %s", rule.name, e)
        return fired
