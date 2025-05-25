import unittest
from unittest import mock
import json

from absl import flags
from absl.testing import absltest
from absl.testing import flagsaver

from services.top_crypto_updater import main as top_crypto_updater_main
from services.top_crypto_updater.redis_client import RedisManager


FLAGS = flags.FLAGS


class TopCryptoUpdaterMainTest(absltest.TestCase):

    def setUp(self):
        super().setUp()
        # Reset global shutdown flag for each test
        top_crypto_updater_main.shutdown_requested = False
        top_crypto_updater_main.redis_manager_global = None

        # Mock shared CMC client
        self.patch_get_top_n = mock.patch(
            "services.top_crypto_updater.main.get_top_n_crypto_symbols"
        )
        self.mock_get_top_n_symbols = self.patch_get_top_n.start()
        self.addCleanup(self.patch_get_top_n.stop)

        # Mock RedisManager
        self.patch_redis_manager = mock.patch(
            "services.top_crypto_updater.main.RedisManager"
        )
        self.mock_redis_manager_constructor = self.patch_redis_manager.start()
        self.mock_redis_instance = mock.MagicMock(spec=RedisManager)
        self.mock_redis_manager_constructor.return_value = self.mock_redis_instance
        self.addCleanup(self.patch_redis_manager.stop)

        # Save and restore flags
        self.saved_flags = flagsaver.save_flag_values()

    def tearDown(self):
        flagsaver.restore_flag_values(self.saved_flags)
        top_crypto_updater_main.shutdown_requested = False
        top_crypto_updater_main.redis_manager_global = None
        super().tearDown()

    def test_main_success_flow(self):
        # Arrange
        FLAGS.cmc_api_key = "fake_cmc_key"
        FLAGS.redis_host = "fakeredis"
        FLAGS.top_n_cryptos = 5
        FLAGS.redis_key = "test_top_cryptos"

        expected_symbols = ["btcusd", "ethusd", "adausd", "solusd", "dogeusd"]
        self.mock_get_top_n_symbols.return_value = expected_symbols
        self.mock_redis_instance.get_client.return_value = (
            True  # Simulate successful connection
        )
        self.mock_redis_instance.set_value.return_value = True

        # Act
        top_crypto_updater_main.main(None)

        # Assert
        self.mock_get_top_n_symbols.assert_called_once_with("fake_cmc_key", 5)
        self.mock_redis_manager_constructor.assert_called_once_with(
            host="fakeredis", port=FLAGS.redis_port, password=None
        )
        self.mock_redis_instance.set_value.assert_called_once_with(
            "test_top_cryptos", json.dumps(expected_symbols)
        )
        self.mock_redis_instance.close.assert_called_once()

    def test_main_no_cmc_api_key_exits(self):
        FLAGS.cmc_api_key = ""  # Ensure it's empty
        with self.assertRaises(SystemExit) as cm:
            top_crypto_updater_main.main(None)
        self.assertEqual(cm.exception.code, 1)
        self.mock_get_top_n_symbols.assert_not_called()

    def test_main_redis_connection_failure_exits(self):
        FLAGS.cmc_api_key = "fake_cmc_key"
        self.mock_redis_instance.get_client.return_value = (
            None  # Simulate connection failure
        )

        with self.assertRaises(SystemExit) as cm:
            top_crypto_updater_main.main(None)
        self.assertEqual(cm.exception.code, 1)
        self.mock_get_top_n_symbols.assert_not_called()  # Should exit before CMC call
        self.mock_redis_instance.close.assert_called_once()  # Should still attempt close in finally

    def test_main_cmc_fetch_fails_logs_warning_but_completes(self):
        FLAGS.cmc_api_key = "fake_cmc_key"
        self.mock_get_top_n_symbols.return_value = []  # Simulate no symbols returned
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
        FLAGS.cmc_api_key = "fake_cmc_key"
        expected_symbols = ["btcusd"]
        self.mock_get_top_n_symbols.return_value = expected_symbols
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

    @mock.patch("services.top_crypto_updater.main.signal")
    def test_main_registers_signal_handlers(self, mock_signal_module):
        FLAGS.cmc_api_key = "fake_cmc_key"
        self.mock_redis_instance.get_client.return_value = True
        self.mock_get_top_n_symbols.return_value = ["btcusd"]

        top_crypto_updater_main.main(None)

        mock_signal_module.signal.assert_any_call(
            mock_signal_module.SIGINT, top_crypto_updater_main.handle_shutdown_signal
        )
        mock_signal_module.signal.assert_any_call(
            mock_signal_module.SIGTERM, top_crypto_updater_main.handle_shutdown_signal
        )

    @mock.patch("services.top_crypto_updater.main.sys.exit")
    @mock.patch(
        "services.top_crypto_updater.main.signal.Signals"
    )  # Mock to avoid issues with Signals(signum).name
    def test_handle_shutdown_signal(self, mock_signals_enum, mock_sys_exit):
        mock_signals_enum.return_value.name = "SIGTEST"
        # Simulate Redis manager being set
        mock_redis_mgr = mock.MagicMock(spec=RedisManager)
        top_crypto_updater_main.redis_manager_global = mock_redis_mgr

        top_crypto_updater_main.handle_shutdown_signal(15, None)  # 15 is SIGTERM

        mock_redis_mgr.close.assert_called_once()
        mock_sys_exit.assert_called_once_with(0)


if __name__ == "__main__":
    absltest.main()
