"""Tests for the market sentiment aggregator."""

import time

import pytest

from services.market_sentiment.aggregator import (
    AggregatedSentiment,
    SentimentDataFetcher,
    SentimentDataPoint,
    SentimentSourceType,
    aggregate_sentiment,
    normalise_fear_greed,
    normalise_funding_rate,
    normalise_long_short_ratio,
    normalise_news_score,
    normalise_social_score,
    sentiment_label,
)


# ---------------------------------------------------------------------------
# Normalisation tests
# ---------------------------------------------------------------------------


class TestNormaliseFearGreed:
    def test_extreme_fear(self):
        assert normalise_fear_greed(0) == -1.0

    def test_extreme_greed(self):
        assert normalise_fear_greed(100) == 1.0

    def test_neutral(self):
        assert normalise_fear_greed(50) == 0.0

    def test_mid_fear(self):
        result = normalise_fear_greed(25)
        assert result == pytest.approx(-0.5)

    def test_mid_greed(self):
        result = normalise_fear_greed(75)
        assert result == pytest.approx(0.5)


class TestNormaliseFundingRate:
    def test_positive_rate(self):
        # 0.01 -> +1.0
        assert normalise_funding_rate(0.01) == 1.0

    def test_negative_rate(self):
        assert normalise_funding_rate(-0.01) == -1.0

    def test_zero_rate(self):
        assert normalise_funding_rate(0.0) == 0.0

    def test_small_positive(self):
        result = normalise_funding_rate(0.005)
        assert result == pytest.approx(0.5)

    def test_clamps_extreme(self):
        assert normalise_funding_rate(0.05) == 1.0


class TestNormaliseLongShortRatio:
    def test_balanced(self):
        assert normalise_long_short_ratio(1.0) == 0.0

    def test_more_longs(self):
        result = normalise_long_short_ratio(1.5)
        assert result == pytest.approx(0.5)

    def test_more_shorts(self):
        result = normalise_long_short_ratio(0.5)
        assert result == pytest.approx(-0.5)

    def test_extreme_longs(self):
        assert normalise_long_short_ratio(3.0) == 1.0


class TestNormaliseSocialScore:
    def test_above_average(self):
        result = normalise_social_score(200, 100)
        assert result == 1.0

    def test_below_average(self):
        result = normalise_social_score(50, 100)
        assert result == pytest.approx(-0.5)

    def test_at_average(self):
        assert normalise_social_score(100, 100) == 0.0

    def test_zero_average(self):
        assert normalise_social_score(100, 0) == 0.0


class TestNormaliseNewsScore:
    def test_passthrough(self):
        assert normalise_news_score(0.5) == 0.5

    def test_clamp_high(self):
        assert normalise_news_score(1.5) == 1.0

    def test_clamp_low(self):
        assert normalise_news_score(-2.0) == -1.0


class TestSentimentLabel:
    def test_extreme_fear(self):
        assert sentiment_label(-0.8) == "extreme_fear"

    def test_fear(self):
        assert sentiment_label(-0.4) == "fear"

    def test_neutral(self):
        assert sentiment_label(0.0) == "neutral"

    def test_greed(self):
        assert sentiment_label(0.4) == "greed"

    def test_extreme_greed(self):
        assert sentiment_label(0.8) == "extreme_greed"


# ---------------------------------------------------------------------------
# SentimentDataFetcher tests
# ---------------------------------------------------------------------------


class TestSentimentDataFetcher:
    def setup_method(self):
        self.fetcher = SentimentDataFetcher()

    def test_fetch_funding_rate(self):
        dp = self.fetcher.fetch_funding_rate("BTC-USD", 0.005)
        assert dp.source == SentimentSourceType.FUNDING_RATE
        assert dp.raw_value == 0.005
        assert dp.normalised_score == pytest.approx(0.5)
        assert dp.metadata["symbol"] == "BTC-USD"

    def test_fetch_long_short_ratio(self):
        dp = self.fetcher.fetch_long_short_ratio("ETH-USD", 1.3)
        assert dp.source == SentimentSourceType.LONG_SHORT_RATIO
        assert dp.normalised_score == pytest.approx(0.3)

    def test_fetch_social_sentiment(self):
        dp = self.fetcher.fetch_social_sentiment(150, 100)
        assert dp.source == SentimentSourceType.SOCIAL_MEDIA
        assert dp.normalised_score == pytest.approx(0.5)

    def test_fetch_news_sentiment(self):
        dp = self.fetcher.fetch_news_sentiment(-0.3, headline_count=10)
        assert dp.source == SentimentSourceType.NEWS
        assert dp.normalised_score == pytest.approx(-0.3)
        assert dp.metadata["headline_count"] == 10


# ---------------------------------------------------------------------------
# Aggregation tests
# ---------------------------------------------------------------------------


class TestAggregateSentiment:
    def test_empty_data_points(self):
        result = aggregate_sentiment("BTC-USD", [])
        assert result.composite_score == 0.0
        assert result.label == "neutral"
        assert result.source_scores == []

    def test_single_source(self):
        dp = SentimentDataPoint(
            source=SentimentSourceType.FEAR_GREED,
            raw_value=20,
            normalised_score=-0.6,
            timestamp=time.time(),
        )
        result = aggregate_sentiment("BTC-USD", [dp])
        assert result.composite_score == -0.6
        assert result.label == "extreme_fear"

    def test_multiple_sources(self):
        now = time.time()
        dps = [
            SentimentDataPoint(
                source=SentimentSourceType.FEAR_GREED,
                raw_value=20,
                normalised_score=-0.6,
                timestamp=now,
            ),
            SentimentDataPoint(
                source=SentimentSourceType.NEWS,
                raw_value=-0.4,
                normalised_score=-0.4,
                timestamp=now,
            ),
            SentimentDataPoint(
                source=SentimentSourceType.SOCIAL_MEDIA,
                raw_value=80,
                normalised_score=-0.2,
                timestamp=now,
            ),
        ]
        result = aggregate_sentiment("BTC-USD", dps)
        # Weighted average: (-0.6*0.30 + -0.4*0.25 + -0.2*0.20) / (0.30+0.25+0.20)
        expected = (-0.18 + -0.10 + -0.04) / 0.75
        assert result.composite_score == pytest.approx(expected, abs=0.01)
        assert result.symbol == "BTC-USD"
        assert len(result.source_scores) == 3

    def test_custom_weights(self):
        dp = SentimentDataPoint(
            source=SentimentSourceType.FEAR_GREED,
            raw_value=80,
            normalised_score=0.6,
            timestamp=time.time(),
        )
        custom_weights = {SentimentSourceType.FEAR_GREED: 1.0}
        result = aggregate_sentiment("ETH-USD", [dp], weights=custom_weights)
        assert result.composite_score == 0.6

    def test_composite_clamped(self):
        dps = [
            SentimentDataPoint(
                source=SentimentSourceType.FEAR_GREED,
                raw_value=0,
                normalised_score=-1.0,
                timestamp=time.time(),
            ),
            SentimentDataPoint(
                source=SentimentSourceType.NEWS,
                raw_value=-1.0,
                normalised_score=-1.0,
                timestamp=time.time(),
            ),
        ]
        result = aggregate_sentiment("BTC-USD", dps)
        assert result.composite_score >= -1.0
        assert result.composite_score <= 1.0
