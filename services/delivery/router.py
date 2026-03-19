"""Delivery router: routes signals to channels based on user preferences."""

import time
from datetime import datetime, timezone

from absl import logging

from services.delivery.channels.base import DeliveryChannel, DeliveryResult
from services.delivery.deduplication import CrossChannelDeduplicator
from services.delivery.preferences import (
    ChannelPreference,
    PreferenceStore,
    UserDeliveryPreferences,
)
from services.delivery.rate_limiter import DeliveryRateLimiter
from services.delivery.tracker import DeliveryTracker


class DeliveryRouter:
    """Routes signals to the correct delivery channels.

    For each signal, the router:
    1. Looks up user preferences (enabled channels, filters, quiet hours)
    2. Checks cross-channel deduplication
    3. Applies rate limiting
    4. Dispatches to the appropriate channel(s)
    5. Tracks delivery status with receipts

    Supports retry with exponential backoff for retryable failures.
    """

    MAX_RETRY_ATTEMPTS = 6
    BASE_RETRY_DELAY = 1.0

    def __init__(
        self,
        channels: dict[str, DeliveryChannel],
        preference_store: PreferenceStore,
        deduplicator: CrossChannelDeduplicator,
        rate_limiter: DeliveryRateLimiter,
        tracker: DeliveryTracker,
    ):
        self.channels = channels
        self.preference_store = preference_store
        self.deduplicator = deduplicator
        self.rate_limiter = rate_limiter
        self.tracker = tracker

    def route_signal(self, signal: dict, user_id: str) -> list[DeliveryResult]:
        """Route a signal to all applicable channels for a user.

        Returns a list of DeliveryResults, one per attempted channel.
        """
        prefs = self.preference_store.get_preferences(user_id)
        if prefs is None:
            return []

        results = []
        signal_id = signal.get("signal_id", "unknown")
        symbol = signal.get("symbol", "")

        target_channels = self._resolve_channels(prefs, signal)

        for ch_pref in target_channels:
            channel_name = ch_pref.channel

            if channel_name not in self.channels:
                continue

            # Deduplication check
            if not self.deduplicator.should_deliver(
                signal_id, user_id, channel_name, prefs.dedup_preference
            ):
                continue

            # Rate limiting check
            if self.rate_limiter.is_rate_limited(
                user_id, channel_name, symbol, prefs.tier
            ):
                continue

            # Quiet hours check
            if self._in_quiet_hours(ch_pref):
                continue

            # Create receipt and dispatch
            self.tracker.create_receipt(signal_id, user_id, channel_name)
            channel = self.channels[channel_name]
            result = self._dispatch_with_retry(
                channel, signal, ch_pref.channel_id, signal_id, user_id
            )
            results.append(result)

            if result.success:
                self.deduplicator.mark_delivered(signal_id, user_id, channel_name)
                self.tracker.mark_sent(
                    signal_id, user_id, channel_name, result.external_message_id
                )
            else:
                self.deduplicator.mark_failed(signal_id, user_id, channel_name)
                self.tracker.mark_failed(
                    signal_id, user_id, channel_name, result.error
                )

        return results

    def route_signal_to_all_users(
        self, signal: dict, user_ids: list[str]
    ) -> dict[str, list[DeliveryResult]]:
        """Route a signal to all applicable channels for multiple users."""
        results = {}
        for user_id in user_ids:
            results[user_id] = self.route_signal(signal, user_id)
        return results

    def _resolve_channels(
        self, prefs: UserDeliveryPreferences, signal: dict
    ) -> list[ChannelPreference]:
        """Determine which channels a signal should be sent to."""
        candidates = []
        for ch_pref in prefs.channels.values():
            if not ch_pref.enabled:
                continue
            if not self._matches_filters(ch_pref, signal):
                continue
            candidates.append(ch_pref)

        if prefs.dedup_preference == "primary_only":
            # Only the primary channel
            primary = [c for c in candidates if c.channel == prefs.primary_channel]
            if primary:
                return primary
            # Fallback to first available
            return candidates[:1]

        if prefs.dedup_preference == "fallback_chain":
            # Order by fallback preference
            ordered = []
            for ch_name in prefs.fallback_order:
                match = [c for c in candidates if c.channel == ch_name]
                if match:
                    ordered.append(match[0])
            # Add any remaining channels not in fallback order
            seen = {c.channel for c in ordered}
            for c in candidates:
                if c.channel not in seen:
                    ordered.append(c)
            return ordered

        # all_enabled: return all candidates
        return candidates

    def _matches_filters(
        self, ch_pref: ChannelPreference, signal: dict
    ) -> bool:
        """Check if a signal matches channel preference filters."""
        score = signal.get("opportunity_score", 0)
        if score and score < ch_pref.min_opportunity_score:
            return False

        symbol = signal.get("symbol", "")
        if ch_pref.symbols and symbol not in ch_pref.symbols:
            return False

        action = signal.get("action", "")
        if ch_pref.actions and action not in ch_pref.actions:
            return False

        return True

    def _in_quiet_hours(self, ch_pref: ChannelPreference) -> bool:
        """Check if current time is within the user's quiet hours."""
        if not ch_pref.quiet_hours_start or not ch_pref.quiet_hours_end:
            return False

        try:
            now = datetime.now(timezone.utc)
            start_parts = ch_pref.quiet_hours_start.split(":")
            end_parts = ch_pref.quiet_hours_end.split(":")
            start = int(start_parts[0]) * 60 + int(start_parts[1])
            end = int(end_parts[0]) * 60 + int(end_parts[1])
            current = now.hour * 60 + now.minute

            if start <= end:
                return start <= current < end
            else:
                # Quiet hours span midnight
                return current >= start or current < end
        except (ValueError, IndexError):
            return False

    def _dispatch_with_retry(
        self,
        channel: DeliveryChannel,
        signal: dict,
        recipient: str,
        signal_id: str,
        user_id: str,
    ) -> DeliveryResult:
        """Dispatch with retry for retryable failures.

        Uses exponential backoff: 1s, 2s, 4s, 8s, 16s.
        Non-retryable errors fail immediately.
        """
        last_result = None
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            result = channel.send(signal, recipient)
            last_result = result

            if result.success:
                return result

            if not result.retryable:
                return result

            if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                delay = self.BASE_RETRY_DELAY * (2 ** attempt)
                import time as time_mod
                time_mod.sleep(min(delay, 16.0))

        return last_result
