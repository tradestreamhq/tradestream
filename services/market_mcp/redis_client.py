"""
Redis client for the market MCP server.
Reads cryptocurrency symbols from Redis.
"""

import json
from typing import Any, Dict, List

import redis
from absl import logging


class RedisClient:
    """Redis client for reading market symbols."""

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

        The value in Redis is a JSON list of symbol strings (e.g., ["btcusd", "ethusd"]).
        We transform each into a structured dict.

        Args:
            key: Redis key for the symbol list.

        Returns:
            List of dicts with id, asset_class, base, quote, exchange.
        """
        if not self.client:
            raise RuntimeError("Redis connection not established")

        raw = self.client.get(key)
        if raw is None:
            logging.warning(f"Key '{key}' not found in Redis")
            return []

        symbols_list = json.loads(raw)
        if not isinstance(symbols_list, list):
            logging.error(f"Value for key '{key}' is not a list: {symbols_list}")
            return []

        result = []
        for symbol_str in symbols_list:
            if not isinstance(symbol_str, str):
                continue
            # Symbols are stored like "btcusd" - split into base/quote
            s = symbol_str.upper()
            # Common quote currencies
            for quote in ["USD", "USDT", "EUR", "BTC", "ETH"]:
                if s.endswith(quote) and len(s) > len(quote):
                    base = s[: -len(quote)]
                    result.append({
                        "id": symbol_str,
                        "asset_class": "crypto",
                        "base": base,
                        "quote": quote,
                        "exchange": "multi",
                    })
                    break
            else:
                # Fallback: assume last 3 chars are quote
                if len(s) > 3:
                    result.append({
                        "id": symbol_str,
                        "asset_class": "crypto",
                        "base": s[:-3],
                        "quote": s[-3:],
                        "exchange": "multi",
                    })

        return result

    def close(self) -> None:
        """Close the Redis connection."""
        if self.client:
            self.client.close()
            logging.info("Redis connection closed")
