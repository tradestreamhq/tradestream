"""Tests for the janitor report generator."""

from datetime import date

import pytest

from services.janitor_agent.db_maintenance import MaintenanceResult
from services.janitor_agent.health_checker import ServiceHealth
from services.janitor_agent.report import JanitorReport
from services.janitor_agent.retirement_criteria import RetirementDecision
from services.janitor_agent.state_repair import RepairResult


class TestJanitorReport:
    def _make_report(self) -> JanitorReport:
        return JanitorReport(
            report_date=date(2026, 3, 19),
            evaluated_count=47,
            retired_implementations=[
                RetirementDecision(
                    should_retire=True,
                    reason="Retired: Sharpe=0.23, Accuracy=41%",
                    impl_id="impl-001-abcdef",
                    spec_id="spec-001",
                    final_sharpe=0.23,
                    final_accuracy=0.41,
                    age_days=245,
                    signal_count=234,
                ),
            ],
            retired_specs=[
                RetirementDecision(
                    should_retire=True,
                    reason="All 3 implementations retired",
                    spec_id="spec-002-abcdef",
                    decision_type="spec",
                ),
            ],
            protected_canonical=[
                RetirementDecision(
                    should_retire=False,
                    reason="CANONICAL spec protected from retirement",
                    impl_id="impl-003-abcdef",
                ),
            ],
            maintenance_results=[
                MaintenanceResult(
                    operation="vacuum_analyze:strategy_implementations",
                    success=True,
                    details="VACUUM ANALYZE completed",
                    rows_affected=0,
                ),
            ],
            health_results=[
                ServiceHealth("market-data-api", "url", healthy=True, response_time_ms=15),
                ServiceHealth("strategy-api", "url", healthy=False, status_code=503, response_time_ms=100),
            ],
            repair_results=[
                RepairResult(
                    check_name="orphaned_implementations",
                    inconsistencies_found=2,
                    repaired=2,
                    details="Found 2 orphaned, retired 2",
                ),
            ],
            duration_seconds=45.3,
        )

    def test_retired_count(self):
        report = self._make_report()
        assert report.retired_count == 1

    def test_protected_count(self):
        report = self._make_report()
        assert report.protected_count == 1

    def test_has_warnings_with_unhealthy(self):
        report = self._make_report()
        assert report.has_warnings is True

    def test_has_warnings_all_healthy(self):
        report = JanitorReport(
            report_date=date(2026, 3, 19),
            health_results=[
                ServiceHealth("svc1", "url", healthy=True, response_time_ms=10),
            ],
        )
        assert report.has_warnings is False

    def test_to_markdown_contains_sections(self):
        report = self._make_report()
        md = report.to_markdown()
        assert "# Janitor Agent Daily Report" in md
        assert "2026-03-19" in md
        assert "## Summary" in md
        assert "Implementations evaluated: 47" in md
        assert "Implementations retired: 1" in md
        assert "## Retired Implementations" in md
        assert "impl-001" in md
        assert "## Retired Specs" in md
        assert "spec-002" in md
        assert "## Protected (CANONICAL)" in md
        assert "## Service Health" in md
        assert "strategy-api" in md
        assert "## Database Maintenance" in md
        assert "## State Repairs" in md

    def test_to_dict(self):
        report = self._make_report()
        d = report.to_dict()
        assert d["report_date"] == "2026-03-19"
        assert d["evaluated_count"] == 47
        assert d["retired_implementations"] == 1
        assert d["retired_specs"] == 1
        assert d["protected_count"] == 1
        assert "# Janitor Agent Daily Report" in d["report_markdown"]

    def test_empty_report(self):
        report = JanitorReport(report_date=date(2026, 3, 19))
        md = report.to_markdown()
        assert "Implementations evaluated: 0" in md
        assert "Implementations retired: 0" in md
        # Should not contain retired sections
        assert "## Retired Implementations" not in md
