"""Data models for the alert rules engine."""

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum


class ConditionType(str, Enum):
    """Types of conditions that can trigger an alert."""

    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    DRAWDOWN_EXCEEDS = "drawdown_exceeds"
    PORTFOLIO_HEAT_EXCEEDS = "portfolio_heat_exceeds"
    SIGNAL_MATCH = "signal_match"
    REGIME_CHANGE = "regime_change"


class ActionType(str, Enum):
    """Types of actions to take when an alert triggers."""

    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


@dataclass
class AlertCondition:
    """A single condition that must be met to trigger an alert.

    Attributes:
        condition_type: The type of condition to evaluate.
        params: Condition-specific parameters. Examples:
            - price_above: {"symbol": "BTC/USD", "threshold": 50000.0}
            - price_below: {"symbol": "BTC/USD", "threshold": 40000.0}
            - drawdown_exceeds: {"threshold": 0.05}
            - portfolio_heat_exceeds: {"threshold": 0.25}
            - signal_match: {"symbol": "BTC/USD", "action": "BUY"}
            - regime_change: {"from_regime": "trending", "to_regime": "volatile"}
    """

    condition_type: ConditionType
    params: dict = field(default_factory=dict)


@dataclass
class AlertAction:
    """An action to perform when an alert fires.

    Attributes:
        action_type: How to deliver the notification.
        params: Action-specific parameters. Examples:
            - webhook: {"url": "https://...", "secret": "..."}
            - email: {"to": "user@example.com"}
            - sms: {"phone": "+1234567890"}
            - in_app: {"channel": "alerts"}
    """

    action_type: ActionType
    params: dict = field(default_factory=dict)


@dataclass
class AlertRule:
    """A complete alert rule: condition + action + cooldown.

    Attributes:
        rule_id: Unique identifier for the rule.
        name: Human-readable name for the rule.
        condition: The condition that triggers this rule.
        action: The action to take when the condition is met.
        cooldown_seconds: Minimum seconds between firings to prevent spam.
        enabled: Whether this rule is currently active.
        created_at: Unix timestamp of rule creation.
        last_triggered_at: Unix timestamp of last firing (0 if never).
    """

    rule_id: str
    name: str
    condition: AlertCondition
    action: AlertAction
    cooldown_seconds: int = 300
    enabled: bool = True
    created_at: float = 0.0
    last_triggered_at: float = 0.0

    def __post_init__(self):
        if not self.rule_id:
            self.rule_id = uuid.uuid4().hex[:16]
        if not self.created_at:
            self.created_at = time.time()

    def is_in_cooldown(self, now: float | None = None) -> bool:
        """Check if this rule is still in its cooldown period."""
        if self.last_triggered_at == 0.0:
            return False
        now = now or time.time()
        return (now - self.last_triggered_at) < self.cooldown_seconds

    def to_dict(self) -> dict:
        """Serialize to a plain dict for storage."""
        d = asdict(self)
        d["condition"]["condition_type"] = self.condition.condition_type.value
        d["action"]["action_type"] = self.action.action_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AlertRule":
        """Deserialize from a plain dict."""
        condition = AlertCondition(
            condition_type=ConditionType(data["condition"]["condition_type"]),
            params=data["condition"].get("params", {}),
        )
        action = AlertAction(
            action_type=ActionType(data["action"]["action_type"]),
            params=data["action"].get("params", {}),
        )
        return cls(
            rule_id=data["rule_id"],
            name=data["name"],
            condition=condition,
            action=action,
            cooldown_seconds=data.get("cooldown_seconds", 300),
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", 0.0),
            last_triggered_at=data.get("last_triggered_at", 0.0),
        )


@dataclass
class AlertEvent:
    """Record of a triggered alert."""

    event_id: str
    rule_id: str
    rule_name: str
    condition_type: str
    message: str
    context: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:16]
        if not self.timestamp:
            self.timestamp = time.time()
