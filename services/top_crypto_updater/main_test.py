import os
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

_MODULE = "services.top_crypto_updater.main"


class TopCryptoUpdaterMainTest(absltest.TestCase):
    def setUp(self):
        super().setUp()
        top_crypto_updater_main.redis_manager_global = None  # Ensure it's reset

        self.patch_get_top_n = mock.patch(f"{_MODULE}.get_top_n_crypto_symbols")
        self.mock_get_top_n_symbols = self.patch_get_top_n.start()
        self.addCleanup(self.patch_get_top_n.stop)

        self.patch_redis_manager = mock.patch(f"{_MODULE}.RedisManager")
        self.mock_redis_manager_constructor = self.patch_redis_manager.start()
        self.mock_redis_instance = mock.MagicMock(spec=RedisManager)

        # Mock cmc_api_key and RedisConfig from credentials module
        self.patch_cmc_api_key = mock.patch(f"{_MODULE}.cmc_api_key")
        self.mock_cmc_api_key = self.patch_cmc_api_key.start()
        self.mock_cmc_api_key.return_value = "dummy_cmc_for_test_main"
        self.addCleanup(self.patch_cmc_api_key.stop)

        self.patch_redis_config = mock.patch(f"{_MODULE}.RedisConfig")
        self.mock_redis_config_cls = self.patch_redis_config.start()
        self.mock_redis_config = mock.MagicMock()
        self.mock_redis_config.host = "dummy_redis_host_main"
        self.mock_redis_config.port = 6379
        self.mock_redis_config.password = None
        self.mock_redis_config_cls.return_value = self.mock_redis_config
        self.addCleanup(self.patch_redis_config.stop)

        self.saved_flags = flagsaver.save_flag_values()

    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        top_crypto_updater_main.redis_manager_global = None  # Clean up global
        super().tearDown()

    def test_main_success_flow(self):
        # Arrange
        self.mock_cmc_api_key.return_value = "fake_cmc_key"
        self.mock_redis_config.host = "fakeredis"
        FLAGS.top_n_cryptos = 5
        FLAGS.redis_key = "test_top_cryptos"

        expected_symbols = ["btcusd", "ethusd", "adausd", "solusd", "dogeusd"]
        self.mock_get_top_n_symbols.return_value = expected_symbols

        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.mock_redis_instance.get_client.return_value = True
        self.mock_redis_instance.set_value.return_value = True

        # Act
        top_crypto_updater_main.main(None)

        # Assert
        self.mock_get_top_n_symbols.assert_called_once_with("fake_cmc_key", 5)
        self.mock_redis_manager_constructor.assert_called_once_with(
            host="fakeredis", port=6379, password=None
        )
        self.mock_redis_instance.set_value.assert_called_once_with(
            "test_top_cryptos", json.dumps(expected_symbols)
        )
        self.mock_redis_instance.close.assert_called_once()

    def test_main_no_cmc_api_key_exits(self):
        self.mock_cmc_api_key.side_effect = SystemExit(1)
        with self.assertRaises(SystemExit) as cm:
            top_crypto_updater_main.main(None)
        self.assertEqual(cm.exception.code, 1)
        self.mock_get_top_n_symbols.assert_not_called()

    @mock.patch(f"{_MODULE}.sys.exit")  # Mock sys.exit
    def test_main_redis_connection_failure_exits(self, mock_sys_exit):
        self.mock_cmc_api_key.return_value = "fake_cmc_key"
        # Simulate RedisManager constructor failing
        self.mock_redis_manager_constructor.side_effect = (
            redis.exceptions.ConnectionError("Mock connection failed")
        )

        # Make the mock sys.exit actually raise SystemExit to simulate real behavior
        def side_effect(code):
            raise SystemExit(code)

        mock_sys_exit.side_effect = side_effect

        with self.assertRaises(SystemExit) as cm:
            top_crypto_updater_main.main(None)

        self.assertEqual(cm.exception.code, 1)
        mock_sys_exit.assert_called_once_with(1)
        self.mock_redis_manager_constructor.assert_called_once()
        # Ensure close was not called since the manager was never successfully created
        self.mock_redis_instance.close.assert_not_called()

    def test_main_cmc_fetch_fails_logs_warning_but_completes(self):
        self.mock_cmc_api_key.return_value = "fake_cmc_key"
        self.mock_get_top_n_symbols.return_value = []  # Simulate no symbols returned

        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.mock_redis_instance.get_client.return_value = True

        with mock.patch.object(
            top_crypto_updater_main.logging, "warning"
        ) as mock_log_warning:
            top_crypto_updater_main.main(None)

        self.mock_get_top_n_symbols.assert_called_once()
        mock_log_warning.assert_any_call(
            "No symbols fetched from CoinMarketCap. Nothing to update in Redis."
        )
        self.mock_redis_instance.set_value.assert_not_called()
        self.mock_redis_instance.close.assert_called_once()

    def test_main_redis_set_value_fails_logs_error(self):
        self.mock_cmc_api_key.return_value = "fake_cmc_key"
        expected_symbols = ["btcusd"]
        self.mock_get_top_n_symbols.return_value = expected_symbols

        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.mock_redis_instance.get_client.return_value = True
        self.mock_redis_instance.set_value.return_value = False  # Simulate set failure

        with mock.patch.object(
            top_crypto_updater_main.logging, "error"
        ) as mock_log_error:
            top_crypto_updater_main.main(None)

        self.mock_redis_instance.set_value.assert_called_once_with(
            FLAGS.redis_key, json.dumps(expected_symbols)
        )
        mock_log_error.assert_any_call(
            f"Failed to update Redis key '{FLAGS.redis_key}'."
        )
        self.mock_redis_instance.close.assert_called_once()

    @mock.patch(f"{_MODULE}.signal")
    def test_main_registers_signal_handlers(self, mock_signal_module):
        self.mock_cmc_api_key.return_value = "fake_cmc_key"
        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.mock_redis_instance.get_client.return_value = True
        self.mock_get_top_n_symbols.return_value = ["btcusd"]
        self.mock_redis_instance.set_value.return_value = True

        top_crypto_updater_main.main(None)

        mock_signal_module.signal.assert_any_call(
            mock_signal_module.SIGINT, top_crypto_updater_main.handle_shutdown_signal
        )
        mock_signal_module.signal.assert_any_call(
            mock_signal_module.SIGTERM, top_crypto_updater_main.handle_shutdown_signal
        )

    @mock.patch(f"{_MODULE}.sys.exit")
    @mock.patch(f"{_MODULE}.signal.Signals")
    def test_handle_shutdown_signal(self, mock_signals_enum, mock_sys_exit):
        mock_signals_enum.return_value.name = "SIGTEST"

        # Simulate Redis manager being set globally
        mock_redis_mgr_global_instance = mock.MagicMock(spec=RedisManager)
        top_crypto_updater_main.redis_manager_global = mock_redis_mgr_global_instance

        top_crypto_updater_main.handle_shutdown_signal(15, None)  # 15 is SIGTERM

        mock_redis_mgr_global_instance.close.assert_called_once()
        mock_sys_exit.assert_called_once_with(0)


if __name__ == "__main__":
    absltest.main()
