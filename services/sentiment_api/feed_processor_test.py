"""Tests for the feed processor and sentiment store."""

from datetime import datetime

from services.sentiment_api.feed_processor import SentimentStore
from services.sentiment_api.models import SentimentRecord


class TestSentimentStore:
    def test_ingest_text(self):
        store = SentimentStore()
        record = store.ingest_text("bullish rally", "BTC/USD", "twitter")
        assert record.symbol == "BTC/USD"
        assert record.score > 0

    def test_get_records_empty(self):
        store = SentimentStore()
        assert store.get_records("BTC/USD") == []

    def test_get_records_filtered_by_time(self):
        store = SentimentStore()
        store.ingest_text("bullish", "BTC/USD", "t", datetime(2026, 3, 1, 10, 0))
        store.ingest_text("bearish", "BTC/USD", "t", datetime(2026, 3, 1, 12, 0))
        store.ingest_text("neutral", "BTC/USD", "t", datetime(2026, 3, 1, 14, 0))

        records = store.get_records(
            "BTC/USD",
            from_time=datetime(2026, 3, 1, 11, 0),
            to_time=datetime(2026, 3, 1, 13, 0),
        )
        assert len(records) == 1

    def test_get_aggregated(self):
        store = SentimentStore()
        store.ingest_text("bullish rally surge", "BTC/USD", "twitter",
                          datetime(2026, 3, 1, 10, 0))
        store.ingest_text("bullish gain profit", "BTC/USD", "news",
                          datetime(2026, 3, 1, 12, 0))

        agg = store.get_aggregated("BTC/USD")
        assert agg is not None
        assert agg.symbol == "BTC/USD"
        assert agg.record_count == 2
        assert agg.average_score > 0
        assert "twitter" in agg.sources
        assert "news" in agg.sources

    def test_get_aggregated_no_data(self):
        store = SentimentStore()
        assert store.get_aggregated("BTC/USD") is None

    def test_velocity_calculation(self):
        store = SentimentStore()
        # Older records: negative
        store.ingest_text("bearish crash dump sell", "BTC/USD", "t",
                          datetime(2026, 3, 1, 10, 0))
        store.ingest_text("bearish loss decline", "BTC/USD", "t",
                          datetime(2026, 3, 1, 11, 0))
        # Newer records: positive
        store.ingest_text("bullish rally surge gain", "BTC/USD", "t",
                          datetime(2026, 3, 1, 12, 0))
        store.ingest_text("bullish profit growth", "BTC/USD", "t",
                          datetime(2026, 3, 1, 13, 0))

        agg = store.get_aggregated("BTC/USD")
        assert agg is not None
        # Sentiment improved over time, so velocity should be positive
        assert agg.velocity > 0

    def test_multiple_symbols(self):
        store = SentimentStore()
        store.ingest_text("bullish", "BTC/USD", "t")
        store.ingest_text("bearish", "ETH/USD", "t")

        btc = store.get_aggregated("BTC/USD")
        eth = store.get_aggregated("ETH/USD")
        assert btc.average_score > 0
        assert eth.average_score < 0
