"""Alert routing engine with delivery tracking and retry logic."""

import time
from typing import Any, Dict, List, Optional

from absl import logging

from services.alert_router.channels import Channel, create_channel
from services.alert_router.models import (
    Alert,
    ChannelConfig,
    DeliveryRecord,
    DeliveryStatus,
    RouteConfig,
)

MAX_RETRIES = 3


class AlertRouter:
    """Routes alerts to configured channels based on per-user rules."""

    def __init__(self):
        self._configs: Dict[str, RouteConfig] = {}
        self._channels: Dict[str, Dict[str, Channel]] = {}
        self._history: List[DeliveryRecord] = []

    def set_route_config(self, config: RouteConfig) -> None:
        """Store or update routing config for a user."""
        self._configs[config.user_id] = config
        self._channels[config.user_id] = {}
        for ch_config in config.channels:
            if ch_config.enabled:
                self._channels[config.user_id][ch_config.name] = create_channel(
                    ch_config
                )

    def get_route_config(self, user_id: str) -> Optional[RouteConfig]:
        return self._configs.get(user_id)

    def delete_route_config(self, user_id: str) -> bool:
        if user_id in self._configs:
            del self._configs[user_id]
            self._channels.pop(user_id, None)
            return True
        return False

    def route_alert(self, alert: Alert) -> List[DeliveryRecord]:
        """Route an alert to all matching channels, returning delivery records."""
        config = self._configs.get(alert.user_id)
        if not config:
            logging.warning("No route config for user %s", alert.user_id)
            return []

        channel_names = self._resolve_channels(alert.alert_type, config)
        if not channel_names:
            logging.info(
                "No channels matched for alert_type=%s user=%s",
                alert.alert_type,
                alert.user_id,
            )
            return []

        records = []
        user_channels = self._channels.get(alert.user_id, {})
        for name in channel_names:
            channel = user_channels.get(name)
            if not channel:
                logging.warning("Channel '%s' not found for user %s", name, alert.user_id)
                continue

            ch_config = self._find_channel_config(config, name)
            record = self._deliver_with_retry(alert, name, ch_config, channel)
            records.append(record)
            self._history.append(record)

        return records

    def get_delivery_history(
        self,
        user_id: Optional[str] = None,
        alert_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DeliveryRecord]:
        """Query delivery history with optional filters."""
        filtered = self._history
        if user_id:
            filtered = [r for r in filtered if r.user_id == user_id]
        if alert_id:
            filtered = [r for r in filtered if r.alert_id == alert_id]
        return filtered[offset : offset + limit]

    def get_history_count(
        self,
        user_id: Optional[str] = None,
        alert_id: Optional[str] = None,
    ) -> int:
        filtered = self._history
        if user_id:
            filtered = [r for r in filtered if r.user_id == user_id]
        if alert_id:
            filtered = [r for r in filtered if r.alert_id == alert_id]
        return len(filtered)

    def _resolve_channels(
        self, alert_type: str, config: RouteConfig
    ) -> List[str]:
        """Find which channels to deliver to based on routing rules."""
        for rule in config.rules:
            if rule.alert_type == alert_type or rule.alert_type == "*":
                return rule.channel_names
        return config.default_channels

    def _find_channel_config(
        self, config: RouteConfig, channel_name: str
    ) -> Optional[ChannelConfig]:
        for ch in config.channels:
            if ch.name == channel_name:
                return ch
        return None

    def _deliver_with_retry(
        self,
        alert: Alert,
        channel_name: str,
        ch_config: Optional[ChannelConfig],
        channel: Channel,
    ) -> DeliveryRecord:
        """Attempt delivery with retries, returning a delivery record."""
        channel_type = ch_config.channel_type.value if ch_config else "unknown"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                success = channel.send(alert)
                if success:
                    return DeliveryRecord(
                        alert_id=alert.alert_id,
                        channel_name=channel_name,
                        channel_type=channel_type,
                        status=DeliveryStatus.DELIVERED,
                        user_id=alert.user_id,
                        attempt=attempt,
                        delivered_at=time.time(),
                    )
            except Exception as e:
                logging.error(
                    "Delivery attempt %d to %s failed: %s",
                    attempt,
                    channel_name,
                    e,
                )
                if attempt < MAX_RETRIES:
                    continue
                return DeliveryRecord(
                    alert_id=alert.alert_id,
                    channel_name=channel_name,
                    channel_type=channel_type,
                    status=DeliveryStatus.FAILED,
                    user_id=alert.user_id,
                    attempt=attempt,
                    error=str(e),
                )

        return DeliveryRecord(
            alert_id=alert.alert_id,
            channel_name=channel_name,
            channel_type=channel_type,
            status=DeliveryStatus.FAILED,
            user_id=alert.user_id,
            attempt=MAX_RETRIES,
            error="Channel returned False",
        )
