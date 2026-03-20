"""Signal event bus: in-process pub/sub for real-time signal distribution.

Allows dashboard SSE endpoints and other consumers to subscribe to signal
events without coupling to Redis or the coordinator directly.
"""

import logging
import threading
import time
from collections import deque
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class SignalEventBus:
    """Thread-safe in-process event bus for signal distribution.

    Supports multiple subscribers and maintains a replay buffer so new
    SSE connections can catch up on recent signals.
    """

    def __init__(self, replay_buffer_size: int = 100):
        self._subscribers: dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._replay_buffer: deque = deque(maxlen=replay_buffer_size)
        self._event_counter = 0

    def subscribe(self, subscriber_id: str, callback: Callable) -> None:
        """Register a subscriber callback. Called with (event_type, data)."""
        with self._lock:
            self._subscribers[subscriber_id] = callback
            logger.info("Subscriber %s registered", subscriber_id)

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a subscriber."""
        with self._lock:
            self._subscribers.pop(subscriber_id, None)
            logger.info("Subscriber %s unsubscribed", subscriber_id)

    def publish(self, event_type: str, data: dict) -> int:
        """Publish an event to all subscribers. Returns delivery count."""
        with self._lock:
            self._event_counter += 1
            event_id = self._event_counter
            event = {
                "id": event_id,
                "type": event_type,
                "data": data,
                "timestamp": time.time(),
            }
            self._replay_buffer.append(event)
            subscribers = dict(self._subscribers)

        delivered = 0
        for sub_id, callback in subscribers.items():
            try:
                callback(event)
                delivered += 1
            except Exception as e:
                logger.warning("Failed to deliver to %s: %s", sub_id, e)

        return delivered

    def get_replay_buffer(self, since_id: int = 0) -> list:
        """Return events from replay buffer after the given event id."""
        with self._lock:
            return [e for e in self._replay_buffer if e["id"] > since_id]

    def get_stats(self) -> dict:
        """Return event bus statistics."""
        with self._lock:
            return {
                "total_events": self._event_counter,
                "subscriber_count": len(self._subscribers),
                "replay_buffer_size": len(self._replay_buffer),
                "replay_buffer_capacity": self._replay_buffer.maxlen,
            }


# Global event bus singleton
_event_bus: Optional[SignalEventBus] = None


def get_event_bus() -> SignalEventBus:
    """Get or create the global signal event bus."""
    global _event_bus
    if _event_bus is None:
        _event_bus = SignalEventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _event_bus
    _event_bus = None
