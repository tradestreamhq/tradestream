"""Redis-backed storage for alert rules."""

import json

from services.alert_rules_engine.models import AlertRule


class RuleStore:
    """CRUD operations for alert rules stored in Redis.

    Rules are stored as individual hash entries under a single Redis key,
    enabling atomic reads and writes without scanning.
    """

    RULES_KEY = "alert_rules"
    EVENTS_KEY = "alert_events:recent"
    MAX_EVENTS = 500
    EVENTS_TTL = 86400 * 7  # 7 days

    def __init__(self, redis_client):
        self.redis = redis_client

    def create(self, rule: AlertRule) -> AlertRule:
        """Create a new alert rule."""
        self.redis.hset(self.RULES_KEY, rule.rule_id, json.dumps(rule.to_dict()))
        return rule

    def get(self, rule_id: str) -> AlertRule | None:
        """Get a single rule by ID."""
        raw = self.redis.hget(self.RULES_KEY, rule_id)
        if raw is None:
            return None
        return AlertRule.from_dict(json.loads(raw))

    def list_all(self) -> list[AlertRule]:
        """List all rules."""
        raw_map = self.redis.hgetall(self.RULES_KEY)
        rules = []
        for raw in raw_map.values():
            rules.append(AlertRule.from_dict(json.loads(raw)))
        return rules

    def list_enabled(self) -> list[AlertRule]:
        """List only enabled rules."""
        return [r for r in self.list_all() if r.enabled]

    def update(self, rule: AlertRule) -> AlertRule:
        """Update an existing rule."""
        self.redis.hset(self.RULES_KEY, rule.rule_id, json.dumps(rule.to_dict()))
        return rule

    def delete(self, rule_id: str) -> bool:
        """Delete a rule. Returns True if it existed."""
        return self.redis.hdel(self.RULES_KEY, rule_id) > 0

    def mark_triggered(self, rule: AlertRule, timestamp: float) -> AlertRule:
        """Update the last_triggered_at timestamp for a rule."""
        rule.last_triggered_at = timestamp
        self.update(rule)
        return rule

    def record_event(self, event_dict: dict) -> None:
        """Record an alert event in the recent events list."""
        data = json.dumps(event_dict, default=str)
        pipe = self.redis.pipeline()
        pipe.lpush(self.EVENTS_KEY, data)
        pipe.ltrim(self.EVENTS_KEY, 0, self.MAX_EVENTS - 1)
        pipe.expire(self.EVENTS_KEY, self.EVENTS_TTL)
        pipe.execute()

    def get_recent_events(self, count: int = 50) -> list[dict]:
        """Return recent alert events."""
        raw = self.redis.lrange(self.EVENTS_KEY, 0, count - 1)
        return [json.loads(r) for r in raw]
