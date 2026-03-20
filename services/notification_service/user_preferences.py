"""User delivery preferences stored in Redis."""

import json
from dataclasses import asdict, dataclass, field


@dataclass
class QuietHours:
    """Time window during which notifications are suppressed."""

    enabled: bool = False
    start_hour: int = 22  # 10 PM
    end_hour: int = 8  # 8 AM
    timezone: str = "UTC"


@dataclass
class ChannelPreference:
    """Per-channel settings for a user."""

    enabled: bool = True
    min_confidence: float = 0.0  # channel-specific threshold
    actions: list[str] = field(default_factory=list)  # empty = all actions
    symbols: list[str] = field(default_factory=list)  # empty = all symbols


@dataclass
class UserDeliveryPreferences:
    """Complete delivery preferences for a user."""

    user_id: str
    primary_channel: str = "telegram"
    delivery_mode: str = "primary_only"  # primary_only, all_enabled, fallback_chain
    tier: str = "free"
    quiet_hours: QuietHours = field(default_factory=QuietHours)
    channels: dict[str, ChannelPreference] = field(default_factory=dict)

    def is_channel_enabled(self, channel: str) -> bool:
        pref = self.channels.get(channel)
        if pref is None:
            return channel == self.primary_channel
        return pref.enabled

    def get_channel_pref(self, channel: str) -> ChannelPreference:
        return self.channels.get(channel, ChannelPreference())

    def passes_channel_filter(self, channel: str, signal: dict) -> bool:
        """Check if a signal passes channel-specific filters."""
        pref = self.get_channel_pref(channel)
        confidence = signal.get("confidence", 0)
        if confidence < pref.min_confidence:
            return False
        if pref.actions:
            action = signal.get("action", "")
            if action and action not in pref.actions:
                return False
        if pref.symbols:
            symbol = signal.get("symbol", "")
            if symbol and symbol not in pref.symbols:
                return False
        return True


class UserPreferencesStore:
    """Redis-backed user preferences store."""

    KEY_PREFIX = "user_prefs"
    TTL_SECONDS = 86400 * 30  # 30 days

    def __init__(self, redis_client):
        self.redis = redis_client

    def get(self, user_id: str) -> UserDeliveryPreferences:
        """Load preferences for a user. Returns defaults if none stored."""
        key = f"{self.KEY_PREFIX}:{user_id}"
        raw = self.redis.get(key)
        if not raw:
            return UserDeliveryPreferences(user_id=user_id)
        try:
            data = json.loads(raw)
            return self._from_dict(user_id, data)
        except (json.JSONDecodeError, KeyError):
            return UserDeliveryPreferences(user_id=user_id)

    def save(self, prefs: UserDeliveryPreferences):
        """Persist user preferences to Redis."""
        key = f"{self.KEY_PREFIX}:{prefs.user_id}"
        data = {
            "primary_channel": prefs.primary_channel,
            "delivery_mode": prefs.delivery_mode,
            "tier": prefs.tier,
            "quiet_hours": asdict(prefs.quiet_hours),
            "channels": {k: asdict(v) for k, v in prefs.channels.items()},
        }
        self.redis.setex(key, self.TTL_SECONDS, json.dumps(data))

    def _from_dict(self, user_id: str, data: dict) -> UserDeliveryPreferences:
        qh_data = data.get("quiet_hours", {})
        quiet_hours = QuietHours(
            enabled=qh_data.get("enabled", False),
            start_hour=qh_data.get("start_hour", 22),
            end_hour=qh_data.get("end_hour", 8),
            timezone=qh_data.get("timezone", "UTC"),
        )
        channels = {}
        for ch_name, ch_data in data.get("channels", {}).items():
            channels[ch_name] = ChannelPreference(
                enabled=ch_data.get("enabled", True),
                min_confidence=ch_data.get("min_confidence", 0.0),
                actions=ch_data.get("actions", []),
                symbols=ch_data.get("symbols", []),
            )
        return UserDeliveryPreferences(
            user_id=user_id,
            primary_channel=data.get("primary_channel", "telegram"),
            delivery_mode=data.get("delivery_mode", "primary_only"),
            tier=data.get("tier", "free"),
            quiet_hours=quiet_hours,
            channels=channels,
        )
