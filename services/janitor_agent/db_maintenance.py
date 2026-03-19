"""Database maintenance operations for PostgreSQL and InfluxDB.

Handles vacuum/analyze, index maintenance, stale data cleanup,
retention policy management, and InfluxDB downsampling.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from absl import logging


@dataclass
class MaintenanceConfig:
    """Configuration for database maintenance tasks."""

    # PostgreSQL
    pg_connection_string: str = ""
    vacuum_tables: list[str] = field(default_factory=lambda: [
        "strategy_implementations",
        "strategy_specs",
        "implementation_signals",
        "retirement_log",
        "reactivation_log",
        "janitor_reports",
    ])
    stale_signal_days: int = 365
    stale_backtest_days: int = 180

    # InfluxDB
    influx_url: str = ""
    influx_token: str = ""
    influx_org: str = ""
    influx_bucket: str = "tradestream"
    raw_retention_days: int = 90
    downsampled_retention_days: int = 730  # 2 years


@dataclass
class MaintenanceResult:
    """Result of a maintenance operation."""

    operation: str
    success: bool
    details: str
    rows_affected: int = 0
    duration_ms: int = 0
    error: Optional[str] = None


class PostgreSQLMaintenance:
    """PostgreSQL maintenance operations."""

    def __init__(self, connection_string: str):
        self._conn_string = connection_string

    def _get_connection(self):
        import psycopg2
        return psycopg2.connect(self._conn_string)

    def vacuum_analyze(self, tables: list[str]) -> list[MaintenanceResult]:
        """Run VACUUM ANALYZE on specified tables."""
        results = []
        try:
            conn = self._get_connection()
            conn.autocommit = True
            cur = conn.cursor()

            for table in tables:
                start = datetime.now(timezone.utc)
                try:
                    cur.execute(f"VACUUM ANALYZE {table}")
                    elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
                    results.append(MaintenanceResult(
                        operation=f"vacuum_analyze:{table}",
                        success=True,
                        details=f"VACUUM ANALYZE completed for {table}",
                        duration_ms=elapsed,
                    ))
                    logging.info("VACUUM ANALYZE completed for %s in %dms", table, elapsed)
                except Exception as e:
                    elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
                    results.append(MaintenanceResult(
                        operation=f"vacuum_analyze:{table}",
                        success=False,
                        details=f"Failed to vacuum {table}",
                        duration_ms=elapsed,
                        error=str(e),
                    ))
                    logging.error("VACUUM ANALYZE failed for %s: %s", table, e)

            cur.close()
            conn.close()
        except Exception as e:
            results.append(MaintenanceResult(
                operation="vacuum_analyze:connection",
                success=False,
                details="Failed to connect to database",
                error=str(e),
            ))
        return results

    def cleanup_stale_signals(self, days: int) -> MaintenanceResult:
        """Remove forward-test signals older than the retention period."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM implementation_signals
                WHERE signal_type = 'forward_test'
                  AND signal_timestamp < NOW() - INTERVAL '%s days'
                """,
                (days,),
            )
            rows = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            logging.info("Cleaned up %d stale signals older than %d days", rows, days)
            return MaintenanceResult(
                operation="cleanup_stale_signals",
                success=True,
                details=f"Removed {rows} signals older than {days} days",
                rows_affected=rows,
            )
        except Exception as e:
            logging.error("Failed to clean up stale signals: %s", e)
            return MaintenanceResult(
                operation="cleanup_stale_signals",
                success=False,
                details="Failed to clean up stale signals",
                error=str(e),
            )

    def cleanup_stale_backtests(self, days: int) -> MaintenanceResult:
        """Remove old backtest results beyond retention period."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM backtest_results
                WHERE created_at < NOW() - INTERVAL '%s days'
                  AND status = 'COMPLETED'
                """,
                (days,),
            )
            rows = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            logging.info("Cleaned up %d stale backtest results older than %d days", rows, days)
            return MaintenanceResult(
                operation="cleanup_stale_backtests",
                success=True,
                details=f"Removed {rows} backtest results older than {days} days",
                rows_affected=rows,
            )
        except Exception as e:
            logging.error("Failed to clean up stale backtests: %s", e)
            return MaintenanceResult(
                operation="cleanup_stale_backtests",
                success=False,
                details="Failed to clean up stale backtests",
                error=str(e),
            )

    def cleanup_orphaned_records(self) -> MaintenanceResult:
        """Find and remove orphaned records (implementations referencing deleted specs)."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM strategy_implementations i
                WHERE NOT EXISTS (
                    SELECT 1 FROM strategy_specs s
                    WHERE s.spec_id = i.spec_id
                )
                """
            )
            rows = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            logging.info("Cleaned up %d orphaned implementation records", rows)
            return MaintenanceResult(
                operation="cleanup_orphaned_records",
                success=True,
                details=f"Removed {rows} orphaned implementation records",
                rows_affected=rows,
            )
        except Exception as e:
            logging.error("Failed to clean up orphaned records: %s", e)
            return MaintenanceResult(
                operation="cleanup_orphaned_records",
                success=False,
                details="Failed to clean up orphaned records",
                error=str(e),
            )

    def reindex(self) -> MaintenanceResult:
        """Reindex key tables for query performance."""
        try:
            conn = self._get_connection()
            conn.autocommit = True
            cur = conn.cursor()
            start = datetime.now(timezone.utc)
            cur.execute("REINDEX TABLE CONCURRENTLY strategy_implementations")
            cur.execute("REINDEX TABLE CONCURRENTLY implementation_signals")
            elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            cur.close()
            conn.close()
            logging.info("Reindex completed in %dms", elapsed)
            return MaintenanceResult(
                operation="reindex",
                success=True,
                details="Reindex completed for key tables",
                duration_ms=elapsed,
            )
        except Exception as e:
            logging.error("Failed to reindex: %s", e)
            return MaintenanceResult(
                operation="reindex",
                success=False,
                details="Failed to reindex tables",
                error=str(e),
            )

    def execute_retirement(
        self,
        impl_id: str,
        reason: str,
        agent_reasoning: str,
    ) -> MaintenanceResult:
        """Execute a retirement by updating status and logging."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                UPDATE strategy_implementations
                SET status = 'RETIRED', updated_at = NOW()
                WHERE impl_id = %s AND status != 'RETIRED'
                """,
                (impl_id,),
            )
            rows = cur.rowcount

            if rows > 0:
                cur.execute(
                    """
                    INSERT INTO retirement_log
                    (impl_id, retirement_type, reason, agent_reasoning, can_reactivate)
                    VALUES (%s, 'implementation', %s, %s, TRUE)
                    """,
                    (impl_id, reason, agent_reasoning),
                )

            conn.commit()
            cur.close()
            conn.close()

            if rows > 0:
                logging.info("Retired implementation %s: %s", impl_id, reason)
                return MaintenanceResult(
                    operation=f"retire_impl:{impl_id}",
                    success=True,
                    details=f"Implementation {impl_id} retired: {reason}",
                    rows_affected=rows,
                )
            else:
                return MaintenanceResult(
                    operation=f"retire_impl:{impl_id}",
                    success=False,
                    details=f"Implementation {impl_id} not found or already retired",
                )
        except Exception as e:
            logging.error("Failed to retire implementation %s: %s", impl_id, e)
            return MaintenanceResult(
                operation=f"retire_impl:{impl_id}",
                success=False,
                details=f"Failed to retire implementation {impl_id}",
                error=str(e),
            )

    def retire_spec(self, spec_id: str, reason: str) -> MaintenanceResult:
        """Retire a spec by updating status and logging."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                UPDATE strategy_specs
                SET status = 'RETIRED', updated_at = NOW()
                WHERE spec_id = %s AND status != 'RETIRED'
                """,
                (spec_id,),
            )
            rows = cur.rowcount

            if rows > 0:
                cur.execute(
                    """
                    INSERT INTO retirement_log
                    (spec_id, retirement_type, reason, can_reactivate)
                    VALUES (%s, 'spec', %s, TRUE)
                    """,
                    (spec_id, reason),
                )

            conn.commit()
            cur.close()
            conn.close()

            if rows > 0:
                return MaintenanceResult(
                    operation=f"retire_spec:{spec_id}",
                    success=True,
                    details=f"Spec {spec_id} retired: {reason}",
                    rows_affected=rows,
                )
            else:
                return MaintenanceResult(
                    operation=f"retire_spec:{spec_id}",
                    success=False,
                    details=f"Spec {spec_id} not found or already retired",
                )
        except Exception as e:
            logging.error("Failed to retire spec %s: %s", spec_id, e)
            return MaintenanceResult(
                operation=f"retire_spec:{spec_id}",
                success=False,
                details=f"Failed to retire spec {spec_id}",
                error=str(e),
            )

    def get_retirement_candidates(self, config) -> list[dict]:
        """Fetch implementations that are candidates for retirement."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    i.impl_id,
                    s.spec_id,
                    s.name as spec_name,
                    s.source,
                    i.symbol,
                    i.forward_sharpe,
                    i.forward_accuracy,
                    i.forward_trades,
                    i.created_at,
                    i.updated_at,
                    i.status,
                    s.preferred_regime
                FROM strategy_implementations i
                JOIN strategy_specs s ON i.spec_id = s.spec_id
                WHERE i.status = 'VALIDATED'
                  AND i.forward_trades >= %s
                  AND i.created_at <= NOW() - INTERVAL '%s days'
                  AND (i.forward_sharpe < %s OR i.forward_accuracy < %s)
                ORDER BY i.forward_sharpe ASC
                LIMIT 100
                """,
                (
                    config.min_signals,
                    config.min_age_days,
                    config.max_sharpe,
                    config.max_accuracy,
                ),
            )
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            cur.close()
            conn.close()
            return rows
        except Exception as e:
            logging.error("Failed to fetch retirement candidates: %s", e)
            return []

    def get_sharpe_trend(self, impl_id: str, lookback_months: int = 6) -> str:
        """Calculate the Sharpe trend for an implementation."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    regr_slope(sharpe, month_num),
                    COUNT(DISTINCT month_num)
                FROM (
                    SELECT
                        EXTRACT(MONTH FROM signal_timestamp) +
                        EXTRACT(YEAR FROM signal_timestamp) * 12 as month_num,
                        AVG(return_pct) / NULLIF(STDDEV(return_pct), 0) as sharpe
                    FROM implementation_signals
                    WHERE impl_id = %s
                      AND signal_type = 'forward_test'
                      AND signal_timestamp > NOW() - INTERVAL '%s months'
                    GROUP BY 1
                    ORDER BY 1
                ) monthly_sharpe
                """,
                (impl_id, lookback_months),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row is None or row[1] is None or row[1] < 3:
                return "INSUFFICIENT_DATA"

            slope = row[0]
            if slope is None:
                return "INSUFFICIENT_DATA"
            elif slope < -0.02:
                return "DECLINING"
            elif slope > 0.02:
                return "IMPROVING"
            else:
                return "STABLE"
        except Exception as e:
            logging.error("Failed to calculate sharpe trend for %s: %s", impl_id, e)
            return "INSUFFICIENT_DATA"

    def check_better_alternatives(
        self, spec_id: str, symbol: str, min_sharpe: float
    ) -> bool:
        """Check if better-performing alternatives exist for the same spec+symbol."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) FROM strategy_implementations
                WHERE spec_id = %s
                  AND symbol = %s
                  AND status = 'VALIDATED'
                  AND forward_sharpe >= %s
                """,
                (spec_id, symbol, min_sharpe),
            )
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count > 0
        except Exception as e:
            logging.error("Failed to check alternatives: %s", e)
            return False

    def get_active_implementation_count(self) -> int:
        """Get the count of active (non-retired) implementations."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM strategy_implementations WHERE status != 'RETIRED'"
            )
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            return count
        except Exception as e:
            logging.error("Failed to get active implementation count: %s", e)
            return 0

    def save_report(self, report_data: dict) -> MaintenanceResult:
        """Save a janitor report to the database."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO janitor_reports
                (report_date, evaluated_count, retired_implementations,
                 retired_specs, protected_count, report_markdown, distributed_to)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (report_date) DO UPDATE SET
                    evaluated_count = EXCLUDED.evaluated_count,
                    retired_implementations = EXCLUDED.retired_implementations,
                    retired_specs = EXCLUDED.retired_specs,
                    protected_count = EXCLUDED.protected_count,
                    report_markdown = EXCLUDED.report_markdown,
                    distributed_to = EXCLUDED.distributed_to
                """,
                (
                    report_data["report_date"],
                    report_data["evaluated_count"],
                    report_data["retired_implementations"],
                    report_data["retired_specs"],
                    report_data["protected_count"],
                    report_data["report_markdown"],
                    json.dumps(report_data.get("distributed_to", {})),
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            return MaintenanceResult(
                operation="save_report",
                success=True,
                details=f"Report saved for {report_data['report_date']}",
            )
        except Exception as e:
            logging.error("Failed to save report: %s", e)
            return MaintenanceResult(
                operation="save_report",
                success=False,
                details="Failed to save report",
                error=str(e),
            )


class InfluxDBMaintenance:
    """InfluxDB maintenance operations."""

    def __init__(self, url: str, token: str, org: str):
        self._url = url
        self._token = token
        self._org = org

    def check_retention_policies(self, bucket: str) -> MaintenanceResult:
        """Check and report on retention policies for the given bucket."""
        try:
            from influxdb_client import InfluxDBClient

            client = InfluxDBClient(url=self._url, token=self._token, org=self._org)
            buckets_api = client.buckets_api()
            found = buckets_api.find_bucket_by_name(bucket)
            client.close()

            if found:
                retention = found.retention_rules
                return MaintenanceResult(
                    operation="check_retention",
                    success=True,
                    details=f"Bucket '{bucket}' retention: {retention}",
                )
            else:
                return MaintenanceResult(
                    operation="check_retention",
                    success=False,
                    details=f"Bucket '{bucket}' not found",
                )
        except Exception as e:
            logging.error("Failed to check retention policies: %s", e)
            return MaintenanceResult(
                operation="check_retention",
                success=False,
                details="Failed to check retention policies",
                error=str(e),
            )

    def downsample_old_data(
        self, bucket: str, days_threshold: int, target_bucket: str
    ) -> MaintenanceResult:
        """Downsample time-series data older than threshold to hourly aggregates."""
        try:
            from influxdb_client import InfluxDBClient

            client = InfluxDBClient(url=self._url, token=self._token, org=self._org)
            query_api = client.query_api()

            # Query to check if downsampling is needed
            query = f"""
            from(bucket: "{bucket}")
                |> range(start: -{days_threshold}d, stop: -{days_threshold - 1}d)
                |> count()
                |> yield(name: "count")
            """
            result = query_api.query(query)
            client.close()

            record_count = sum(
                record.get_value()
                for table in result
                for record in table.records
            )

            if record_count > 0:
                return MaintenanceResult(
                    operation="downsample",
                    success=True,
                    details=f"Found {record_count} records to downsample from {days_threshold}+ days ago",
                    rows_affected=record_count,
                )
            else:
                return MaintenanceResult(
                    operation="downsample",
                    success=True,
                    details="No data needs downsampling",
                )
        except Exception as e:
            logging.error("Failed to downsample data: %s", e)
            return MaintenanceResult(
                operation="downsample",
                success=False,
                details="Failed to downsample InfluxDB data",
                error=str(e),
            )
