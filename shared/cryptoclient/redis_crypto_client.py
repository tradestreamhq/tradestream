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

# Define common retry parameters for Redis operations
redis_retry_params = dict(
    stop=stop_after_attempt(3),  # Reduced attempts for quicker failure if Redis is truly down
    wait=wait_exponential(multiplier=1, min=1, max=5), # Faster backoff
    retry=retry_if_exception_type(
        (
            redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            redis.exceptions.RedisError,
        )
    ),
    reraise=True,
)

class RedisCryptoClient:
    def __init__(self, host: str, port: int, password: str | None = None):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
        try:
            self._connect()
        except RetryError as e: # Catch RetryError specifically if all retries fail
            logging.error(f"RedisCryptoClient: Failed to connect to Redis at {self.host}:{self.port} after multiple retries: {e}")
            self.client = None # Ensure client is None
        except Exception as e:
            logging.error(f"RedisCryptoClient: Unexpected error during initial connection to {self.host}:{self.port}: {e}")
            self.client = None # Ensure client is None


    @retry(**redis_retry_params)
    def _connect(self):
        try:
            logging.info(f"Attempting to connect to Redis at {self.host}:{self.port}")
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                socket_connect_timeout=5,
                socket_timeout=5,
                decode_responses=True, # Important for getting strings directly
            )
            if not self.client.ping(): # ping() returns True on success, raises ConnectionError on failure
                logging.error(
                    f"Failed to ping Redis at {self.host}:{self.port}. Check connection and configuration."
                )
                self.client = None # Ensure client is None if ping fails logically (though redis-py usually raises)
                raise redis.exceptions.ConnectionError("Redis ping failed")
            logging.info("Successfully connected to Redis and pinged server.")
        except redis.exceptions.ConnectionError as e: # Catch specific connection errors
            logging.error(f"Redis connection error at {self.host}:{self.port}: {e}")
            self.client = None # Ensure client is None on connection error
            raise # Reraise to be caught by @retry or the caller
        except Exception as e: # Catch other potential errors during connection
            logging.error(f"Unexpected error connecting to Redis at {self.host}:{self.port}: {e}")
            self.client = None
            raise


    @retry(**redis_retry_params)
    def _get_value_retryable(self, key: str) -> str | None:
        if not self.client:
            logging.warning("Redis client not initialized in _get_value_retryable. Attempting to reconnect...")
            try:
                self._connect() # Attempt to reconnect
                if not self.client: # Check if reconnect failed
                    logging.error("Failed to reconnect to Redis in _get_value_retryable.")
                    return None
            except Exception as e:
                logging.error(f"Exception during reconnect attempt in _get_value_retryable: {e}")
                return None

        try:
            value = self.client.get(key)
            if value is None:
                logging.warning(f"Key '{key}' not found in Redis.")
                return None
            logging.info(f"Successfully retrieved value for key '{key}' from Redis.")
            return value
        except Exception as e: # Catch other redis errors during GET
            logging.error(f"Error getting value for key '{key}' from Redis: {e}")
            raise # Reraise to allow tenacity to handle retries


    def get_top_crypto_pairs_from_redis(self, key: str = "top_cryptocurrencies") -> list[str]:
        """
        Fetches a list of top cryptocurrency pairs from Redis.
        The value in Redis is expected to be a JSON string representing a list of strings.
        Example format in Redis: '["btcusd", "ethusd", "adausd"]'
        """
        if not self.client:
            logging.error("Cannot fetch crypto pairs: Redis client not available or connection failed.")
            # Attempt one final reconnect if client is None due to initial connection failure
            if self.client is None:
                 try:
                    logging.info("Attempting a final reconnect before failing get_top_crypto_pairs_from_redis...")
                    self._connect()
                    if not self.client:
                         logging.error("Final reconnect attempt failed. Returning empty list.")
                         return []
                 except Exception as e:
                    logging.error(f"Exception during final reconnect attempt: {e}. Returning empty list.")
                    return []
            else: # If client was available but then connection dropped and couldn't be re-established by _get_value_retryable
                return []


        try:
            json_string = self._get_value_retryable(key)
            if json_string is None:
                return []

            symbols = json.loads(json_string)
            if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
                logging.error(f"Value for key '{key}' in Redis is not a JSON list of strings: {symbols}")
                return []

            logging.info(f"Successfully fetched and parsed {len(symbols)} crypto pairs from Redis key '{key}'.")
            return symbols
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from Redis key '{key}': {e}. Value was: '{json_string}'")
            return []
        except RetryError as e: # Catch RetryError if _get_value_retryable fails all retries
            logging.error(f"Failed to get value for key '{key}' from Redis after multiple retries: {e}")
            return []
        except Exception as e:
            logging.error(f"An unexpected error occurred while fetching crypto pairs from Redis: {e}")
            return []

    def close(self):
        if self.client:
            try:
                self.client.close()
                logging.info("Redis client connection closed.")
            except Exception as e:
                logging.error(f"Error closing Redis client connection: {e}")
            finally:
                self.client = None
