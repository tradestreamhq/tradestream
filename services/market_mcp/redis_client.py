"""
Redis client for the market MCP server.
Reads cryptocurrency symbols from Redis.
"""

import json
from typing import Any, Dict, List

import redis
from absl import logging


class RedisMarketClient:
    """Redis client for reading market symbol data."""

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

    def get_symbols(self, key: str = "top_cryptocurrencies") -> List[Dict[str, Any]]:
        """Read cryptocurrency symbols from Redis.

        The top_cryptocurrencies key stores a JSON array of tiingo-format
        symbols (e.g., ["btcusd", "ethusd"]).

        Args:
            key: Redis key for the symbol list.

        Returns:
            List of symbol dicts with id, asset_class, base, quote, exchange.
        """
        if not self.client:
            raise RuntimeError("Redis connection not established")

        raw = self.client.get(key)
        if raw is None:
            logging.warning(f"Redis key '{key}' not found")
            return []

        symbols_list = json.loads(raw)
        result = []
        for sym in symbols_list:
            # Tiingo format: "btcusd" -> base="BTC", quote="USD"
            sym_str = str(sym).lower()
            if sym_str.endswith("usd"):
                base = sym_str[:-3].upper()
                quote = "USD"
            else:
                # Fallback: treat entire string as base
                base = sym_str.upper()
                quote = "USD"
            result.append(
                {
                    "id": sym_str,
                    "asset_class": "crypto",
                    "base": base,
                    "quote": quote,
                    "exchange": "multi",
                }
            )
        return result

    def close(self) -> None:
        """Close the Redis connection."""
        if self.client:
            self.client.close()
            logging.info("Redis connection closed")
