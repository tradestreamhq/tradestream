"""Tests for the Polymarket Data Ingestor main module."""

from unittest import mock
from absl.testing import absltest, flagsaver

from services.polymarket_ingestor import main as main_module


SAMPLE_MARKET = {
    "condition_id": "0xabc123",
    "question": "Will BTC reach 100k by end of 2025?",
    "description": "This market resolves YES if Bitcoin reaches $100,000.",
    "market_slug": "btc-100k-2025",
    "active": True,
    "closed": False,
    "volume": "1500000.50",
    "liquidity": "250000.00",
    "end_date_iso": "2025-12-31T23:59:59Z",
    "tokens": [
        {"token_id": "token_yes_1", "outcome": "Yes", "price": "0.65"},
        {"token_id": "token_no_1", "outcome": "No", "price": "0.35"},
    ],
}

SAMPLE_ORDERBOOK = {
    "bids": [
        {"price": "0.60", "size": "100"},
        {"price": "0.58", "size": "200"},
    ],
    "asks": [
        {"price": "0.65", "size": "150"},
        {"price": "0.67", "size": "75"},
    ],
}


class ParseMarketToProtoTest(absltest.TestCase):
    def test_basic_market_parsing(self):
        proto = main_module._parse_market_to_proto(SAMPLE_MARKET)
        self.assertEqual(proto.market_id, "0xabc123")
        self.assertEqual(proto.condition_id, "0xabc123")
        self.assertIn("BTC", proto.question)
        self.assertTrue(proto.active)
        self.assertFalse(proto.closed)
        self.assertAlmostEqual(proto.volume, 1500000.50, places=2)
        self.assertAlmostEqual(proto.liquidity, 250000.00, places=2)

    def test_tokens_parsed(self):
        proto = main_module._parse_market_to_proto(SAMPLE_MARKET)
        self.assertEqual(len(proto.tokens), 2)
        self.assertEqual(proto.tokens[0].token_id, "token_yes_1")
        self.assertEqual(proto.tokens[0].outcome, "Yes")
        self.assertAlmostEqual(proto.tokens[0].price, 0.65, places=2)

    def test_missing_fields_defaults(self):
        proto = main_module._parse_market_to_proto({})
        self.assertEqual(proto.market_id, "")
        self.assertEqual(proto.question, "")
        self.assertFalse(proto.active)
        self.assertAlmostEqual(proto.volume, 0.0)

    def test_invalid_volume_defaults_to_zero(self):
        market = dict(SAMPLE_MARKET, volume="not_a_number")
        proto = main_module._parse_market_to_proto(market)
        self.assertAlmostEqual(proto.volume, 0.0)


class ParseOrderBookToProtoTest(absltest.TestCase):
    @flagsaver.flagsaver(orderbook_top_n=10)
    def test_basic_orderbook_parsing(self):
        proto = main_module._parse_orderbook_to_proto(
            "token123", "market456", SAMPLE_ORDERBOOK
        )
        self.assertEqual(proto.market_id, "market456")
        self.assertEqual(proto.asset_id, "token123")
        self.assertEqual(len(proto.bids), 2)
        self.assertEqual(len(proto.asks), 2)
        self.assertAlmostEqual(proto.bids[0].price, 0.60)
        self.assertAlmostEqual(proto.asks[0].size, 150.0)

    @flagsaver.flagsaver(orderbook_top_n=1)
    def test_orderbook_top_n_limits(self):
        proto = main_module._parse_orderbook_to_proto(
            "token123", "market456", SAMPLE_ORDERBOOK
        )
        self.assertEqual(len(proto.bids), 1)
        self.assertEqual(len(proto.asks), 1)


class IngestMarketsTest(absltest.TestCase):
    @flagsaver.flagsaver(run_mode="dry", max_pages=1)
    def test_dry_run_no_kafka(self):
        mock_api = mock.MagicMock()
        mock_api.get_all_active_markets.return_value = [SAMPLE_MARKET]

        count = main_module._ingest_markets(mock_api, kafka_producer=None)

        self.assertEqual(count, 1)
        mock_api.get_all_active_markets.assert_called_once()

    @flagsaver.flagsaver(
        run_mode="wet", max_pages=1, kafka_topic_markets="test-markets"
    )
    def test_wet_run_publishes_to_kafka(self):
        mock_api = mock.MagicMock()
        mock_api.get_all_active_markets.return_value = [SAMPLE_MARKET]
        mock_kafka = mock.MagicMock()

        count = main_module._ingest_markets(mock_api, kafka_producer=mock_kafka)

        self.assertEqual(count, 1)
        mock_kafka.publish.assert_called_once()
        call_args = mock_kafka.publish.call_args
        self.assertEqual(call_args[0][0], "test-markets")


class IngestOrderBooksTest(absltest.TestCase):
    @flagsaver.flagsaver(
        run_mode="dry", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_dry_run_orderbooks(self):
        mock_api = mock.MagicMock()
        mock_api.get_order_book.return_value = SAMPLE_ORDERBOOK

        count = main_module._ingest_orderbooks(
            mock_api, [SAMPLE_MARKET], kafka_producer=None
        )

        # 2 tokens in SAMPLE_MARKET
        self.assertEqual(count, 2)

    @flagsaver.flagsaver(
        run_mode="wet", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_wet_run_publishes_orderbooks(self):
        mock_api = mock.MagicMock()
        mock_api.get_order_book.return_value = SAMPLE_ORDERBOOK
        mock_kafka = mock.MagicMock()

        count = main_module._ingest_orderbooks(
            mock_api, [SAMPLE_MARKET], kafka_producer=mock_kafka
        )

        self.assertEqual(count, 2)
        self.assertEqual(mock_kafka.publish.call_count, 2)

    @flagsaver.flagsaver(
        run_mode="dry", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_orderbook_api_failure_continues(self):
        mock_api = mock.MagicMock()
        mock_api.get_order_book.side_effect = Exception("API Error")

        count = main_module._ingest_orderbooks(
            mock_api, [SAMPLE_MARKET], kafka_producer=None
        )

        self.assertEqual(count, 0)


if __name__ == "__main__":
    absltest.main()
