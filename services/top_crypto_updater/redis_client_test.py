import unittest
from unittest import mock
import redis

from services.top_crypto_updater.redis_client import RedisManager, redis_retry_params


class TestRedisManager(unittest.TestCase):

    @mock.patch('redis.Redis')
    def test_connect_success(self, mock_redis_client_constructor):
        # Arrange
        mock_client_instance = mock.MagicMock()
        mock_client_instance.ping.return_value = True
        mock_redis_client_constructor.return_value = mock_client_instance

        # Act
        manager = RedisManager(host="localhost", port=6379)

        # Assert
        mock_redis_client_constructor.assert_called_once_with(
            host="localhost", port=6379, password=None,
            socket_connect_timeout=5, socket_timeout=5, decode_responses=True
        )
        mock_client_instance.ping.assert_called_once()
        self.assertIsNotNone(manager.client)
        self.assertIsNotNone(manager.get_client())

    @mock.patch('redis.Redis')
    def test_connect_ping_fails_raises_connection_error(self, mock_redis_client_constructor):
        # Arrange
        mock_client_instance = mock.MagicMock()
        mock_client_instance.ping.return_value = False # Simulate ping failure
        mock_redis_client_constructor.return_value = mock_client_instance

        # Act & Assert
        with self.assertRaises(redis.exceptions.ConnectionError) as context:
            RedisManager(host="localhost", port=6379) # ConnectionError raised by _connect
        self.assertIn("Ping failed", str(context.exception))
        # Verify client is None if constructor completed (it won't due to reraise=True)
        # For this test, we focus on the exception being raised as expected.


    @mock.patch('redis.Redis')
    def test_connect_failure_due_to_exception(self, mock_redis_client_constructor):
        # Arrange
        mock_redis_client_constructor.side_effect = redis.exceptions.ConnectionError("Simulated connection refused")

        # Act & Assert
        with self.assertRaises(redis.exceptions.ConnectionError):
            RedisManager(host="remotehost", port=1234)


    @mock.patch('redis.Redis')
    def test_get_client_not_initialized_attempts_reconnect_success(self, mock_redis_client_constructor):
        # Arrange
        # First call to constructor fails
        mock_first_attempt = mock.MagicMock()
        mock_first_attempt.ping.side_effect = redis.exceptions.ConnectionError("Initial connect fail")
        # Second call (reconnect) succeeds
        mock_second_attempt = mock.MagicMock()
        mock_second_attempt.ping.return_value = True
        mock_redis_client_constructor.side_effect = [mock_first_attempt, mock_second_attempt]

        manager = RedisManager(host="localhost", port=6379) # Initial connection fails silently in __init__ for this test
        self.assertIsNone(manager.client) # Client should be None after failed __init__

        # Act
        client = manager.get_client()

        # Assert
        self.assertIsNotNone(client)
        self.assertEqual(mock_redis_client_constructor.call_count, 2) # Init + get_client
        mock_second_attempt.ping.assert_called_once()


    @mock.patch('redis.Redis')
    def test_get_client_not_initialized_reconnect_fails(self, mock_redis_client_constructor):
        # Arrange
        mock_redis_client_constructor.side_effect = redis.exceptions.ConnectionError("Persistent connection fail")

        manager = RedisManager(host="localhost", port=6379) # Initial connection fails silently
        self.assertIsNone(manager.client)

        # Act
        client = manager.get_client()

        # Assert
        self.assertIsNone(client)
        # Depending on tenacity reraise, this might be more calls if _connect is retried by tenacity.
        # For a single retry attempt within get_client:
        self.assertEqual(mock_redis_client_constructor.call_count, 6) # __init__ (5 attempts) + get_client (1 attempt)


    @mock.patch('redis.Redis')
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


    @mock.patch('redis.Redis')
    def test_set_value_failure_client_not_available(self, mock_redis_client_constructor):
        # Arrange
        # Ensure client is None by making connection fail
        mock_redis_client_constructor.side_effect = redis.exceptions.ConnectionError("Connection Error")
        manager = RedisManager(host="localhost", port=6379)
        self.assertIsNone(manager.client) # Verify client is None

        # Act
        result = manager.set_value("test_key", "test_value")

        # Assert
        self.assertFalse(result)


    @mock.patch('redis.Redis')
    def test_set_value_redis_error_raises_and_retries(self, mock_redis_client_constructor):
        # Arrange
        mock_client_instance = mock.MagicMock()
        mock_client_instance.ping.return_value = True
        mock_client_instance.set.side_effect = redis.exceptions.RedisError("Set failed")
        mock_redis_client_constructor.return_value = mock_client_instance
        manager = RedisManager(host="localhost", port=6379)

        # Act & Assert
        with self.assertRaises(redis.exceptions.RedisError):
            manager.set_value("test_key", "test_value")
        self.assertEqual(mock_client_instance.set.call_count, redis_retry_params['stop'].max_attempt_number)


    @mock.patch('redis.Redis')
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


    @mock.patch('redis.Redis')
    def test_close_no_client_does_nothing(self, mock_redis_client_constructor):
        # Arrange
        mock_redis_client_constructor.side_effect = redis.exceptions.ConnectionError("No connect")
        manager = RedisManager(host="localhost", port=6379)
        self.assertIsNone(manager.client)

        # Act
        manager.close() # Should not raise error

        # Assert
        # mock_redis_client_constructor.return_value.close was never called because instance was never made
        # No specific assertion here other than no error was raised.


if __name__ == '__main__':
    unittest.main()
