"""Report generation for Janitor Agent runs.

Produces markdown reports with retirement summaries, health status,
maintenance results, and state repair details.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from services.janitor_agent.db_maintenance import MaintenanceResult
from services.janitor_agent.health_checker import ServiceHealth
from services.janitor_agent.retirement_criteria import RetirementDecision
from services.janitor_agent.state_repair import RepairResult


@dataclass
class JanitorReport:
    """Complete report for a janitor agent run."""

    report_date: date
    # Retirement summary
    evaluated_count: int = 0
    retired_implementations: list[RetirementDecision] = field(default_factory=list)
    retired_specs: list[RetirementDecision] = field(default_factory=list)
    protected_canonical: list[RetirementDecision] = field(default_factory=list)
    skipped_batch_limit: list[RetirementDecision] = field(default_factory=list)
    regime_deferred: list[RetirementDecision] = field(default_factory=list)
    # Maintenance results
    maintenance_results: list[MaintenanceResult] = field(default_factory=list)
    # Health check results
    health_results: list[ServiceHealth] = field(default_factory=list)
    # State repair results
    repair_results: list[RepairResult] = field(default_factory=list)
    # Timing
    duration_seconds: float = 0.0

    @property
    def retired_count(self) -> int:
        return len(self.retired_implementations)

    @property
    def protected_count(self) -> int:
        return len(self.protected_canonical)

    @property
    def has_warnings(self) -> bool:
        unhealthy = [h for h in self.health_results if not h.healthy]
        failed_repairs = [r for r in self.repair_results if not r.success]
        return len(unhealthy) > 0 or len(failed_repairs) > 0

    def to_markdown(self) -> str:
        """Generate full markdown report."""
        lines = []
        lines.append(f"# Janitor Agent Daily Report")
        lines.append(f"Date: {self.report_date}")
        lines.append(f"Duration: {self.duration_seconds:.1f}s")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append(f"- Implementations evaluated: {self.evaluated_count}")
        lines.append(f"- Implementations retired: {self.retired_count}")
        lines.append(f"- Specs retired: {len(self.retired_specs)}")
        lines.append(f"- CANONICAL specs protected: {self.protected_count}")
        lines.append(f"- Batch-limit skipped: {len(self.skipped_batch_limit)}")
        lines.append(f"- Regime-deferred: {len(self.regime_deferred)}")
        lines.append("")

        # Retired implementations
        if self.retired_implementations:
            lines.append("## Retired Implementations")
            lines.append("")
            lines.append("| Impl ID | Sharpe | Accuracy | Signals | Age | Reason |")
            lines.append("|---------|--------|----------|---------|-----|--------|")
            for d in self.retired_implementations:
                sharpe = f"{d.final_sharpe:.2f}" if d.final_sharpe is not None else "N/A"
                acc = f"{d.final_accuracy:.0%}" if d.final_accuracy is not None else "N/A"
                signals = str(d.signal_count) if d.signal_count is not None else "N/A"
                age = f"{d.age_days}d" if d.age_days is not None else "N/A"
                lines.append(
                    f"| {d.impl_id[:8]}... | {sharpe} | {acc} | {signals} | {age} | {d.reason} |"
                )
            lines.append("")

        # Retired specs
        if self.retired_specs:
            lines.append("## Retired Specs")
            lines.append("")
            lines.append("| Spec ID | Reason |")
            lines.append("|---------|--------|")
            for d in self.retired_specs:
                lines.append(f"| {d.spec_id[:8]}... | {d.reason} |")
            lines.append("")

        # Protected canonical
        if self.protected_canonical:
            lines.append("## Protected (CANONICAL)")
            lines.append("")
            lines.append("| Impl ID | Note |")
            lines.append("|---------|------|")
            for d in self.protected_canonical:
                lines.append(f"| {d.impl_id[:8]}... | {d.reason} |")
            lines.append("")

        # Health checks
        if self.health_results:
            lines.append("## Service Health")
            lines.append("")
            healthy = [h for h in self.health_results if h.healthy]
            unhealthy = [h for h in self.health_results if not h.healthy]
            lines.append(
                f"- Healthy: {len(healthy)}/{len(self.health_results)}"
            )
            if unhealthy:
                lines.append("")
                lines.append("### Unhealthy Services")
                lines.append("")
                lines.append("| Service | Error | Response Time |")
                lines.append("|---------|-------|---------------|")
                for h in unhealthy:
                    err = h.error or f"HTTP {h.status_code}"
                    lines.append(
                        f"| {h.service_name} | {err} | {h.response_time_ms}ms |"
                    )
            lines.append("")

        # Maintenance results
        if self.maintenance_results:
            lines.append("## Database Maintenance")
            lines.append("")
            lines.append("| Operation | Status | Details | Rows |")
            lines.append("|-----------|--------|---------|------|")
            for m in self.maintenance_results:
                status = "OK" if m.success else "FAILED"
                lines.append(
                    f"| {m.operation} | {status} | {m.details} | {m.rows_affected} |"
                )
            lines.append("")

        # State repairs
        if self.repair_results:
            lines.append("## State Repairs")
            lines.append("")
            lines.append("| Check | Found | Repaired | Details |")
            lines.append("|-------|-------|----------|---------|")
            for r in self.repair_results:
                lines.append(
                    f"| {r.check_name} | {r.inconsistencies_found} | {r.repaired} | {r.details} |"
                )
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert report to a dictionary for database storage."""
        return {
            "report_date": str(self.report_date),
            "evaluated_count": self.evaluated_count,
            "retired_implementations": self.retired_count,
            "retired_specs": len(self.retired_specs),
            "protected_count": self.protected_count,
            "report_markdown": self.to_markdown(),
            "distributed_to": {},
        }
