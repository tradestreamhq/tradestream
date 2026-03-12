"""Data models for the alert routing service."""

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ChannelType(str, enum.Enum):
    EMAIL = "email"
    SLACK_WEBHOOK = "slack_webhook"
    CUSTOM_WEBHOOK = "custom_webhook"
    IN_APP = "in_app"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ChannelConfig:
    """Configuration for a single delivery channel."""

    channel_type: ChannelType
    name: str
    enabled: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_type": self.channel_type.value,
            "name": self.name,
            "enabled": self.enabled,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelConfig":
        return cls(
            channel_type=ChannelType(data["channel_type"]),
            name=data["name"],
            enabled=data.get("enabled", True),
            settings=data.get("settings", {}),
        )


@dataclass
class RoutingRule:
    """Maps an alert type to one or more channels."""

    alert_type: str
    channel_names: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_type": self.alert_type,
            "channel_names": self.channel_names,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingRule":
        return cls(
            alert_type=data["alert_type"],
            channel_names=data["channel_names"],
        )


@dataclass
class RouteConfig:
    """Per-user routing configuration."""

    user_id: str
    channels: List[ChannelConfig] = field(default_factory=list)
    rules: List[RoutingRule] = field(default_factory=list)
    default_channels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "channels": [c.to_dict() for c in self.channels],
            "rules": [r.to_dict() for r in self.rules],
            "default_channels": self.default_channels,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouteConfig":
        return cls(
            user_id=data["user_id"],
            channels=[ChannelConfig.from_dict(c) for c in data.get("channels", [])],
            rules=[RoutingRule.from_dict(r) for r in data.get("rules", [])],
            default_channels=data.get("default_channels", []),
        )


@dataclass
class Alert:
    """An alert to be routed."""

    alert_type: str
    title: str
    message: str
    user_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type,
            "title": self.title,
            "message": self.message,
            "user_id": self.user_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


@dataclass
class DeliveryRecord:
    """Tracks a single delivery attempt."""

    alert_id: str
    channel_name: str
    channel_type: str
    status: DeliveryStatus
    user_id: str
    attempt: int = 1
    error: Optional[str] = None
    delivered_at: Optional[float] = None
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "alert_id": self.alert_id,
            "channel_name": self.channel_name,
            "channel_type": self.channel_type,
            "status": self.status.value,
            "user_id": self.user_id,
            "attempt": self.attempt,
            "error": self.error,
            "delivered_at": self.delivered_at,
            "created_at": self.created_at,
        }
