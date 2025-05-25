from absl import logging
import redis
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# Define common retry parameters for Redis operations
redis_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)
    ),
    reraise=True,
)


class RedisManager:
    def __init__(self, host: str, port: int, password: str | None = None):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
        try:
            self._connect()
        except Exception as e:
            logging.error(f"RedisManager __init__ failed to connect after retries: {e}")

    @retry(**redis_retry_params)
    def _connect(self):
        try:
            logging.info(f"Attempting to connect to Redis at {self.host}:{self.port}")
            self.client = redis.Redis(
                host=self.host, port=self.port, password=self.password,
                socket_connect_timeout=5, # seconds
                socket_timeout=5, # seconds
                decode_responses=True # Decode responses to strings
            )
            if not self.client.ping():
                logging.error(
                    f"Failed to ping Redis at {self.host}:{self.port}. Check connection and configuration."
                )
                self.client = None # Ensure client is None if ping fails
                raise redis.exceptions.ConnectionError("Ping failed")
            logging.info("Successfully connected to Redis and pinged server.")
        except Exception as e:
            logging.error(f"Error connecting to Redis at {self.host}:{self.port}: {e}")
            self.client = None # Ensure client is None on any exception
            raise

    def get_client(self) -> redis.Redis | None:
        if not self.client:
            logging.warning("Redis client not initialized. Attempting to reconnect...")
            try:
                self._connect() # Try to reconnect if the client is None
            except Exception as e:
                logging.error(f"Failed to reconnect to Redis: {e}")
                return None
        return self.client

    @retry(**redis_retry_params)
    def set_value(self, key: str, value: str) -> bool:
        client = self.get_client()
        if not client:
            logging.error("Cannot set value: Redis client not available.")
            return False
        try:
            client.set(key, value)
            logging.info(f"Successfully set value for key '{key}' in Redis.")
            return True
        except Exception as e:
            logging.error(f"Error setting value for key '{key}' in Redis: {e}")
            raise # Reraise to allow tenacity to retry

    def close(self):
        if self.client:
            try:
                self.client.close()
                logging.info("Redis client connection closed.")
            except Exception as e:
                logging.error(f"Error closing Redis client connection: {e}")
            finally:
                self.client = None
