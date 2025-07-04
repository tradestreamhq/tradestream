import unittest
from unittest import mock
import json
import redis

from absl import logging

# It's good practice to ensure logging is configured for tests if the module uses it.
logging.set_verbosity(logging.INFO)


from shared.cryptoclient.redis_crypto_client import RedisCryptoClient, RetryError


class TestRedisCryptoClient(unittest.TestCase):
    @mock.patch("redis.Redis")
    def test_init_connection_success(self, MockRedis):
        mock_redis_instance = MockRedis.return_value
        mock_redis_instance.ping.return_value = True

        client = RedisCryptoClient(host="localhost", port=6379)
        self.assertIsNotNone(client.client)
        MockRedis.assert_called_once_with(
            host="localhost",
            port=6379,
            password=None,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=True,
        )
        mock_redis_instance.ping.assert_called_once()

    @mock.patch("redis.Redis")
    def test_init_connection_ping_fails_retries_and_sets_client_to_none(
        self, MockRedis
    ):
        mock_redis_instance = MockRedis.return_value
        # Simulate ping failing, which for redis-py client usually means ConnectionError on ping()
        mock_redis_instance.ping.side_effect = redis.exceptions.ConnectionError(
            "Ping failed"
        )

        with self.assertLogs(level="ERROR") as log_watcher:
            client = RedisCryptoClient(host="localhost", port=6379)

        self.assertIsNone(client.client)
        # _connect is called from __init__, it will retry. Default is 3 for this class.
        self.assertEqual(MockRedis.call_count, 3)
        self.assertEqual(
            mock_redis_instance.ping.call_count, 3
        )  # Ping called for each connect attempt
        # Check the actual log messages that are produced
        log_messages = [record.message for record in log_watcher.records]
        self.assertTrue(
            any(
                "RedisCryptoClient: Failed to connect to Redis at localhost:6379 after multiple retries"
                in message
                for message in log_messages
            )
        )

    @mock.patch("redis.Redis")
    def test_init_connection_exception_retries_and_sets_client_to_none(self, MockRedis):
        MockRedis.side_effect = redis.exceptions.ConnectionError(
            "Initial connection refused"
        )
        with self.assertLogs(level="ERROR") as log_watcher:
            client = RedisCryptoClient(host="remotehost", port=1234)

        self.assertIsNone(client.client)
        self.assertEqual(MockRedis.call_count, 3)  # Called 3 times due to retries
        # Check the actual log messages that are produced
        log_messages = [record.message for record in log_watcher.records]
        self.assertTrue(
            any(
                "RedisCryptoClient: Failed to connect to Redis at remotehost:1234 after multiple retries"
                in message
                for message in log_messages
            )
        )

    @mock.patch("redis.Redis")
    def test_get_top_crypto_pairs_success(self, MockRedis):
        mock_redis_instance = MockRedis.return_value
        mock_redis_instance.ping.return_value = True
        expected_pairs = ["btcusd", "ethusd"]
        mock_redis_instance.get.return_value = json.dumps(expected_pairs)

        client = RedisCryptoClient(host="localhost", port=6379)
        pairs = client.get_top_crypto_pairs_from_redis("test_key")

        self.assertEqual(pairs, expected_pairs)
        mock_redis_instance.get.assert_called_once_with("test_key")

    @mock.patch("redis.Redis")
    def test_get_top_crypto_pairs_key_not_found(self, MockRedis):
        mock_redis_instance = MockRedis.return_value
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = None

        client = RedisCryptoClient(host="localhost", port=6379)
        pairs = client.get_top_crypto_pairs_from_redis("nonexistent_key")

        self.assertEqual(pairs, [])
        mock_redis_instance.get.assert_called_once_with("nonexistent_key")

    @mock.patch("redis.Redis")
    def test_get_top_crypto_pairs_invalid_json(self, MockRedis):
        mock_redis_instance = MockRedis.return_value
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = "this is not json"

        client = RedisCryptoClient(host="localhost", port=6379)
        with self.assertLogs(level="ERROR") as log_watcher:
            pairs = client.get_top_crypto_pairs_from_redis("invalid_json_key")

        self.assertEqual(pairs, [])
        log_messages = [record.message for record in log_watcher.records]
        self.assertTrue(
            any(
                "Failed to parse JSON from Redis key 'invalid_json_key'" in message
                for message in log_messages
            )
        )

    @mock.patch("redis.Redis")
    def test_get_top_crypto_pairs_not_a_list(self, MockRedis):
        mock_redis_instance = MockRedis.return_value
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.get.return_value = json.dumps({"not": "a list"})

        client = RedisCryptoClient(host="localhost", port=6379)
        with self.assertLogs(level="ERROR") as log_watcher:
            pairs = client.get_top_crypto_pairs_from_redis("not_a_list_key")

        self.assertEqual(pairs, [])
        log_messages = [record.message for record in log_watcher.records]
        self.assertTrue(
            any(
                "Value for key 'not_a_list_key' in Redis is not a JSON list of strings"
                in message
                for message in log_messages
            )
        )

    @mock.patch("redis.Redis")
    def test_get_top_crypto_pairs_redis_get_fails_after_retries(self, MockRedis):
        mock_redis_instance = MockRedis.return_value
        mock_redis_instance.ping.return_value = True  # Initial connect succeeds
        mock_redis_instance.get.side_effect = redis.exceptions.ConnectionError(
            "GET failed"
        )

        client = RedisCryptoClient(host="localhost", port=6379)
        with self.assertLogs(level="ERROR") as log_watcher:
            pairs = client.get_top_crypto_pairs_from_redis("fail_key")

        self.assertEqual(pairs, [])
        # get is called inside _get_value_retryable, which has 3 attempts
        self.assertEqual(mock_redis_instance.get.call_count, 3)
        log_messages = [record.message for record in log_watcher.records]
        self.assertTrue(
            any(
                "Failed to get value for key 'fail_key' from Redis after multiple retries"
                in message
                for message in log_messages
            )
        )

    @mock.patch("redis.Redis")
    def test_get_top_crypto_pairs_client_initially_none_then_reconnects_for_get(
        self, MockRedis
    ):
        # Create separate mock instances for each call
        failing_instances = [mock.MagicMock() for _ in range(3)]
        for instance in failing_instances:
            instance.ping.side_effect = redis.exceptions.ConnectionError("Initial fail")
        successful_instance = mock.MagicMock()
        successful_instance.ping.return_value = True
        expected_pairs = ["btcusd", "ethusd"]
        successful_instance.get.return_value = json.dumps(expected_pairs)
        # Set up the side_effect with the instances
        MockRedis.side_effect = failing_instances + [successful_instance]

        client = RedisCryptoClient(host="localhost", port=6379)  # __init__ fails
        self.assertIsNone(client.client)

        pairs = client.get_top_crypto_pairs_from_redis("test_key")

        self.assertEqual(pairs, expected_pairs)
        self.assertEqual(
            MockRedis.call_count, 4
        )  # 3 for __init__ retries + 1 for get_top_crypto's _connect
        successful_instance.get.assert_called_once_with("test_key")

    @mock.patch("redis.Redis")
    def test_close_client(self, MockRedis):
        mock_redis_instance = MockRedis.return_value
        mock_redis_instance.ping.return_value = True
        client = RedisCryptoClient(host="localhost", port=6379)
        self.assertIsNotNone(client.client)

        client.close()
        mock_redis_instance.close.assert_called_once()
        self.assertIsNone(client.client)

    @mock.patch("redis.Redis")
    def test_close_client_no_initial_connection(self, MockRedis):
        MockRedis.side_effect = redis.exceptions.ConnectionError("No connect")
        client = RedisCryptoClient(host="localhost", port=6379)
        self.assertIsNone(client.client)
        client.close()  # Should not raise an error
        # Since client.client is None, close() should not attempt to call close on any redis instance


if __name__ == "__main__":
    unittest.main()
