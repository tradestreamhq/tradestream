"""Dashboard data provider for the Janitor Agent.

Exposes last run times, items cleaned, health status, and historical
trends for display in the TradeStream admin dashboard.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from absl import logging


@dataclass
class DashboardData:
    """Complete dashboard snapshot for the janitor agent."""

    # Last run info
    last_run_at: Optional[str] = None
    last_run_duration_seconds: float = 0.0
    next_scheduled_run: Optional[str] = None

    # Retirement stats
    total_retired_implementations: int = 0
    total_retired_specs: int = 0
    retirements_last_7_days: int = 0
    reactivations_last_7_days: int = 0

    # Cleanup stats
    stale_signals_cleaned: int = 0
    stale_backtests_cleaned: int = 0
    orphaned_records_cleaned: int = 0

    # Health overview
    services_healthy: int = 0
    services_unhealthy: int = 0
    unhealthy_services: list[dict] = field(default_factory=list)

    # State repair stats
    inconsistencies_found: int = 0
    inconsistencies_repaired: int = 0

    # Log rotation stats
    logs_rotated: int = 0
    logs_deleted: int = 0
    log_space_freed_bytes: int = 0

    # Historical reports (last N days)
    recent_reports: list[dict] = field(default_factory=list)


class DashboardProvider:
    """Provides dashboard data by querying the janitor database."""

    def __init__(self, connection_string: str):
        self._conn_string = connection_string

    def _get_connection(self):
        import psycopg2

        return psycopg2.connect(self._conn_string)

    def get_dashboard_data(self) -> DashboardData:
        """Aggregate all dashboard data from the database."""
        data = DashboardData()

        try:
            conn = self._get_connection()
            cur = conn.cursor()

            # Last report info
            cur.execute(
                """
                SELECT report_date, evaluated_count, retired_implementations,
                       retired_specs, protected_count, created_at
                FROM janitor_reports
                ORDER BY report_date DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row:
                data.last_run_at = row[5].isoformat() if row[5] else None

            # Total retirement counts
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE retirement_type = 'implementation'),
                    COUNT(*) FILTER (WHERE retirement_type = 'spec')
                FROM retirement_log
                """
            )
            row = cur.fetchone()
            if row:
                data.total_retired_implementations = row[0] or 0
                data.total_retired_specs = row[1] or 0

            # Last 7 days retirements
            cur.execute(
                """
                SELECT COUNT(*) FROM retirement_log
                WHERE retired_at > NOW() - INTERVAL '7 days'
                """
            )
            row = cur.fetchone()
            data.retirements_last_7_days = row[0] if row else 0

            # Last 7 days reactivations
            cur.execute(
                """
                SELECT COUNT(*) FROM reactivation_log
                WHERE reactivated_at > NOW() - INTERVAL '7 days'
                """
            )
            row = cur.fetchone()
            data.reactivations_last_7_days = row[0] if row else 0

            # Recent reports for trend chart
            cur.execute(
                """
                SELECT report_date, evaluated_count, retired_implementations,
                       retired_specs, protected_count
                FROM janitor_reports
                ORDER BY report_date DESC
                LIMIT 14
                """
            )
            for row in cur.fetchall():
                data.recent_reports.append(
                    {
                        "date": str(row[0]),
                        "evaluated": row[1],
                        "retired_impls": row[2],
                        "retired_specs": row[3],
                        "protected": row[4],
                    }
                )

            cur.close()
            conn.close()
        except Exception as e:
            logging.error("Failed to fetch dashboard data: %s", e)

        return data

    def get_dashboard_json(self) -> dict:
        """Return dashboard data as a JSON-serializable dict."""
        data = self.get_dashboard_data()
        return {
            "last_run": {
                "at": data.last_run_at,
                "duration_seconds": data.last_run_duration_seconds,
            },
            "retirements": {
                "total_implementations": data.total_retired_implementations,
                "total_specs": data.total_retired_specs,
                "last_7_days": data.retirements_last_7_days,
                "reactivations_last_7_days": data.reactivations_last_7_days,
            },
            "cleanup": {
                "stale_signals": data.stale_signals_cleaned,
                "stale_backtests": data.stale_backtests_cleaned,
                "orphaned_records": data.orphaned_records_cleaned,
            },
            "health": {
                "healthy": data.services_healthy,
                "unhealthy": data.services_unhealthy,
                "unhealthy_services": data.unhealthy_services,
            },
            "state_repair": {
                "found": data.inconsistencies_found,
                "repaired": data.inconsistencies_repaired,
            },
            "log_rotation": {
                "rotated": data.logs_rotated,
                "deleted": data.logs_deleted,
                "space_freed_bytes": data.log_space_freed_bytes,
            },
            "recent_reports": data.recent_reports,
        }
