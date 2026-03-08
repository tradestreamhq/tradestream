"""
Redis client for the market MCP server.
Reads cryptocurrency symbols from the top_cryptocurrencies key.
"""

import json

from absl import logging
import redis


class RedisMarketClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.client = None

    def connect(self):
        """Connect to Redis."""
        self.client = redis.Redis(host=self.host, port=self.port, decode_responses=True)
        logging.info(f"Connected to Redis at {self.host}:{self.port}")

    def get_symbols(self) -> list[dict]:
        """Read top_cryptocurrencies key from Redis and return list of symbol dicts."""
        if not self.client:
            logging.error("Redis client not connected.")
            return []

        raw = self.client.get("top_cryptocurrencies")
        if not raw:
            logging.warning("No data found for key 'top_cryptocurrencies' in Redis.")
            return []

        try:
            symbols_list = json.loads(raw)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse top_cryptocurrencies JSON: {e}")
            return []

        results = []
        for sym in symbols_list:
            sym_str = str(sym).lower()
            # Symbols are stored as e.g. "btcusd" - split into base/quote
            if sym_str.endswith("usd"):
                base = sym_str[:-3].upper()
                quote = "USD"
            elif sym_str.endswith("usdt"):
                base = sym_str[:-4].upper()
                quote = "USDT"
            else:
                base = sym_str.upper()
                quote = "USD"

            results.append({
                "id": sym_str,
                "asset_class": "crypto",
                "base": base,
                "quote": quote,
                "exchange": "multi",
            })

        return results

    def close(self):
        """Close the Redis connection."""
        if self.client:
            self.client.close()
            logging.info("Redis client closed.")
