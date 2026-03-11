import unittest
from unittest import mock
import json
import redis

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver

from services.top_crypto_updater import main as top_crypto_updater_main
from services.top_crypto_updater.redis_client import RedisManager


FLAGS = flags.FLAGS


class TopCryptoUpdaterMainTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        top_crypto_updater_main._redis_manager = None

        self.patch_get_top_n = mock.patch(
            "services.top_crypto_updater.main.get_top_n_crypto_symbols"
        )
        self.mock_get_top_n_symbols = self.patch_get_top_n.start()
        self.addCleanup(self.patch_get_top_n.stop)

        self.patch_redis_manager = mock.patch(
            "services.top_crypto_updater.main.RedisManager"
        )
        self.mock_redis_manager_constructor = self.patch_redis_manager.start()
        self.mock_redis_instance = mock.MagicMock(spec=RedisManager)
        self.addCleanup(self.patch_redis_manager.stop)

        self.saved_flags = flagsaver.save_flag_values()
        FLAGS.cmc_api_key = "dummy_cmc_for_test_main"
        FLAGS.redis_host = "dummy_redis_host_main"

    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        top_crypto_updater_main._redis_manager = None
        super().tearDown()

    def test_update_top_cryptos_success(self):
        FLAGS.cmc_api_key = "fake_cmc_key"
        FLAGS.redis_host = "fakeredis"
        FLAGS.top_n_cryptos = 5
        FLAGS.redis_key = "test_top_cryptos"

        expected_symbols = ["btcusd", "ethusd", "adausd", "solusd", "dogeusd"]
        self.mock_get_top_n_symbols.return_value = expected_symbols

        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.mock_redis_instance.get_client.return_value = True
        self.mock_redis_instance.set_value.return_value = True

        top_crypto_updater_main._update_top_cryptos()

        self.mock_get_top_n_symbols.assert_called_once_with("fake_cmc_key", 5)
        self.mock_redis_instance.set_value.assert_called_once_with(
            "test_top_cryptos", json.dumps(expected_symbols)
        )

    def test_update_no_symbols_logs_warning(self):
        FLAGS.cmc_api_key = "fake_cmc_key"
        self.mock_get_top_n_symbols.return_value = []

        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.mock_redis_instance.get_client.return_value = True

        top_crypto_updater_main._update_top_cryptos()

        self.mock_get_top_n_symbols.assert_called_once()
        self.mock_redis_instance.set_value.assert_not_called()

    def test_update_redis_set_failure_logs_error(self):
        FLAGS.cmc_api_key = "fake_cmc_key"
        expected_symbols = ["btcusd"]
        self.mock_get_top_n_symbols.return_value = expected_symbols

        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.mock_redis_instance.get_client.return_value = True
        self.mock_redis_instance.set_value.return_value = False

        top_crypto_updater_main._update_top_cryptos()

        self.mock_redis_instance.set_value.assert_called_once()

    @mock.patch("services.top_crypto_updater.main.ServiceRunner")
    def test_main_creates_service_runner(self, mock_runner_cls):
        FLAGS.cmc_api_key = "fake_cmc_key"
        mock_runner = mock.MagicMock()
        mock_runner_cls.return_value = mock_runner

        top_crypto_updater_main.main(None)

        mock_runner_cls.assert_called_once()
        call_kwargs = mock_runner_cls.call_args
        self.assertEqual(call_kwargs.kwargs["service_name"], "top_crypto_updater")
        mock_runner.run.assert_called_once()

    @flagsaver.flagsaver(cmc_api_key="")
    def test_main_no_cmc_api_key_exits(self):
        with self.assertRaises(SystemExit) as cm:
            top_crypto_updater_main.main(None)
        self.assertEqual(cm.exception.code, 1)

    def test_initialize_redis_connection_failure(self):
        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.mock_redis_instance.get_client.return_value = False

        with self.assertRaises(ConnectionError):
            top_crypto_updater_main._initialize_redis()


if __name__ == "__main__":
    absltest.main()
