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

    def test_second_token_parsed(self):
        proto = main_module._parse_market_to_proto(SAMPLE_MARKET)
        self.assertEqual(proto.tokens[1].token_id, "token_no_1")
        self.assertEqual(proto.tokens[1].outcome, "No")
        self.assertAlmostEqual(proto.tokens[1].price, 0.35, places=2)

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

    def test_invalid_liquidity_defaults_to_zero(self):
        market = dict(SAMPLE_MARKET, liquidity="invalid")
        proto = main_module._parse_market_to_proto(market)
        self.assertAlmostEqual(proto.liquidity, 0.0)

    def test_none_volume_defaults_to_zero(self):
        market = dict(SAMPLE_MARKET, volume=None)
        proto = main_module._parse_market_to_proto(market)
        self.assertAlmostEqual(proto.volume, 0.0)

    def test_description_truncated_at_1000_chars(self):
        long_desc = "x" * 2000
        market = dict(SAMPLE_MARKET, description=long_desc)
        proto = main_module._parse_market_to_proto(market)
        self.assertEqual(len(proto.description), 1000)

    def test_description_under_limit_preserved(self):
        market = dict(SAMPLE_MARKET, description="short desc")
        proto = main_module._parse_market_to_proto(market)
        self.assertEqual(proto.description, "short desc")

    def test_end_date_parsed(self):
        proto = main_module._parse_market_to_proto(SAMPLE_MARKET)
        self.assertTrue(proto.HasField("end_date"))
        # Verify it parsed to a non-zero timestamp (exact value depends on timezone)
        self.assertGreater(proto.end_date.seconds, 0)

    def test_invalid_end_date_ignored(self):
        market = dict(SAMPLE_MARKET, end_date_iso="not-a-date")
        proto = main_module._parse_market_to_proto(market)
        # Should not crash, end_date stays at default
        self.assertEqual(proto.end_date.seconds, 0)

    def test_missing_end_date_ignored(self):
        market = {k: v for k, v in SAMPLE_MARKET.items() if k != "end_date_iso"}
        proto = main_module._parse_market_to_proto(market)
        self.assertEqual(proto.end_date.seconds, 0)

    def test_market_slug_mapped_to_resolution_source(self):
        proto = main_module._parse_market_to_proto(SAMPLE_MARKET)
        self.assertEqual(proto.resolution_source, "btc-100k-2025")

    def test_no_tokens(self):
        market = dict(SAMPLE_MARKET, tokens=[])
        proto = main_module._parse_market_to_proto(market)
        self.assertEqual(len(proto.tokens), 0)

    def test_token_with_invalid_price(self):
        market = dict(
            SAMPLE_MARKET,
            tokens=[{"token_id": "t1", "outcome": "Yes", "price": "invalid"}],
        )
        proto = main_module._parse_market_to_proto(market)
        self.assertAlmostEqual(proto.tokens[0].price, 0.0)

    def test_token_missing_fields(self):
        market = dict(SAMPLE_MARKET, tokens=[{}])
        proto = main_module._parse_market_to_proto(market)
        self.assertEqual(proto.tokens[0].token_id, "")
        self.assertEqual(proto.tokens[0].outcome, "")

    def test_closed_market(self):
        market = dict(SAMPLE_MARKET, active=False, closed=True)
        proto = main_module._parse_market_to_proto(market)
        self.assertFalse(proto.active)
        self.assertTrue(proto.closed)


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

    @flagsaver.flagsaver(orderbook_top_n=10)
    def test_orderbook_empty_bids_and_asks(self):
        proto = main_module._parse_orderbook_to_proto(
            "token1", "market1", {"bids": [], "asks": []}
        )
        self.assertEqual(len(proto.bids), 0)
        self.assertEqual(len(proto.asks), 0)

    @flagsaver.flagsaver(orderbook_top_n=10)
    def test_orderbook_missing_bids_and_asks_keys(self):
        proto = main_module._parse_orderbook_to_proto("token1", "market1", {})
        self.assertEqual(len(proto.bids), 0)
        self.assertEqual(len(proto.asks), 0)

    @flagsaver.flagsaver(orderbook_top_n=10)
    def test_orderbook_has_timestamp(self):
        proto = main_module._parse_orderbook_to_proto(
            "token123", "market456", SAMPLE_ORDERBOOK
        )
        self.assertTrue(proto.HasField("timestamp"))
        self.assertGreater(proto.timestamp.seconds, 0)

    @flagsaver.flagsaver(orderbook_top_n=10)
    def test_orderbook_bid_values(self):
        proto = main_module._parse_orderbook_to_proto(
            "t1", "m1", SAMPLE_ORDERBOOK
        )
        self.assertAlmostEqual(proto.bids[0].price, 0.60)
        self.assertAlmostEqual(proto.bids[0].size, 100.0)
        self.assertAlmostEqual(proto.bids[1].price, 0.58)
        self.assertAlmostEqual(proto.bids[1].size, 200.0)

    @flagsaver.flagsaver(orderbook_top_n=10)
    def test_orderbook_ask_values(self):
        proto = main_module._parse_orderbook_to_proto(
            "t1", "m1", SAMPLE_ORDERBOOK
        )
        self.assertAlmostEqual(proto.asks[0].price, 0.65)
        self.assertAlmostEqual(proto.asks[0].size, 150.0)
        self.assertAlmostEqual(proto.asks[1].price, 0.67)
        self.assertAlmostEqual(proto.asks[1].size, 75.0)


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

    @flagsaver.flagsaver(
        run_mode="wet", max_pages=1, kafka_topic_markets="test-markets"
    )
    def test_wet_run_publish_uses_market_id_as_key(self):
        mock_api = mock.MagicMock()
        mock_api.get_all_active_markets.return_value = [SAMPLE_MARKET]
        mock_kafka = mock.MagicMock()

        main_module._ingest_markets(mock_api, kafka_producer=mock_kafka)

        call_kwargs = mock_kafka.publish.call_args
        self.assertEqual(call_kwargs[1]["key"], "0xabc123")

    @flagsaver.flagsaver(run_mode="dry", max_pages=1)
    def test_empty_markets_returns_zero(self):
        mock_api = mock.MagicMock()
        mock_api.get_all_active_markets.return_value = []

        count = main_module._ingest_markets(mock_api, kafka_producer=None)

        self.assertEqual(count, 0)

    @flagsaver.flagsaver(run_mode="dry", max_pages=1)
    def test_multiple_markets(self):
        mock_api = mock.MagicMock()
        mock_api.get_all_active_markets.return_value = [
            SAMPLE_MARKET,
            dict(SAMPLE_MARKET, condition_id="0xdef456"),
            dict(SAMPLE_MARKET, condition_id="0xghi789"),
        ]

        count = main_module._ingest_markets(mock_api, kafka_producer=None)

        self.assertEqual(count, 3)

    @flagsaver.flagsaver(
        run_mode="wet", max_pages=1, kafka_topic_markets="test-markets"
    )
    def test_wet_run_no_kafka_producer_does_not_publish(self):
        """When run_mode is wet but kafka_producer is None, no publish happens."""
        mock_api = mock.MagicMock()
        mock_api.get_all_active_markets.return_value = [SAMPLE_MARKET]

        count = main_module._ingest_markets(mock_api, kafka_producer=None)

        # Count still increments (market was processed)
        self.assertEqual(count, 1)

    @flagsaver.flagsaver(run_mode="dry", max_pages=5)
    def test_max_pages_passed_to_api(self):
        mock_api = mock.MagicMock()
        mock_api.get_all_active_markets.return_value = []

        main_module._ingest_markets(mock_api, kafka_producer=None)

        mock_api.get_all_active_markets.assert_called_once_with(max_pages=5)


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
        run_mode="wet", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_wet_run_uses_token_id_as_key(self):
        mock_api = mock.MagicMock()
        mock_api.get_order_book.return_value = SAMPLE_ORDERBOOK
        mock_kafka = mock.MagicMock()

        main_module._ingest_orderbooks(
            mock_api, [SAMPLE_MARKET], kafka_producer=mock_kafka
        )

        first_call_kwargs = mock_kafka.publish.call_args_list[0]
        self.assertEqual(first_call_kwargs[1]["key"], "token_yes_1")
        second_call_kwargs = mock_kafka.publish.call_args_list[1]
        self.assertEqual(second_call_kwargs[1]["key"], "token_no_1")

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

    @flagsaver.flagsaver(
        run_mode="dry", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_empty_markets_list(self):
        mock_api = mock.MagicMock()

        count = main_module._ingest_orderbooks(mock_api, [], kafka_producer=None)

        self.assertEqual(count, 0)
        mock_api.get_order_book.assert_not_called()

    @flagsaver.flagsaver(
        run_mode="dry", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_token_with_empty_id_skipped(self):
        """Tokens with empty token_id are skipped."""
        market = dict(
            SAMPLE_MARKET,
            tokens=[
                {"token_id": "", "outcome": "Yes", "price": "0.5"},
                {"token_id": "valid_token", "outcome": "No", "price": "0.5"},
            ],
        )
        mock_api = mock.MagicMock()
        mock_api.get_order_book.return_value = SAMPLE_ORDERBOOK

        count = main_module._ingest_orderbooks(
            mock_api, [market], kafka_producer=None
        )

        self.assertEqual(count, 1)
        mock_api.get_order_book.assert_called_once_with("valid_token")

    @flagsaver.flagsaver(
        run_mode="dry", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_partial_api_failure_processes_remaining(self):
        """If one token fails, other tokens in the same market still process."""
        mock_api = mock.MagicMock()
        mock_api.get_order_book.side_effect = [
            Exception("API Error"),
            SAMPLE_ORDERBOOK,
        ]

        count = main_module._ingest_orderbooks(
            mock_api, [SAMPLE_MARKET], kafka_producer=None
        )

        self.assertEqual(count, 1)

    @flagsaver.flagsaver(
        run_mode="dry", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_market_with_no_tokens(self):
        market = dict(SAMPLE_MARKET, tokens=[])
        mock_api = mock.MagicMock()

        count = main_module._ingest_orderbooks(
            mock_api, [market], kafka_producer=None
        )

        self.assertEqual(count, 0)
        mock_api.get_order_book.assert_not_called()

    @flagsaver.flagsaver(
        run_mode="wet", kafka_topic_orderbook="test-orderbook", orderbook_top_n=10
    )
    def test_wet_run_publishes_to_correct_topic(self):
        mock_api = mock.MagicMock()
        mock_api.get_order_book.return_value = SAMPLE_ORDERBOOK
        mock_kafka = mock.MagicMock()

        main_module._ingest_orderbooks(
            mock_api, [SAMPLE_MARKET], kafka_producer=mock_kafka
        )

        for call in mock_kafka.publish.call_args_list:
            self.assertEqual(call[0][0], "test-orderbook")


class RunFunctionTest(absltest.TestCase):
    @flagsaver.flagsaver(
        run_mode="dry",
        max_pages=1,
        polymarket_api_url="https://test.polymarket.com",
        api_request_timeout=5,
    )
    @mock.patch(
        "services.polymarket_ingestor.main._ingest_orderbooks", return_value=2
    )
    @mock.patch(
        "services.polymarket_ingestor.main._ingest_markets", return_value=1
    )
    @mock.patch(
        "services.polymarket_ingestor.main.PolymarketApiClient"
    )
    def test_dry_run_does_not_create_kafka_producer(
        self, mock_api_cls, mock_ingest_markets, mock_ingest_orderbooks
    ):
        mock_api_instance = mock.MagicMock()
        mock_api_instance.get_all_active_markets.return_value = []
        mock_api_cls.return_value = mock_api_instance

        main_module.run()

        # In dry mode, kafka_producer should be None
        mock_ingest_markets.assert_called_once()
        call_args = mock_ingest_markets.call_args
        # Second positional arg or kafka_producer kwarg should be None
        kafka_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("kafka_producer")
        self.assertIsNone(kafka_arg)

    @flagsaver.flagsaver(
        run_mode="dry",
        max_pages=1,
        polymarket_api_url="https://test.polymarket.com",
        api_request_timeout=5,
    )
    @mock.patch(
        "services.polymarket_ingestor.main.PolymarketApiClient"
    )
    def test_run_closes_api_client(self, mock_api_cls):
        mock_api_instance = mock.MagicMock()
        mock_api_instance.get_all_active_markets.return_value = []
        mock_api_cls.return_value = mock_api_instance

        main_module.run()

        mock_api_instance.close.assert_called_once()

    @flagsaver.flagsaver(
        run_mode="dry",
        max_pages=1,
        polymarket_api_url="https://test.polymarket.com",
        api_request_timeout=5,
    )
    @mock.patch(
        "services.polymarket_ingestor.main.PolymarketApiClient"
    )
    def test_run_closes_api_client_on_error(self, mock_api_cls):
        mock_api_instance = mock.MagicMock()
        mock_api_instance.get_all_active_markets.side_effect = RuntimeError("boom")
        mock_api_cls.return_value = mock_api_instance

        with self.assertRaises(RuntimeError):
            main_module.run()

        mock_api_instance.close.assert_called_once()

    @flagsaver.flagsaver(
        run_mode="dry",
        max_pages=1,
        polymarket_api_url="https://test.polymarket.com",
        api_request_timeout=5,
    )
    @mock.patch(
        "services.polymarket_ingestor.main.PolymarketApiClient"
    )
    def test_run_filters_active_markets_for_orderbooks(self, mock_api_cls):
        """Only active, non-closed markets are passed to orderbook ingestion."""
        active_market = dict(SAMPLE_MARKET, condition_id="active1", active=True, closed=False)
        closed_market = dict(SAMPLE_MARKET, condition_id="closed1", active=True, closed=True)
        inactive_market = dict(SAMPLE_MARKET, condition_id="inactive1", active=False, closed=False)

        mock_api_instance = mock.MagicMock()
        # First call for _ingest_markets, second call for orderbooks
        mock_api_instance.get_all_active_markets.return_value = [
            active_market,
            closed_market,
            inactive_market,
        ]
        mock_api_cls.return_value = mock_api_instance
        mock_api_instance.get_order_book.return_value = SAMPLE_ORDERBOOK

        main_module.run()

        # Orderbook should only be fetched for the active, non-closed market's tokens
        # The active_market has 2 tokens from SAMPLE_MARKET
        self.assertEqual(mock_api_instance.get_order_book.call_count, 2)


class SignalHandlerTest(absltest.TestCase):
    def setUp(self):
        # Reset shutdown state before each test
        main_module._shutdown_requested = False

    def tearDown(self):
        main_module._shutdown_requested = False

    def test_signal_handler_sets_shutdown_flag(self):
        self.assertFalse(main_module._shutdown_requested)
        main_module._signal_handler(2, None)
        self.assertTrue(main_module._shutdown_requested)


if __name__ == "__main__":
    absltest.main()
