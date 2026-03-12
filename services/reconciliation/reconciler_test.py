"""Tests for position reconciliation logic."""

from services.reconciliation.models import (
    Discrepancy,
    DiscrepancyType,
    PositionSnapshot,
    ReconciliationReport,
)
from services.reconciliation.reconciler import reconcile


class TestReconcile:
    def test_matched_positions(self):
        internal = [PositionSnapshot("BTC/USD", 1.0, 50000.0)]
        exchange = [PositionSnapshot("BTC/USD", 1.0, 50000.0)]
        report = reconcile(internal, exchange)
        assert report.status == "MATCHED"
        assert report.total_positions_checked == 1
        assert len(report.discrepancies) == 0

    def test_quantity_mismatch(self):
        internal = [PositionSnapshot("BTC/USD", 1.0, 50000.0)]
        exchange = [PositionSnapshot("BTC/USD", 0.9, 50000.0)]
        report = reconcile(internal, exchange)
        assert report.status == "DISCREPANCIES_FOUND"
        assert len(report.discrepancies) == 1
        d = report.discrepancies[0]
        assert d.type == DiscrepancyType.QUANTITY_MISMATCH
        assert d.internal_quantity == 1.0
        assert d.exchange_quantity == 0.9
        assert abs(d.difference - 0.1) < 1e-9

    def test_phantom_position(self):
        internal = [PositionSnapshot("BTC/USD", 1.0, 50000.0)]
        exchange = []
        report = reconcile(internal, exchange)
        assert report.status == "DISCREPANCIES_FOUND"
        assert len(report.discrepancies) == 1
        d = report.discrepancies[0]
        assert d.type == DiscrepancyType.PHANTOM_POSITION
        assert d.exchange_quantity is None

    def test_missing_internal(self):
        internal = []
        exchange = [PositionSnapshot("ETH/USD", 5.0, 3000.0)]
        report = reconcile(internal, exchange)
        assert report.status == "DISCREPANCIES_FOUND"
        assert len(report.discrepancies) == 1
        d = report.discrepancies[0]
        assert d.type == DiscrepancyType.MISSING_INTERNAL
        assert d.internal_quantity is None

    def test_auto_reconcile_within_threshold(self):
        internal = [PositionSnapshot("BTC/USD", 1.0, 50000.0)]
        exchange = [PositionSnapshot("BTC/USD", 0.99, 50000.0)]
        report = reconcile(internal, exchange, auto_reconcile_threshold=0.05)
        assert len(report.discrepancies) == 1
        d = report.discrepancies[0]
        assert d.auto_reconciled is True
        assert report.auto_reconciled_count == 1

    def test_auto_reconcile_exceeds_threshold(self):
        internal = [PositionSnapshot("BTC/USD", 1.0, 50000.0)]
        exchange = [PositionSnapshot("BTC/USD", 0.5, 50000.0)]
        report = reconcile(internal, exchange, auto_reconcile_threshold=0.05)
        assert len(report.discrepancies) == 1
        d = report.discrepancies[0]
        assert d.auto_reconciled is False
        assert report.auto_reconciled_count == 0

    def test_empty_positions(self):
        report = reconcile([], [])
        assert report.status == "MATCHED"
        assert report.total_positions_checked == 0

    def test_multiple_discrepancies(self):
        internal = [
            PositionSnapshot("BTC/USD", 1.0, 50000.0),
            PositionSnapshot("PHANTOM/USD", 2.0, 100.0),
        ]
        exchange = [
            PositionSnapshot("BTC/USD", 0.8, 50000.0),
            PositionSnapshot("MISSING/USD", 3.0, 200.0),
        ]
        report = reconcile(internal, exchange)
        assert report.status == "DISCREPANCIES_FOUND"
        assert report.total_positions_checked == 3
        assert len(report.discrepancies) == 3
        types = {d.type for d in report.discrepancies}
        assert DiscrepancyType.QUANTITY_MISMATCH in types
        assert DiscrepancyType.PHANTOM_POSITION in types
        assert DiscrepancyType.MISSING_INTERNAL in types

    def test_report_to_dict(self):
        internal = [PositionSnapshot("BTC/USD", 1.0, 50000.0)]
        exchange = [PositionSnapshot("BTC/USD", 0.9, 50000.0)]
        report = reconcile(internal, exchange)
        d = report.to_dict()
        assert "run_id" in d
        assert "timestamp" in d
        assert d["status"] == "DISCREPANCIES_FOUND"
        assert len(d["discrepancies"]) == 1
        assert d["discrepancies"][0]["type"] == "QUANTITY_MISMATCH"
