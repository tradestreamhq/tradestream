"""Delivery router: routes signals to correct channels based on user preferences."""

import time
from dataclasses import dataclass, field

from absl import logging

from services.notification_service.deduplicator import CrossChannelDeduplicator
from services.notification_service.rate_limiter import DeliveryRateLimiter
from services.notification_service.user_preferences import (
    UserDeliveryPreferences,
    UserPreferencesStore,
)


@dataclass
class DeliveryResult:
    """Result of routing a signal to a user."""

    signal_id: str
    user_id: str
    channel: str
    success: bool
    error: str = ""
    skipped_reason: str = ""


@dataclass
class RoutingResult:
    """Aggregate result of routing a signal across all channels for a user."""

    signal_id: str
    user_id: str
    results: list[DeliveryResult] = field(default_factory=list)

    @property
    def any_success(self) -> bool:
        return any(r.success for r in self.results if not r.skipped_reason)

    @property
    def all_skipped(self) -> bool:
        return all(bool(r.skipped_reason) for r in self.results)


class DeliveryRouter:
    """Routes signals to the correct channels based on user preferences.

    Integrates deduplication, rate limiting, quiet hours, and per-channel
    filtering to determine where each signal should be delivered.
    """

    def __init__(
        self,
        senders: dict[str, object],
        redis_client,
        preferences_store: UserPreferencesStore | None = None,
        deduplicator: CrossChannelDeduplicator | None = None,
        rate_limiter: DeliveryRateLimiter | None = None,
    ):
        self.senders = senders  # channel_name -> sender instance
        self.redis = redis_client
        self.prefs_store = preferences_store or UserPreferencesStore(redis_client)
        self.dedup = deduplicator or CrossChannelDeduplicator(redis_client)
        self.rate_limiter = rate_limiter or DeliveryRateLimiter(redis_client)

    def route(
        self,
        signal: dict,
        user_id: str,
        prefs: UserDeliveryPreferences | None = None,
    ) -> RoutingResult:
        """Route a signal to the appropriate channels for a user.

        Args:
            signal: Signal payload dict.
            user_id: Target user.
            prefs: Pre-loaded preferences (loaded from store if None).

        Returns:
            RoutingResult with per-channel delivery outcomes.
        """
        signal_id = signal.get("signal_id", "unknown")
        if prefs is None:
            prefs = self.prefs_store.get(user_id)

        result = RoutingResult(signal_id=signal_id, user_id=user_id)

        # Check quiet hours
        if self._in_quiet_hours(prefs):
            priority = signal.get("priority", "normal")
            if priority != "critical":
                result.results.append(
                    DeliveryResult(
                        signal_id=signal_id,
                        user_id=user_id,
                        channel="all",
                        success=False,
                        skipped_reason="quiet_hours",
                    )
                )
                return result

        # Determine which channels to attempt
        channels = self._resolve_channels(prefs)

        for channel_name in channels:
            dr = self._deliver_to_channel(
                signal, signal_id, user_id, channel_name, prefs
            )
            result.results.append(dr)

            # For fallback_chain: stop after first success
            if prefs.delivery_mode == "fallback_chain" and dr.success:
                self.dedup.mark_success(signal_id, user_id)
                break

        return result

    def _resolve_channels(self, prefs: UserDeliveryPreferences) -> list[str]:
        """Determine ordered list of channels to attempt."""
        if prefs.delivery_mode == "primary_only":
            if prefs.primary_channel in self.senders:
                return [prefs.primary_channel]
            return []

        # all_enabled or fallback_chain: return all enabled channels
        channels = []
        # Primary first for fallback_chain ordering
        if prefs.primary_channel in self.senders and prefs.is_channel_enabled(
            prefs.primary_channel
        ):
            channels.append(prefs.primary_channel)
        for name in self.senders:
            if name not in channels and prefs.is_channel_enabled(name):
                channels.append(name)
        return channels

    def _deliver_to_channel(
        self,
        signal: dict,
        signal_id: str,
        user_id: str,
        channel_name: str,
        prefs: UserDeliveryPreferences,
    ) -> DeliveryResult:
        """Attempt delivery to a single channel with all checks."""
        # Per-channel filter
        if not prefs.passes_channel_filter(channel_name, signal):
            return DeliveryResult(
                signal_id=signal_id,
                user_id=user_id,
                channel=channel_name,
                success=False,
                skipped_reason="channel_filter",
            )

        # Priority check on sender
        sender = self.senders[channel_name]
        priority = signal.get("priority", "normal")
        if hasattr(sender, "supports_priority") and not sender.supports_priority(
            priority
        ):
            return DeliveryResult(
                signal_id=signal_id,
                user_id=user_id,
                channel=channel_name,
                success=False,
                skipped_reason="priority_not_supported",
            )

        # Deduplication
        if not self.dedup.should_deliver(
            signal_id,
            user_id,
            channel_name,
            preference=prefs.delivery_mode,
            primary_channel=prefs.primary_channel,
        ):
            return DeliveryResult(
                signal_id=signal_id,
                user_id=user_id,
                channel=channel_name,
                success=False,
                skipped_reason="deduplicated",
            )

        # Rate limiting
        if not self.rate_limiter.allow(user_id, channel_name, prefs.tier):
            return DeliveryResult(
                signal_id=signal_id,
                user_id=user_id,
                channel=channel_name,
                success=False,
                skipped_reason="rate_limited",
            )

        # Deliver
        try:
            success = sender.send_signal(signal)
            if not success and prefs.delivery_mode == "fallback_chain":
                self.dedup.mark_failed(signal_id, user_id, channel_name)
            return DeliveryResult(
                signal_id=signal_id,
                user_id=user_id,
                channel=channel_name,
                success=success,
            )
        except Exception as e:
            logging.error(
                "Delivery to %s failed for user %s: %s", channel_name, user_id, e
            )
            if prefs.delivery_mode == "fallback_chain":
                self.dedup.mark_failed(signal_id, user_id, channel_name)
            return DeliveryResult(
                signal_id=signal_id,
                user_id=user_id,
                channel=channel_name,
                success=False,
                error=str(e),
            )

    def _in_quiet_hours(self, prefs: UserDeliveryPreferences) -> bool:
        """Check if current time falls within user's quiet hours."""
        qh = prefs.quiet_hours
        if not qh.enabled:
            return False

        # Use UTC for simplicity; production would use qh.timezone
        current_hour = time.gmtime().tm_hour
        if qh.start_hour > qh.end_hour:
            # Wraps midnight: e.g. 22:00 - 08:00
            return current_hour >= qh.start_hour or current_hour < qh.end_hour
        else:
            return qh.start_hour <= current_hour < qh.end_hour
