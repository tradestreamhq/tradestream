"""Tests for the MTF Signal Filter."""

from unittest.mock import MagicMock, patch

import pytest

from services.mtf_analysis.analyzer import (
    ConfluenceResult,
    MultiTimeframeAnalyzer,
    Signal,
)
from services.mtf_analysis.signal_filter import MTFSignalFilter


@pytest.fixture
def analyzer():
    return MagicMock(spec=MultiTimeframeAnalyzer)


@pytest.fixture
def filter_(analyzer):
    return MTFSignalFilter(analyzer, min_confluence=0.3, min_agreeing=2)


def _make_confluence(score, signal, agreeing):
    return ConfluenceResult(
        pair="BTC/USD",
        score=score,
        signal=signal,
        agreeing_timeframes=agreeing,
        total_timeframes=6,
    )


class TestShouldExecute:
    def test_allows_aligned_buy(self, filter_, analyzer):
        analyzer.get_confluence.return_value = _make_confluence(
            0.5, Signal.BULLISH, ["1h", "4h", "1d"]
        )
        result = filter_.should_execute("BTC/USD", "BUY")
        assert result["allowed"] is True

    def test_allows_aligned_sell(self, filter_, analyzer):
        analyzer.get_confluence.return_value = _make_confluence(
            -0.5, Signal.BEARISH, ["1h", "4h", "1d"]
        )
        result = filter_.should_execute("BTC/USD", "SELL")
        assert result["allowed"] is True

    def test_rejects_low_confluence(self, filter_, analyzer):
        analyzer.get_confluence.return_value = _make_confluence(
            0.1, Signal.NEUTRAL, []
        )
        result = filter_.should_execute("BTC/USD", "BUY")
        assert result["allowed"] is False
        assert "below threshold" in result["reason"]

    def test_rejects_conflicting_direction(self, filter_, analyzer):
        analyzer.get_confluence.return_value = _make_confluence(
            -0.5, Signal.BEARISH, ["1h", "4h", "1d"]
        )
        result = filter_.should_execute("BTC/USD", "BUY")
        assert result["allowed"] is False
        assert "conflicts" in result["reason"]

    def test_rejects_insufficient_agreeing(self, filter_, analyzer):
        analyzer.get_confluence.return_value = _make_confluence(
            0.4, Signal.BULLISH, ["1d"]
        )
        result = filter_.should_execute("BTC/USD", "BUY")
        assert result["allowed"] is False
        assert "agreeing timeframes" in result["reason"]

    def test_returns_confluence_details(self, filter_, analyzer):
        analyzer.get_confluence.return_value = _make_confluence(
            0.6, Signal.BULLISH, ["1h", "4h", "1d"]
        )
        result = filter_.should_execute("BTC/USD", "BUY")
        assert result["confluence_score"] == 0.6
        assert result["confluence_signal"] == "bullish"
        assert result["agreeing_timeframes"] == ["1h", "4h", "1d"]
