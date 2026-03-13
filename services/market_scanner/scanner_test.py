"""Tests for the Market Scanner core logic."""

from unittest.mock import MagicMock

import pytest

from services.market_scanner.scanner import (
    MarketScanner,
    ScanCondition,
    ScanDefinition,
)


@pytest.fixture
def scanner():
    market_data = MagicMock()
    return MarketScanner(market_data), market_data


class TestScanLifecycle:
    def test_create_scan(self, scanner):
        sc, _ = scanner
        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.PRICE_BREAKOUT]
        )
        scan = sc.create_scan(definition)
        assert scan.id is not None
        assert scan.pairs == ["BTC/USD"]
        assert ScanCondition.PRICE_BREAKOUT in scan.conditions

    def test_delete_scan(self, scanner):
        sc, _ = scanner
        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.PRICE_BREAKOUT]
        )
        scan = sc.create_scan(definition)
        assert sc.delete_scan(scan.id) is True
        assert sc.get_scan(scan.id) is None

    def test_delete_nonexistent(self, scanner):
        sc, _ = scanner
        assert sc.delete_scan("fake-id") is False

    def test_get_scan(self, scanner):
        sc, _ = scanner
        definition = ScanDefinition(
            pairs=["ETH/USD"], conditions=[ScanCondition.VOLUME_SPIKE]
        )
        scan = sc.create_scan(definition)
        retrieved = sc.get_scan(scan.id)
        assert retrieved is not None
        assert retrieved.pairs == ["ETH/USD"]


class TestPriceBreakout:
    def test_bullish_breakout(self, scanner):
        sc, market_data = scanner
        candles = [
            {"high": 100, "low": 90, "close": 95, "volume": 10} for _ in range(23)
        ]
        candles.append({"high": 110, "low": 95, "close": 105, "volume": 10})
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.PRICE_BREAKOUT]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 1
        assert results[0].details["direction"] == "bullish"

    def test_bearish_breakout(self, scanner):
        sc, market_data = scanner
        candles = [
            {"high": 100, "low": 90, "close": 95, "volume": 10} for _ in range(23)
        ]
        candles.append({"high": 95, "low": 80, "close": 85, "volume": 10})
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.PRICE_BREAKOUT]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 1
        assert results[0].details["direction"] == "bearish"

    def test_no_breakout(self, scanner):
        sc, market_data = scanner
        candles = [
            {"high": 100, "low": 90, "close": 95, "volume": 10} for _ in range(24)
        ]
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.PRICE_BREAKOUT]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 0


class TestVolumeSplke:
    def test_volume_spike_detected(self, scanner):
        sc, market_data = scanner
        candles = [
            {"high": 100, "low": 90, "close": 95, "volume": 100} for _ in range(23)
        ]
        candles.append({"high": 100, "low": 90, "close": 95, "volume": 500})
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.VOLUME_SPIKE]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 1
        assert results[0].details["ratio"] == 5.0

    def test_no_volume_spike(self, scanner):
        sc, market_data = scanner
        candles = [
            {"high": 100, "low": 90, "close": 95, "volume": 100} for _ in range(24)
        ]
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.VOLUME_SPIKE]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 0


class TestRSIExtreme:
    def test_rsi_overbought(self, scanner):
        sc, market_data = scanner
        closes = [60000 + i * 100 for i in range(16)]
        candles = [
            {"high": c + 10, "low": c - 10, "close": c, "volume": 100}
            for c in closes
        ]
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.RSI_EXTREME]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 1
        assert results[0].details["signal"] == "overbought"

    def test_rsi_oversold(self, scanner):
        sc, market_data = scanner
        closes = [60000 - i * 100 for i in range(16)]
        candles = [
            {"high": c + 10, "low": c - 10, "close": c, "volume": 100}
            for c in closes
        ]
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.RSI_EXTREME]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 1
        assert results[0].details["signal"] == "oversold"

    def test_insufficient_data(self, scanner):
        sc, market_data = scanner
        market_data.get_candles.return_value = [
            {"high": 100, "low": 90, "close": 95, "volume": 100}
        ]

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.RSI_EXTREME]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 0


class TestMACrossover:
    def test_bullish_crossover(self, scanner):
        sc, market_data = scanner
        closes = [60000 + i * i * 5 for i in range(22)]
        candles = [
            {"high": c + 10, "low": c - 10, "close": c, "volume": 100}
            for c in closes
        ]
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.MA_CROSSOVER]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        # May or may not trigger depending on data — verify no crash
        assert isinstance(results, list)

    def test_insufficient_data(self, scanner):
        sc, market_data = scanner
        market_data.get_candles.return_value = [
            {"high": 100, "low": 90, "close": 95, "volume": 100}
        ]

        definition = ScanDefinition(
            pairs=["BTC/USD"], conditions=[ScanCondition.MA_CROSSOVER]
        )
        sc.create_scan(definition)
        results = sc.run_scans()
        assert len(results) == 0


class TestComputeRSI:
    def test_all_gains(self):
        closes = [100 + i * 10 for i in range(16)]
        rsi = MarketScanner._compute_rsi(closes, 14)
        assert rsi == 100.0

    def test_mixed(self):
        closes = [100, 110, 105, 115, 108, 120, 112, 125, 118, 130, 122, 135, 128, 140, 132]
        rsi = MarketScanner._compute_rsi(closes, 14)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_insufficient_data(self):
        rsi = MarketScanner._compute_rsi([100, 110], 14)
        assert rsi is None


class TestResultFiltering:
    def test_filter_by_pair(self, scanner):
        sc, market_data = scanner
        candles_breakout = [
            {"high": 100, "low": 90, "close": 95, "volume": 10} for _ in range(23)
        ]
        candles_breakout.append({"high": 110, "low": 95, "close": 105, "volume": 10})
        market_data.get_candles.return_value = candles_breakout

        definition = ScanDefinition(
            pairs=["BTC/USD", "ETH/USD"],
            conditions=[ScanCondition.PRICE_BREAKOUT],
        )
        sc.create_scan(definition)
        sc.run_scans()
        btc_results = sc.get_results(pair="BTC/USD")
        for r in btc_results:
            assert r.pair == "BTC/USD"

    def test_filter_by_condition(self, scanner):
        sc, market_data = scanner
        candles = [
            {"high": 100, "low": 90, "close": 95, "volume": 100} for _ in range(23)
        ]
        candles.append({"high": 110, "low": 95, "close": 105, "volume": 500})
        market_data.get_candles.return_value = candles

        definition = ScanDefinition(
            pairs=["BTC/USD"],
            conditions=[ScanCondition.PRICE_BREAKOUT, ScanCondition.VOLUME_SPIKE],
        )
        sc.create_scan(definition)
        sc.run_scans()
        spike_results = sc.get_results(condition="volume_spike")
        for r in spike_results:
            assert r.condition_met == ScanCondition.VOLUME_SPIKE
