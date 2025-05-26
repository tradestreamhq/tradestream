from absl import logging
import redis
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from typing import Optional

# Define common retry parameters for Redis operations
redis_retry_params = dict(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(
        (
            redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            redis.exceptions.RedisError,
        )
    ),
    reraise=True,
)


class RedisLastProcessedTracker:
    """
    Manages last processed timestamps for different services and keys using Redis.
    """

    def __init__(
        self,
        redis_host: str,
        redis_port: int,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_password = redis_password
        self.client: Optional[redis.Redis] = None
        self._connect_with_retry()

    @retry(**redis_retry_params)
    def _connect_with_retry(self):
        try:
            logging.info(
                f"Attempting to connect to Redis at {self.redis_host}:{self.redis_port}"
            )
            self.client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                socket_connect_timeout=5,  # seconds
                socket_timeout=5,  # seconds
                decode_responses=True, # Decode responses to strings
            )
            if not self.client.ping():
                logging.error(
                    f"Failed to ping Redis at {self.redis_host}:{self.redis_port}. Check connection and configuration."
                )
                self.client = None # Ensure client is None if ping fails
                raise redis.exceptions.ConnectionError("Redis ping failed")
            logging.info("Successfully connected to Redis and pinged server.")
        except Exception as e:
            logging.error(
                f"Error connecting to Redis at {self.redis_host}:{self.redis_port}: {e}"
            )
            self.client = None # Ensure client is None on any exception
            raise

    def _get_redis_key(self, service_name: str) -> str:
        return f"{service_name}:last_processed_timestamps"

    @retry(**redis_retry_params)
    def get_last_timestamp(
        self, service_name: str, key: str
    ) -> Optional[int]:
        """
        Retrieves the last processed timestamp for a given service and key.
        Args:
            service_name: Namespace for the service (e.g., "strategy_discovery").
            key: The specific item being tracked (e.g., "BTC/USD").
        Returns:
            The timestamp in milliseconds, or None if not found or an error occurs.
        """
        if not self.client:
            logging.warning("Redis client not initialized. Attempting to reconnect for get_last_timestamp.")
            try:
                self._connect_with_retry()
            except Exception as e:
                logging.error(f"Failed to reconnect to Redis for get_last_timestamp: {e}")
                return None
            if not self.client:
                logging.error("Redis client still not available after reconnect attempt for get_last_timestamp.")
                return None

        redis_hash_key = self._get_redis_key(service_name)
        try:
            timestamp_str = self.client.hget(redis_hash_key, key)
            if timestamp_str:
                logging.info(f"Retrieved last timestamp for {service_name} - {key}: {timestamp_str}")
                return int(timestamp_str)
            logging.info(f"No last timestamp found for {service_name} - {key}")
            return None
        except Exception as e:
            logging.error(
                f"Error getting last timestamp for {service_name} - {key} from Redis: {e}"
            )
            raise # Reraise to be caught by tenacity

    @retry(**redis_retry_params)
    def set_last_timestamp(
        self, service_name: str, key: str, timestamp_ms: int
    ) -> bool:
        """
        Sets the last processed timestamp for a given service and key.
        Args:
            service_name: Namespace for the service.
            key: The specific item being tracked.
            timestamp_ms: The timestamp in milliseconds.
        Returns:
            True if successful, False otherwise.
        """
        if not self.client:
            logging.warning("Redis client not initialized. Attempting to reconnect for set_last_timestamp.")
            try:
                self._connect_with_retry()
            except Exception as e:
                logging.error(f"Failed to reconnect to Redis for set_last_timestamp: {e}")
                return False
            if not self.client:
                logging.error("Redis client still not available after reconnect attempt for set_last_timestamp.")
                return False

        redis_hash_key = self._get_redis_key(service_name)
        try:
            self.client.hset(redis_hash_key, key, str(timestamp_ms))
            logging.info(
                f"Successfully set last timestamp for {service_name} - {key} to {timestamp_ms}"
            )
            return True
        except Exception as e:
            logging.error(
                f"Error setting last timestamp for {service_name} - {key} in Redis: {e}"
            )
            raise # Reraise to be caught by tenacity

    def close(self):
        if self.client:
            try:
                self.client.close()
                logging.info("Redis client connection closed.")
            except Exception as e:
                logging.error(f"Error closing Redis client connection: {e}")
            finally:
                self.client = None
