import unittest
from unittest import mock
import redis

from services.top_crypto_updater.redis_client import RedisManager, redis_retry_params


class TestRedisManager(unittest.TestCase):

    @mock.patch("redis.Redis")
    def test_connect_success(self, mock_redis_client_constructor):
        # Arrange
        mock_client_instance = mock.MagicMock()
        mock_client_instance.ping.return_value = True
        mock_redis_client_constructor.return_value = mock_client_instance

        # Act
        manager = RedisManager(host="localhost", port=6379)

        # Assert
        mock_redis_client_constructor.assert_called_once_with(
            host="localhost",
            port=6379,
            password=None,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True,
        )
        mock_client_instance.ping.assert_called_once()
        self.assertIsNotNone(manager.client)
        self.assertIsNotNone(manager.get_client())

    @mock.patch("redis.Redis")
    def test_connect_ping_fails_results_in_none_client(
        self, mock_redis_client_constructor
    ):
        # Arrange
        mock_client_instance = mock.MagicMock()
        mock_client_instance.ping.return_value = False
        mock_redis_client_constructor.return_value = mock_client_instance

        # Act
        manager = RedisManager(
            host="localhost", port=6379
        )  # Constructor no longer raises, but logs and sets client to None

        # Assert
        self.assertIsNone(manager.client)
        # _connect is called from __init__, it will retry 5 times
        self.assertEqual(mock_redis_client_constructor.call_count, 5)
        # ping would be called 5 times by the 5 attempts of _connect
        self.assertEqual(mock_client_instance.ping.call_count, 5)

    @mock.patch("redis.Redis")
    def test_connect_failure_results_in_none_client(
        self, mock_redis_client_constructor
    ):
        # Arrange
        mock_redis_client_constructor.side_effect = redis.exceptions.ConnectionError(
            "Simulated connection refused"
        )
        # Act
        manager = RedisManager(
            host="remotehost", port=1234
        )  # Constructor no longer raises, but logs and sets client to None

        # Assert
        self.assertIsNone(manager.client)  # Check that client attribute is None
        # _connect is called from __init__, it will retry 5 times
        self.assertEqual(mock_redis_client_constructor.call_count, 5)

    @mock.patch("redis.Redis")
    def test_get_client_not_initialized_attempts_reconnect_success(
        self, mock_redis_client_constructor
    ):
        # Arrange
        mock_successful_connection = mock.MagicMock()
        mock_successful_connection.ping.return_value = True

        # First call to constructor's _connect (via __init__) will fail after retries
        # Subsequent call from get_client's _connect will succeed
        # Total 5 + 1 = 6 calls if init fails and get_client succeeds on first try
        # But _connect itself has retries. So if __init__'s _connect fails all 5 times,
        # and get_client's _connect succeeds on its 1st try (within its own retry wrapper).
        initial_failures = [
            redis.exceptions.ConnectionError("Initial connect attempt fail")
        ] * 5
        mock_redis_client_constructor.side_effect = initial_failures + [
            mock_successful_connection
        ]

        manager = RedisManager(
            host="localhost", port=6379
        )  # __init__ calls _connect 5 times, self.client is None

        self.assertIsNone(manager.client, "Client should be None after failed __init__")

        # Act
        client = (
            manager.get_client()
        )  # get_client calls _connect, which succeeds on the 6th overall call to constructor

        # Assert
        self.assertIsNotNone(client)
        # Called 5 times during __init__ (all failing), then 1 time during get_client (succeeding)
        self.assertEqual(mock_redis_client_constructor.call_count, 6)
        mock_successful_connection.ping.assert_called_once()

    @mock.patch("redis.Redis")
    def test_get_client_not_initialized_reconnect_fails(
        self, mock_redis_client_constructor
    ):
        # Arrange
        # All attempts to connect will fail
        mock_redis_client_constructor.side_effect = redis.exceptions.ConnectionError(
            "Persistent connection fail"
        )

        manager = RedisManager(
            host="localhost", port=6379
        )  # __init__ calls _connect 5 times. self.client will be None.

        self.assertIsNone(
            manager.client, "Client attribute should be None after failed __init__"
        )

        # Act
        # get_client will attempt to reconnect, which will also fail after retries.
        # It will catch the exception from its _connect call and return None.
        client = manager.get_client()  # This will call _connect 5 more times.

        # Assert
        self.assertIsNone(client)
        # __init__ calls _connect which retries 5 times (5 constructor calls).
        # get_client calls _connect which retries 5 times (5 more constructor calls).
        self.assertEqual(mock_redis_client_constructor.call_count, 10)

    @mock.patch("redis.Redis")
    def test_set_value_success(self, mock_redis_client_constructor):
        # Arrange
        mock_client_instance = mock.MagicMock()
        mock_client_instance.ping.return_value = True
        mock_redis_client_constructor.return_value = mock_client_instance
        manager = RedisManager(host="localhost", port=6379)

        # Act
        result = manager.set_value("test_key", "test_value")

        # Assert
        self.assertTrue(result)
        mock_client_instance.set.assert_called_once_with("test_key", "test_value")

    @mock.patch("redis.Redis")
    def test_set_value_failure_client_not_available(
        self, mock_redis_client_constructor
    ):
        # Arrange
        mock_redis_client_constructor.side_effect = redis.exceptions.ConnectionError(
            "Connection Error"
        )

        manager = RedisManager(
            host="localhost", port=6379
        )  # __init__ calls _connect 5 times. self.client is None.

        self.assertIsNone(manager.client)  # Assert self.client is indeed None.

        # Act
        result = manager.set_value(
            "test_key", "test_value"
        )  # Calls get_client -> _connect 5 times. get_client returns None. set_value returns False.

        # Assert
        self.assertFalse(result)
        self.assertEqual(
            mock_redis_client_constructor.call_count, 10
        )  # 5 for __init__, 5 for set_value->get_client

    @mock.patch("redis.Redis")
    def test_set_value_redis_error_raises_and_retries(
        self, mock_redis_client_constructor
    ):
        # Arrange
        mock_client_instance = mock.MagicMock()
        mock_client_instance.ping.return_value = True
        # Configure .set() to raise RedisError, which is now in redis_retry_params
        mock_client_instance.set.side_effect = redis.exceptions.RedisError("Set failed")
        mock_redis_client_constructor.return_value = mock_client_instance
        manager = RedisManager(host="localhost", port=6379)

        # Act & Assert
        with self.assertRaises(redis.exceptions.RedisError):
            manager.set_value("test_key", "test_value")
        # Verify .set was called 5 times due to retry
        self.assertEqual(
            mock_client_instance.set.call_count,
            redis_retry_params["stop"].max_attempt_number,
        )

    @mock.patch("redis.Redis")
    def test_close_closes_client(self, mock_redis_client_constructor):
        # Arrange
        mock_client_instance = mock.MagicMock()
        mock_client_instance.ping.return_value = True
        mock_redis_client_constructor.return_value = mock_client_instance
        manager = RedisManager(host="localhost", port=6379)
        self.assertIsNotNone(manager.client)

        # Act
        manager.close()

        # Assert
        mock_client_instance.close.assert_called_once()
        self.assertIsNone(manager.client)

    @mock.patch("redis.Redis")
    def test_close_no_client_does_nothing(self, mock_redis_client_constructor):
        # Arrange
        mock_redis_client_constructor.side_effect = redis.exceptions.ConnectionError(
            "No connect"
        )

        manager = RedisManager(
            host="localhost", port=6379
        )  # __init__ fails to connect, self.client is None
        self.assertIsNone(manager.client)

        # Act
        manager.close()  # Should not raise error

        # Assert
        # mock_redis_client_constructor.return_value.close was never called because instance was never successfully created
        # and assigned to self.client in a way that close() would use it.
        # No specific assertion here other than no error was raised.
        pass


if __name__ == "__main__":
    unittest.main()
