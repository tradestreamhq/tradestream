"""User channel preference management for signal delivery."""

import json
from dataclasses import dataclass, field, asdict
from datetime import time
from typing import Optional


@dataclass
class ChannelPreference:
    """Per-channel configuration for a user."""

    channel: str
    channel_id: str  # recipient identifier (chat_id, webhook_url, email, phone)
    enabled: bool = True
    is_primary: bool = False
    min_opportunity_score: int = 60
    symbols: list[str] = field(default_factory=list)  # empty = all symbols
    actions: list[str] = field(default_factory=list)  # empty = all actions
    quiet_hours_start: Optional[str] = None  # HH:MM format
    quiet_hours_end: Optional[str] = None
    timezone: str = "UTC"


@dataclass
class UserDeliveryPreferences:
    """Complete delivery preferences for a user."""

    user_id: str
    dedup_preference: str = "primary_only"  # primary_only, all_enabled, fallback_chain
    primary_channel: str = "telegram"
    fallback_order: list[str] = field(default_factory=lambda: ["telegram", "email"])
    tier: str = "free"
    channels: dict[str, ChannelPreference] = field(default_factory=dict)


class PreferenceStore:
    """Manages user delivery preferences in Redis.

    Stores preferences as JSON hashes for fast lookup during delivery routing.
    In production this would be backed by PostgreSQL, but Redis gives us
    fast per-signal lookups.
    """

    KEY_PREFIX = "delivery:prefs"

    def __init__(self, redis_client):
        self.redis = redis_client

    def get_preferences(self, user_id: str) -> Optional[UserDeliveryPreferences]:
        """Load user delivery preferences."""
        key = f"{self.KEY_PREFIX}:{user_id}"
        raw = self.redis.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        channels = {}
        for ch_name, ch_data in data.get("channels", {}).items():
            channels[ch_name] = ChannelPreference(**ch_data)
        return UserDeliveryPreferences(
            user_id=data["user_id"],
            dedup_preference=data.get("dedup_preference", "primary_only"),
            primary_channel=data.get("primary_channel", "telegram"),
            fallback_order=data.get("fallback_order", ["telegram", "email"]),
            tier=data.get("tier", "free"),
            channels=channels,
        )

    def save_preferences(self, prefs: UserDeliveryPreferences) -> None:
        """Save user delivery preferences."""
        key = f"{self.KEY_PREFIX}:{prefs.user_id}"
        data = {
            "user_id": prefs.user_id,
            "dedup_preference": prefs.dedup_preference,
            "primary_channel": prefs.primary_channel,
            "fallback_order": prefs.fallback_order,
            "tier": prefs.tier,
            "channels": {name: asdict(ch) for name, ch in prefs.channels.items()},
        }
        self.redis.set(key, json.dumps(data))

    def set_channel(self, user_id: str, channel_pref: ChannelPreference) -> None:
        """Add or update a channel for a user."""
        prefs = self.get_preferences(user_id)
        if prefs is None:
            prefs = UserDeliveryPreferences(user_id=user_id)
        prefs.channels[channel_pref.channel] = channel_pref
        if channel_pref.is_primary:
            prefs.primary_channel = channel_pref.channel
        self.save_preferences(prefs)

    def remove_channel(self, user_id: str, channel: str) -> None:
        """Disable a channel for a user."""
        prefs = self.get_preferences(user_id)
        if prefs and channel in prefs.channels:
            del prefs.channels[channel]
            self.save_preferences(prefs)

    def get_enabled_channels(self, user_id: str) -> list[ChannelPreference]:
        """Get all enabled channels for a user."""
        prefs = self.get_preferences(user_id)
        if not prefs:
            return []
        return [ch for ch in prefs.channels.values() if ch.enabled]
