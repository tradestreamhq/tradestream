"""Tests for the stock screener engine."""

import pytest

from services.screener_api.screener import (
    BUILT_IN_PRESETS,
    FilterCriterion,
    FilterOperator,
    MarketSnapshot,
    ScanRequest,
    ScanResult,
    run_scan,
)


def _make_snapshot(**kwargs) -> MarketSnapshot:
    defaults = {
        "symbol": "AAPL",
        "price": 150.0,
        "volume": 1_000_000.0,
        "rsi": 55.0,
        "sma_20": 148.0,
        "sma_50": 145.0,
        "sma_200": 140.0,
        "ema_12": 149.0,
        "ema_26": 147.0,
        "sector": "Technology",
        "change_pct": 1.5,
    }
    defaults.update(kwargs)
    return MarketSnapshot(**defaults)


class TestFilterOperators:
    def test_gt(self):
        snap = _make_snapshot(price=100.0)
        criterion = FilterCriterion("price", FilterOperator.GT, 50.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    def test_gt_no_match(self):
        snap = _make_snapshot(price=30.0)
        criterion = FilterCriterion("price", FilterOperator.GT, 50.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 0

    def test_gte(self):
        snap = _make_snapshot(price=50.0)
        criterion = FilterCriterion("price", FilterOperator.GTE, 50.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 1

    def test_lt(self):
        snap = _make_snapshot(price=30.0)
        criterion = FilterCriterion("price", FilterOperator.LT, 50.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 1

    def test_lte(self):
        snap = _make_snapshot(price=50.0)
        criterion = FilterCriterion("price", FilterOperator.LTE, 50.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 1

    def test_eq(self):
        snap = _make_snapshot(rsi=70.0)
        criterion = FilterCriterion("rsi", FilterOperator.EQ, 70.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 1

    def test_between(self):
        snap = _make_snapshot(rsi=45.0)
        criterion = FilterCriterion("rsi", FilterOperator.BETWEEN, 30.0, value_max=50.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 1

    def test_between_no_max(self):
        snap = _make_snapshot(rsi=45.0)
        criterion = FilterCriterion("rsi", FilterOperator.BETWEEN, 30.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 0

    def test_between_out_of_range(self):
        snap = _make_snapshot(rsi=60.0)
        criterion = FilterCriterion("rsi", FilterOperator.BETWEEN, 30.0, value_max=50.0)
        request = ScanRequest(filters=[criterion])
        results = run_scan([snap], request)
        assert len(results) == 0


class TestScanLogic:
    def test_multiple_filters_all_match(self):
        snap = _make_snapshot(price=100.0, volume=2_000_000.0, rsi=25.0)
        request = ScanRequest(
            filters=[
                FilterCriterion("price", FilterOperator.GTE, 50.0),
                FilterCriterion("volume", FilterOperator.GTE, 1_000_000.0),
                FilterCriterion("rsi", FilterOperator.LTE, 30.0),
            ]
        )
        results = run_scan([snap], request)
        assert len(results) == 1
        assert results[0].score == 1.0
        assert len(results[0].matched_criteria) == 3

    def test_partial_match(self):
        snap = _make_snapshot(price=100.0, rsi=55.0)
        request = ScanRequest(
            filters=[
                FilterCriterion("price", FilterOperator.GTE, 50.0),
                FilterCriterion("rsi", FilterOperator.LTE, 30.0),
            ]
        )
        results = run_scan([snap], request)
        assert len(results) == 1
        assert results[0].score == 0.5

    def test_no_match(self):
        snap = _make_snapshot(price=10.0, rsi=80.0)
        request = ScanRequest(
            filters=[
                FilterCriterion("price", FilterOperator.GTE, 50.0),
                FilterCriterion("rsi", FilterOperator.LTE, 30.0),
            ]
        )
        results = run_scan([snap], request)
        assert len(results) == 0

    def test_sector_filter(self):
        snaps = [
            _make_snapshot(symbol="AAPL", sector="Technology"),
            _make_snapshot(symbol="JPM", sector="Finance"),
        ]
        request = ScanRequest(
            filters=[FilterCriterion("price", FilterOperator.GT, 0)],
            sector="Technology",
        )
        results = run_scan(snaps, request)
        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    def test_sorted_by_score(self):
        snaps = [
            _make_snapshot(symbol="LOW", price=10.0, rsi=55.0),
            _make_snapshot(symbol="HIGH", price=200.0, rsi=20.0),
        ]
        request = ScanRequest(
            filters=[
                FilterCriterion("price", FilterOperator.GTE, 100.0),
                FilterCriterion("rsi", FilterOperator.LTE, 30.0),
            ]
        )
        results = run_scan(snaps, request)
        assert len(results) == 1
        assert results[0].symbol == "HIGH"
        assert results[0].score == 1.0

    def test_limit(self):
        snaps = [_make_snapshot(symbol=f"SYM{i}") for i in range(10)]
        request = ScanRequest(
            filters=[FilterCriterion("price", FilterOperator.GT, 0)],
            limit=3,
        )
        results = run_scan(snaps, request)
        assert len(results) == 3

    def test_unknown_field_ignored(self):
        snap = _make_snapshot()
        request = ScanRequest(
            filters=[FilterCriterion("nonexistent", FilterOperator.GT, 0)]
        )
        results = run_scan([snap], request)
        assert len(results) == 0

    def test_none_value_field(self):
        snap = _make_snapshot(rsi=None)
        request = ScanRequest(
            filters=[FilterCriterion("rsi", FilterOperator.LTE, 30)]
        )
        results = run_scan([snap], request)
        assert len(results) == 0

    def test_empty_snapshots(self):
        request = ScanRequest(
            filters=[FilterCriterion("price", FilterOperator.GT, 0)]
        )
        results = run_scan([], request)
        assert len(results) == 0

    def test_empty_filters(self):
        snap = _make_snapshot()
        request = ScanRequest(filters=[])
        results = run_scan([snap], request)
        assert len(results) == 0

    def test_scan_result_fields(self):
        snap = _make_snapshot(symbol="TSLA", price=250.0, volume=5_000_000.0)
        request = ScanRequest(
            filters=[FilterCriterion("price", FilterOperator.GT, 100.0)]
        )
        results = run_scan([snap], request)
        assert len(results) == 1
        r = results[0]
        assert r.symbol == "TSLA"
        assert r.current_price == 250.0
        assert r.volume == 5_000_000.0
        assert "price gt 100.0" in r.matched_criteria


class TestMovingAverageFilters:
    def test_sma_20_filter(self):
        snap = _make_snapshot(sma_20=155.0)
        request = ScanRequest(
            filters=[FilterCriterion("sma_20", FilterOperator.GTE, 150.0)]
        )
        results = run_scan([snap], request)
        assert len(results) == 1

    def test_sma_50_filter(self):
        snap = _make_snapshot(sma_50=145.0)
        request = ScanRequest(
            filters=[FilterCriterion("sma_50", FilterOperator.GT, 140.0)]
        )
        results = run_scan([snap], request)
        assert len(results) == 1

    def test_sma_200_filter(self):
        snap = _make_snapshot(sma_200=130.0)
        request = ScanRequest(
            filters=[FilterCriterion("sma_200", FilterOperator.LT, 140.0)]
        )
        results = run_scan([snap], request)
        assert len(results) == 1

    def test_ema_filters(self):
        snap = _make_snapshot(ema_12=150.0, ema_26=148.0)
        request = ScanRequest(
            filters=[
                FilterCriterion("ema_12", FilterOperator.GT, 149.0),
                FilterCriterion("ema_26", FilterOperator.GT, 147.0),
            ]
        )
        results = run_scan([snap], request)
        assert len(results) == 1
        assert results[0].score == 1.0


class TestBuiltInPresets:
    def test_presets_exist(self):
        assert "high_volume_breakout" in BUILT_IN_PRESETS
        assert "oversold_bounce" in BUILT_IN_PRESETS
        assert "golden_cross" in BUILT_IN_PRESETS
        assert "overbought" in BUILT_IN_PRESETS
        assert "penny_stocks" in BUILT_IN_PRESETS

    def test_preset_has_required_fields(self):
        for key, preset in BUILT_IN_PRESETS.items():
            assert "name" in preset
            assert "description" in preset
            assert "filters" in preset
            assert len(preset["filters"]) > 0
