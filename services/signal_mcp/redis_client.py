"""
Redis client for the signal MCP server.
Handles pub/sub for signal emission.
"""

import json
from typing import Any, Dict

import redis
from absl import logging


class RedisClient:
    """Redis client for signal pub/sub."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.client = None

    def connect(self) -> None:
        """Establish connection to Redis."""
        logging.info(f"Connecting to Redis at {self.host}:{self.port}")
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            decode_responses=True,
        )
        self.client.ping()
        logging.info("Successfully connected to Redis")

    def publish_signal(self, symbol: str, signal_data: Dict[str, Any]) -> int:
        """Publish a signal to the Redis channel for the given symbol.

        Args:
            symbol: Trading symbol (e.g., BTC/USD).
            signal_data: Signal data to publish as JSON.

        Returns:
            Number of subscribers that received the message.
        """
        if not self.client:
            raise RuntimeError("Redis connection not established")

        channel = f"signals:{symbol}"
        message = json.dumps(signal_data, default=str)
        subscribers = self.client.publish(channel, message)
        logging.info(
            f"Published signal to {channel} ({subscribers} subscribers)"
        )
        return subscribers

    def close(self) -> None:
        """Close the Redis connection."""
        if self.client:
            self.client.close()
            logging.info("Redis connection closed")
