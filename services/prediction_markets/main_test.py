"""Tests for the prediction market integration service main module."""

from unittest import mock
from absl.testing import absltest
from absl import flags

from services.prediction_markets.main import (
    _build_kalshi_client,
    _build_polymarket_client,
    _categorize_kalshi_market,
    _run_check,
)
from services.prediction_markets.signal_generator import (
    PredictionMarketSignalGenerator,
    ThresholdConfig,
)
from services.prediction_markets.insider_detector import InsiderActivityDetector
from services.prediction_markets.correlation_tracker import CorrelationTracker


FLAGS = flags.FLAGS


class CategorizeKalshiMarketTest(absltest.TestCase):
    def test_fed_market(self):
        market = {"ticker": "FED-26MAR-T3.50", "series_ticker": "FED"}
        self.assertEqual(_categorize_kalshi_market(market), "monetary_policy")

    def test_btc_etf_market(self):
        market = {"ticker": "BTCETF-APR", "series_ticker": "BTCETF"}
        self.assertEqual(_categorize_kalshi_market(market), "btc_etf")

    def test_eth_etf_market(self):
        market = {"ticker": "ETHETF-MAR", "series_ticker": "ETHETF"}
        self.assertEqual(_categorize_kalshi_market(market), "eth_etf")

    def test_sec_market(self):
        market = {"ticker": "SEC-RULING-1", "series_ticker": "SEC"}
        self.assertEqual(_categorize_kalshi_market(market), "regulatory")

    def test_election_market(self):
        market = {"ticker": "ELECTION-2026", "series_ticker": "PRES"}
        self.assertEqual(_categorize_kalshi_market(market), "political")

    def test_economic_market(self):
        market = {"ticker": "CPI-MAR-26", "series_ticker": "ECON"}
        self.assertEqual(_categorize_kalshi_market(market), "economic")

    def test_unknown_defaults_to_crypto(self):
        market = {"ticker": "UNKNOWN-1", "series_ticker": "OTHER"}
        self.assertEqual(_categorize_kalshi_market(market), "crypto_specific")


class RunCheckTest(absltest.TestCase):
    def setUp(self):
        self.signal_gen = PredictionMarketSignalGenerator(config=ThresholdConfig())
        self.insider_detector = InsiderActivityDetector()
        self.correlation_tracker = CorrelationTracker()

    def test_run_check_with_no_clients(self):
        signals = _run_check(
            polymarket_client=None,
            kalshi_client=None,
            signal_gen=self.signal_gen,
            insider_detector=self.insider_detector,
            correlation_tracker=self.correlation_tracker,
        )
        self.assertEqual(len(signals), 0)

    def test_run_check_with_mock_kalshi(self):
        mock_kalshi = mock.MagicMock()
        mock_kalshi.get_crypto_relevant_markets_safe.return_value = {
            "markets": [
                {
                    "ticker": "FED-T3.50",
                    "title": "Fed Rate Cut",
                    "series_ticker": "FED",
                    "yes_price": 0.75,
                    "previous_yes_price": 0.60,
                    "volume": 10000,
                }
            ],
            "available": True,
        }

        signals = _run_check(
            polymarket_client=None,
            kalshi_client=mock_kalshi,
            signal_gen=self.signal_gen,
            insider_detector=self.insider_detector,
            correlation_tracker=self.correlation_tracker,
        )

        mock_kalshi.get_crypto_relevant_markets_safe.assert_called_once()
        # Should generate signals for the threshold crossing
        self.assertGreater(len(signals), 0)

    def test_run_check_with_mock_polymarket(self):
        mock_poly = mock.MagicMock()
        mock_poly.get_recent_alerts_safe.return_value = {
            "data": [
                {
                    "wallet_address": "0x7a3f91",
                    "market_id": "m1",
                    "market_question": "Fed Rate",
                    "side": "BUY",
                    "position_size": 15000,
                    "price": 0.75,
                    "confidence": "HIGH",
                }
            ],
        }

        signals = _run_check(
            polymarket_client=mock_poly,
            kalshi_client=None,
            signal_gen=self.signal_gen,
            insider_detector=self.insider_detector,
            correlation_tracker=self.correlation_tracker,
        )

        mock_poly.get_recent_alerts_safe.assert_called_once()
        insider_signals = [
            s for s in signals if s.signal_type.value == "insider_activity"
        ]
        self.assertGreater(len(insider_signals), 0)


if __name__ == "__main__":
    absltest.main()
