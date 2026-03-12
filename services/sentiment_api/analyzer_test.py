"""Tests for the sentiment analyzer."""

from datetime import datetime

from services.sentiment_api.analyzer import analyze_text


class TestAnalyzeText:
    def test_positive_text(self):
        record = analyze_text(
            "BTC is surging with bullish momentum, huge rally incoming",
            symbol="BTC/USD",
            source="twitter",
        )
        assert record.score > 0
        assert record.confidence > 0

    def test_negative_text(self):
        record = analyze_text(
            "market crash imminent, bearish dump and panic selling",
            symbol="ETH/USD",
            source="news",
        )
        assert record.score < 0
        assert record.confidence > 0

    def test_neutral_text(self):
        record = analyze_text(
            "the quick brown fox jumped over the lazy dog",
            symbol="BTC/USD",
            source="test",
        )
        assert record.score == 0.0
        assert record.confidence == 0.0

    def test_empty_text(self):
        record = analyze_text("", symbol="BTC/USD", source="test")
        assert record.score == 0.0
        assert record.confidence == 0.0

    def test_mixed_sentiment(self):
        record = analyze_text(
            "despite the rally and gains, there is fear of a crash",
            symbol="BTC/USD",
            source="news",
        )
        # Mixed: rally, gains (2 pos) vs fear, crash (2 neg) -> near 0
        assert -0.5 <= record.score <= 0.5

    def test_snippet_truncation(self):
        long_text = "bullish " * 200
        record = analyze_text(long_text, symbol="BTC/USD", source="test")
        assert len(record.raw_text_snippet) <= 280

    def test_custom_timestamp(self):
        ts = datetime(2026, 3, 1, 12, 0, 0)
        record = analyze_text(
            "bullish", symbol="BTC/USD", source="test", timestamp=ts
        )
        assert record.timestamp == ts

    def test_score_bounds(self):
        # All positive words
        record = analyze_text(
            "bullish surge rally gain profit",
            symbol="BTC/USD",
            source="test",
        )
        assert record.score == 1.0

        # All negative words
        record = analyze_text(
            "bearish crash dump sell loss",
            symbol="BTC/USD",
            source="test",
        )
        assert record.score == -1.0
