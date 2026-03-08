"""Redis client for reading cryptocurrency symbols."""

import json

from absl import logging
import redis
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

redis_retry_params = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(
        (
            redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            redis.exceptions.RedisError,
        )
    ),
)


class RedisMarketClient:
    def __init__(self, host: str, port: int, password: str | None = None):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
        try:
            self._connect()
        except RetryError as e:
            logging.error(
                f"RedisMarketClient: Failed to connect to Redis at "
                f"{self.host}:{self.port} after retries: {e}"
            )
            self.client = None
        except Exception as e:
            logging.error(
                f"RedisMarketClient: Unexpected error connecting to "
                f"{self.host}:{self.port}: {e}"
            )
            self.client = None

    @retry(**redis_retry_params)
    def _connect(self):
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            password=self.password,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True,
        )
        if not self.client.ping():
            self.client = None
            raise redis.exceptions.ConnectionError("Redis ping failed")
        logging.info("Successfully connected to Redis.")

    def get_symbols(self, key: str = "top_cryptocurrencies") -> list[dict]:
        """Read symbols from Redis and return structured list.

        The Redis key stores a JSON list of symbol strings like
        ["btcusd", "ethusd"]. This method parses them into structured dicts.
        """
        if not self.client:
            logging.error("Redis client not available.")
            return []

        try:
            raw = self._get_value_retryable(key)
            if raw is None:
                return []

            symbols = json.loads(raw)
            if not isinstance(symbols, list):
                logging.error(f"Redis key '{key}' is not a list: {symbols}")
                return []

            result = []
            for s in symbols:
                if not isinstance(s, str):
                    continue
                s_upper = s.upper()
                # Parse symbol format: "btcusd" -> base=BTC, quote=USD
                if len(s_upper) >= 6:
                    base = s_upper[:-3]
                    quote = s_upper[-3:]
                else:
                    base = s_upper
                    quote = "USD"

                result.append({
                    "id": s,
                    "asset_class": "crypto",
                    "base": base,
                    "quote": quote,
                    "exchange": "multi",
                })
            return result

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from Redis key '{key}': {e}")
            return []
        except RetryError as e:
            logging.error(
                f"Failed to get key '{key}' after retries: {e}"
            )
            return []
        except Exception as e:
            logging.error(f"Unexpected error fetching symbols: {e}")
            return []

    @retry(**redis_retry_params)
    def _get_value_retryable(self, key: str) -> str | None:
        if not self.client:
            return None
        value = self.client.get(key)
        if value is None:
            logging.warning(f"Key '{key}' not found in Redis.")
        return value

    def close(self):
        if self.client:
            try:
                self.client.close()
                logging.info("Redis client closed.")
            except Exception as e:
                logging.error(f"Error closing Redis client: {e}")
            finally:
                self.client = None
