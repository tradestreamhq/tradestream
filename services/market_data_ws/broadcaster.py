"""Market data broadcaster that pushes updates to subscribed WebSocket clients."""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, Set

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class MarketDataBroadcaster:
    """Manages channel subscriptions and broadcasts market data updates.

    Channels follow the format: "{data_type}:{pair}" or "{data_type}:{pair}:{interval}"
    Examples: "trades:BTC-USD", "candles:ETH-USD:1m", "orderbook:BTC-USD"
    """

    VALID_DATA_TYPES = frozenset({"trades", "candles", "orderbook"})

    def __init__(self):
        # channel -> set of WebSocket connections
        self._subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
        # websocket -> set of channels
        self._client_channels: Dict[WebSocket, Set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    @staticmethod
    def validate_channel(channel: str) -> bool:
        """Validate a channel string format."""
        parts = channel.split(":")
        if len(parts) < 2 or len(parts) > 3:
            return False
        data_type = parts[0]
        if data_type not in MarketDataBroadcaster.VALID_DATA_TYPES:
            return False
        if data_type == "candles" and len(parts) != 3:
            return False
        if data_type in ("trades", "orderbook") and len(parts) != 2:
            return False
        return True

    async def subscribe(self, ws: WebSocket, channel: str) -> bool:
        """Subscribe a client to a channel. Returns True if newly subscribed."""
        if not self.validate_channel(channel):
            return False
        async with self._lock:
            if ws in self._subscriptions[channel]:
                return False
            self._subscriptions[channel].add(ws)
            self._client_channels[ws].add(channel)
        return True

    async def unsubscribe(self, ws: WebSocket, channel: str) -> bool:
        """Unsubscribe a client from a channel. Returns True if was subscribed."""
        async with self._lock:
            if ws not in self._subscriptions.get(channel, set()):
                return False
            self._subscriptions[channel].discard(ws)
            if not self._subscriptions[channel]:
                del self._subscriptions[channel]
            self._client_channels[ws].discard(channel)
            if not self._client_channels[ws]:
                del self._client_channels[ws]
        return True

    async def disconnect(self, ws: WebSocket):
        """Remove a client from all subscriptions."""
        async with self._lock:
            channels = self._client_channels.pop(ws, set())
            for channel in channels:
                self._subscriptions[channel].discard(ws)
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]

    async def broadcast(self, channel: str, data: Dict[str, Any]):
        """Broadcast data to all subscribers of a channel."""
        async with self._lock:
            subscribers = set(self._subscriptions.get(channel, set()))

        message = {"type": "data", "channel": channel, "payload": data}
        disconnected = []
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(ws)

    async def get_subscriber_count(self, channel: str) -> int:
        """Return the number of subscribers for a channel."""
        async with self._lock:
            return len(self._subscriptions.get(channel, set()))

    async def get_client_channels(self, ws: WebSocket) -> Set[str]:
        """Return the set of channels a client is subscribed to."""
        async with self._lock:
            return set(self._client_channels.get(ws, set()))
