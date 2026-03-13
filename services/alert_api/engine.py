"""Alert evaluation engine.

Evaluates alert rules against incoming trading events and records
triggered alerts in the alert_history table.
"""

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AlertEvent:
    """An incoming event to evaluate against alert rules."""

    event_type: str  # matches condition_type
    value: Optional[Decimal] = None
    strategy_id: Optional[str] = None
    implementation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AlertRule:
    """An alert rule loaded from the database."""

    id: str
    name: str
    condition_type: str
    threshold: Optional[Decimal]
    strategy_id: Optional[str]
    implementation_id: Optional[str]
    notification_channels: List[str]
    is_active: bool


@dataclass
class TriggeredAlert:
    """Result of a rule evaluation that matched."""

    rule: AlertRule
    triggered_value: Optional[Decimal]
    message: str
    metadata: Optional[Dict[str, Any]] = None


def evaluate_rule(rule: AlertRule, event: AlertEvent) -> Optional[TriggeredAlert]:
    """Evaluate a single rule against an event.

    Returns a TriggeredAlert if the rule matches, None otherwise.
    """
    if not rule.is_active:
        return None

    if rule.condition_type != event.event_type:
        return None

    # Filter by strategy if the rule is scoped to one
    if rule.strategy_id and event.strategy_id != rule.strategy_id:
        return None
    if rule.implementation_id and event.implementation_id != rule.implementation_id:
        return None

    if rule.condition_type == "drawdown_exceeded":
        if event.value is not None and rule.threshold is not None:
            if event.value >= rule.threshold:
                return TriggeredAlert(
                    rule=rule,
                    triggered_value=event.value,
                    message=(
                        f"Drawdown {event.value}% exceeded threshold "
                        f"{rule.threshold}% for rule '{rule.name}'"
                    ),
                    metadata=event.metadata,
                )

    elif rule.condition_type == "pnl_target":
        if event.value is not None and rule.threshold is not None:
            if event.value >= rule.threshold:
                return TriggeredAlert(
                    rule=rule,
                    triggered_value=event.value,
                    message=(
                        f"PnL {event.value} reached target "
                        f"{rule.threshold} for rule '{rule.name}'"
                    ),
                    metadata=event.metadata,
                )

    elif rule.condition_type == "signal_generated":
        # Signal alerts trigger whenever a matching signal event arrives
        return TriggeredAlert(
            rule=rule,
            triggered_value=event.value,
            message=f"New signal generated for rule '{rule.name}'",
            metadata=event.metadata,
        )

    elif rule.condition_type == "consecutive_losses":
        if event.value is not None and rule.threshold is not None:
            if event.value >= rule.threshold:
                return TriggeredAlert(
                    rule=rule,
                    triggered_value=event.value,
                    message=(
                        f"{int(event.value)} consecutive losses reached threshold "
                        f"{int(rule.threshold)} for rule '{rule.name}'"
                    ),
                    metadata=event.metadata,
                )

    return None


def evaluate_rules(rules: List[AlertRule], event: AlertEvent) -> List[TriggeredAlert]:
    """Evaluate all rules against an event, returning any that triggered."""
    triggered = []
    for rule in rules:
        result = evaluate_rule(rule, event)
        if result is not None:
            triggered.append(result)
    return triggered


class AlertEngine:
    """Evaluates alert rules against events using a database connection pool."""

    def __init__(self, db_pool):
        self._pool = db_pool

    async def load_active_rules(self) -> List[AlertRule]:
        """Load all active alert rules from the database."""
        query = """
            SELECT id, name, condition_type, threshold, strategy_id,
                   implementation_id, notification_channels, is_active
            FROM alert_rules
            WHERE is_active = TRUE
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)

        return [
            AlertRule(
                id=str(row["id"]),
                name=row["name"],
                condition_type=row["condition_type"],
                threshold=row["threshold"],
                strategy_id=str(row["strategy_id"]) if row["strategy_id"] else None,
                implementation_id=(
                    str(row["implementation_id"]) if row["implementation_id"] else None
                ),
                notification_channels=list(row["notification_channels"]),
                is_active=row["is_active"],
            )
            for row in rows
        ]

    async def process_event(self, event: AlertEvent) -> List[TriggeredAlert]:
        """Load rules, evaluate against event, and persist triggered alerts."""
        rules = await self.load_active_rules()
        triggered = evaluate_rules(rules, event)

        for alert in triggered:
            await self._record_triggered_alert(alert)

        return triggered

    async def _record_triggered_alert(self, alert: TriggeredAlert) -> None:
        """Insert a triggered alert into alert_history."""
        query = """
            INSERT INTO alert_history (rule_id, triggered_value, message, metadata)
            VALUES ($1::uuid, $2, $3, $4::jsonb)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                query,
                alert.rule.id,
                alert.triggered_value,
                alert.message,
                json.dumps(alert.metadata) if alert.metadata else None,
            )
