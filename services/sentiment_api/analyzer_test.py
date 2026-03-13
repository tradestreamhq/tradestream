"""Tests for the SentimentAnalyzer."""

import pytest

from services.sentiment_api.analyzer import SentimentAnalyzer
from services.sentiment_api.models import WhaleTrade


@pytest.fixture
def analyzer():
    return SentimentAnalyzer(whale_threshold=50_000.0)


class TestOrderBookImbalance:
    def test_balanced_book(self, analyzer):
        bids = [(100.0, 10.0), (99.0, 10.0)]
        asks = [(101.0, 10.0), (102.0, 10.0)]
        result = analyzer.compute_order_book_imbalance("BTC/USD", bids, asks, levels=2)
        assert result.imbalance_ratio == 0.0
        assert result.bid_volume == 20.0
        assert result.ask_volume == 20.0
        assert result.pair == "BTC/USD"

    def test_bid_heavy(self, analyzer):
        bids = [(100.0, 30.0), (99.0, 20.0)]
        asks = [(101.0, 5.0), (102.0, 5.0)]
        result = analyzer.compute_order_book_imbalance("ETH/USD", bids, asks, levels=2)
        # (50 - 10) / (50 + 10) = 40/60 = 0.666...
        assert result.imbalance_ratio > 0.6
        assert result.imbalance_ratio < 0.7

    def test_ask_heavy(self, analyzer):
        bids = [(100.0, 2.0)]
        asks = [(101.0, 10.0), (102.0, 10.0)]
        result = analyzer.compute_order_book_imbalance("BTC/USD", bids, asks, levels=5)
        assert result.imbalance_ratio < 0.0

    def test_empty_book(self, analyzer):
        result = analyzer.compute_order_book_imbalance("BTC/USD", [], [], levels=10)
        assert result.imbalance_ratio == 0.0
        assert result.bid_volume == 0.0
        assert result.ask_volume == 0.0

    def test_levels_capped(self, analyzer):
        bids = [(100.0, 1.0)] * 3
        asks = [(101.0, 1.0)] * 3
        result = analyzer.compute_order_book_imbalance("BTC/USD", bids, asks, levels=2)
        assert result.bid_volume == 2.0
        assert result.ask_volume == 2.0


class TestTradeFlow:
    def test_all_buys(self, analyzer):
        trades = [
            {"side": "buy", "price": 100.0, "size": 5.0},
            {"side": "buy", "price": 100.0, "size": 3.0},
        ]
        result = analyzer.compute_trade_flow("BTC/USD", trades, window_seconds=60)
        assert result.flow_ratio == 1.0
        assert result.buy_count == 2
        assert result.sell_count == 0
        assert result.buy_volume == 8.0

    def test_all_sells(self, analyzer):
        trades = [
            {"side": "sell", "price": 100.0, "size": 5.0},
        ]
        result = analyzer.compute_trade_flow("BTC/USD", trades, window_seconds=60)
        assert result.flow_ratio == -1.0
        assert result.sell_volume == 5.0

    def test_balanced_flow(self, analyzer):
        trades = [
            {"side": "buy", "price": 100.0, "size": 10.0},
            {"side": "sell", "price": 100.0, "size": 10.0},
        ]
        result = analyzer.compute_trade_flow("BTC/USD", trades)
        assert result.flow_ratio == 0.0
        assert result.net_flow == 0.0

    def test_empty_trades(self, analyzer):
        result = analyzer.compute_trade_flow("BTC/USD", [])
        assert result.flow_ratio == 0.0
        assert result.buy_count == 0


class TestWhaleDetection:
    def test_detects_whale(self, analyzer):
        trades = [
            {"side": "buy", "price": 60000.0, "size": 1.0, "timestamp": "2026-01-01T00:00:00Z"},
            {"side": "sell", "price": 60000.0, "size": 0.5, "timestamp": "2026-01-01T00:01:00Z"},
        ]
        whales = analyzer.detect_whale_trades("BTC/USD", trades)
        # 60000 * 1.0 = 60000 >= 50000 threshold → whale
        # 60000 * 0.5 = 30000 < 50000 → not whale
        assert len(whales) == 1
        assert whales[0].side == "buy"
        assert whales[0].notional == 60000.0

    def test_no_whales(self, analyzer):
        trades = [
            {"side": "buy", "price": 100.0, "size": 1.0, "timestamp": "2026-01-01T00:00:00Z"},
        ]
        whales = analyzer.detect_whale_trades("BTC/USD", trades)
        assert len(whales) == 0

    def test_custom_threshold(self, analyzer):
        trades = [
            {"side": "sell", "price": 50.0, "size": 10.0, "timestamp": "2026-01-01T00:00:00Z"},
        ]
        whales = analyzer.detect_whale_trades("BTC/USD", trades, threshold=400.0)
        assert len(whales) == 1
        assert whales[0].notional == 500.0


class TestFundingSentiment:
    def test_positive_funding_bearish(self, analyzer):
        # Positive funding → longs pay shorts → bearish → negative sentiment
        score = analyzer.compute_funding_sentiment(0.001)
        assert score < 0.0

    def test_negative_funding_bullish(self, analyzer):
        # Negative funding → shorts pay longs → bullish → positive sentiment
        score = analyzer.compute_funding_sentiment(-0.001)
        assert score > 0.0

    def test_zero_funding(self, analyzer):
        score = analyzer.compute_funding_sentiment(0.0)
        assert score == 0.0

    def test_none_funding(self, analyzer):
        score = analyzer.compute_funding_sentiment(None)
        assert score == 0.0

    def test_bounded(self, analyzer):
        assert analyzer.compute_funding_sentiment(1.0) >= -1.0
        assert analyzer.compute_funding_sentiment(-1.0) <= 1.0


class TestWhaleSentiment:
    def test_buy_dominant(self, analyzer):
        whales = [
            WhaleTrade("BTC/USD", "buy", 60000, 2.0, 120000, "t"),
            WhaleTrade("BTC/USD", "sell", 60000, 0.5, 30000, "t"),
        ]
        score = analyzer.compute_whale_sentiment(whales)
        assert score > 0.0

    def test_sell_dominant(self, analyzer):
        whales = [
            WhaleTrade("BTC/USD", "sell", 60000, 3.0, 180000, "t"),
        ]
        score = analyzer.compute_whale_sentiment(whales)
        assert score == -1.0

    def test_empty(self, analyzer):
        assert analyzer.compute_whale_sentiment([]) == 0.0


class TestCompositeSnapshot:
    def test_full_data(self, analyzer):
        bids = [(60000.0, 5.0), (59990.0, 3.0)]
        asks = [(60010.0, 2.0), (60020.0, 1.0)]
        trades = [
            {"side": "buy", "price": 60000.0, "size": 2.0, "timestamp": "2026-01-01T00:00:00Z"},
            {"side": "sell", "price": 60000.0, "size": 1.0, "timestamp": "2026-01-01T00:00:01Z"},
        ]
        snapshot = analyzer.compute_snapshot(
            pair="BTC/USD",
            bids=bids,
            asks=asks,
            trades=trades,
            funding_rate=0.0001,
            timestamp="2026-01-01T00:00:00Z",
        )
        assert snapshot.pair == "BTC/USD"
        assert snapshot.order_book_imbalance is not None
        assert snapshot.trade_flow is not None
        assert -1.0 <= snapshot.composite_score <= 1.0
        assert snapshot.order_book_imbalance.imbalance_ratio > 0
        assert snapshot.trade_flow.flow_ratio > 0

    def test_partial_data_no_order_book(self, analyzer):
        trades = [
            {"side": "buy", "price": 100.0, "size": 10.0, "timestamp": "t"},
        ]
        snapshot = analyzer.compute_snapshot(
            pair="ETH/USD", trades=trades, timestamp="t"
        )
        assert snapshot.order_book_imbalance is None
        assert snapshot.trade_flow is not None
        assert snapshot.composite_score > 0.0

    def test_no_data(self, analyzer):
        snapshot = analyzer.compute_snapshot(pair="BTC/USD", timestamp="t")
        assert snapshot.composite_score == 0.0
        assert snapshot.order_book_imbalance is None
        assert snapshot.trade_flow is None
        assert len(snapshot.whale_trades) == 0

    def test_to_dict_roundtrip(self, analyzer):
        bids = [(100.0, 5.0)]
        asks = [(101.0, 5.0)]
        trades = [{"side": "buy", "price": 100.0, "size": 1.0, "timestamp": "t"}]
        snapshot = analyzer.compute_snapshot(
            pair="TEST/USD", bids=bids, asks=asks, trades=trades, timestamp="t"
        )
        d = snapshot.to_dict()
        assert d["pair"] == "TEST/USD"
        assert isinstance(d["composite_score"], float)
        assert isinstance(d["order_book_imbalance"], dict)
        assert isinstance(d["trade_flow"], dict)
        assert isinstance(d["whale_trades"], list)
