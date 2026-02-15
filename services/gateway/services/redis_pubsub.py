"""Redis pub/sub service for real-time signal streaming."""

import json
import logging
from typing import AsyncGenerator, Optional

import redis.asyncio as redis

from ..config import settings

logger = logging.getLogger(__name__)

# Global Redis client
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = await redis.from_url(settings.REDIS_URL)
    return _redis_client


async def close_redis():
    """Close Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


async def subscribe_signals(
    channel: str = "scored-signals",
) -> AsyncGenerator[dict, None]:
    """Subscribe to Redis channel and yield signals.

    Yields parsed signal dictionaries from the Redis pub/sub channel.
    """
    client = await get_redis_client()
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    signal = json.loads(message["data"])
                    yield signal
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse signal JSON: {e}")
                    continue
    finally:
        await pubsub.unsubscribe(channel)


async def publish_signal(signal: dict, channel: str = "scored-signals") -> None:
    """Publish a signal to Redis channel."""
    client = await get_redis_client()
    await client.publish(channel, json.dumps(signal))
