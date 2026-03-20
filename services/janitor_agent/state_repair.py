"""State repair module for detecting and fixing inconsistencies.

Detects broken state across services such as:
- Implementations referencing deleted specs
- Signals referencing retired implementations still marked active
- Strategies in signal routing but deleted from specs
- Stale retirement log entries
"""

from dataclasses import dataclass
from typing import Optional

from absl import logging


@dataclass
class RepairResult:
    """Result of a state repair operation."""

    check_name: str
    inconsistencies_found: int
    repaired: int
    details: str
    success: bool = True
    error: Optional[str] = None


class StateRepairer:
    """Detects and repairs state inconsistencies across the platform."""

    def __init__(self, connection_string: str):
        self._conn_string = connection_string

    def _get_connection(self):
        import psycopg2

        return psycopg2.connect(self._conn_string)

    def repair_orphaned_implementations(self) -> RepairResult:
        """Find implementations whose specs have been deleted and mark them RETIRED."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            # Count orphaned implementations
            cur.execute(
                """
                SELECT COUNT(*) FROM strategy_implementations i
                WHERE NOT EXISTS (
                    SELECT 1 FROM strategy_specs s WHERE s.spec_id = i.spec_id
                )
                AND i.status != 'RETIRED'
                """
            )
            count = cur.fetchone()[0]

            if count > 0:
                cur.execute(
                    """
                    UPDATE strategy_implementations
                    SET status = 'RETIRED', updated_at = NOW()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM strategy_specs s
                        WHERE s.spec_id = strategy_implementations.spec_id
                    )
                    AND status != 'RETIRED'
                    """
                )
                repaired = cur.rowcount
                conn.commit()
            else:
                repaired = 0

            cur.close()
            conn.close()

            logging.info(
                "Orphaned implementations: found=%d, repaired=%d", count, repaired
            )
            return RepairResult(
                check_name="orphaned_implementations",
                inconsistencies_found=count,
                repaired=repaired,
                details=f"Found {count} orphaned implementations, retired {repaired}",
            )
        except Exception as e:
            logging.error("Failed to repair orphaned implementations: %s", e)
            return RepairResult(
                check_name="orphaned_implementations",
                inconsistencies_found=0,
                repaired=0,
                details="Failed to check orphaned implementations",
                success=False,
                error=str(e),
            )

    def repair_stale_validated_status(self) -> RepairResult:
        """Find implementations marked VALIDATED but with no recent signals."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT COUNT(*) FROM strategy_implementations i
                WHERE i.status = 'VALIDATED'
                AND NOT EXISTS (
                    SELECT 1 FROM implementation_signals s
                    WHERE s.impl_id = i.impl_id
                    AND s.signal_timestamp > NOW() - INTERVAL '90 days'
                )
                AND i.created_at < NOW() - INTERVAL '180 days'
                """
            )
            count = cur.fetchone()[0]

            # Mark as STALE rather than retiring - needs human review
            if count > 0:
                cur.execute(
                    """
                    UPDATE strategy_implementations
                    SET status = 'STALE', updated_at = NOW()
                    WHERE status = 'VALIDATED'
                    AND NOT EXISTS (
                        SELECT 1 FROM implementation_signals s
                        WHERE s.impl_id = strategy_implementations.impl_id
                        AND s.signal_timestamp > NOW() - INTERVAL '90 days'
                    )
                    AND created_at < NOW() - INTERVAL '180 days'
                    """
                )
                repaired = cur.rowcount
                conn.commit()
            else:
                repaired = 0

            cur.close()
            conn.close()

            logging.info(
                "Stale validated implementations: found=%d, marked_stale=%d",
                count,
                repaired,
            )
            return RepairResult(
                check_name="stale_validated_status",
                inconsistencies_found=count,
                repaired=repaired,
                details=f"Found {count} stale validated implementations, marked {repaired} as STALE",
            )
        except Exception as e:
            logging.error("Failed to repair stale validated status: %s", e)
            return RepairResult(
                check_name="stale_validated_status",
                inconsistencies_found=0,
                repaired=0,
                details="Failed to check stale validated status",
                success=False,
                error=str(e),
            )

    def repair_signal_impl_mismatch(self) -> RepairResult:
        """Find signals referencing retired implementations that are still being routed."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT COUNT(DISTINCT s.impl_id)
                FROM implementation_signals s
                JOIN strategy_implementations i ON s.impl_id = i.impl_id
                WHERE i.status = 'RETIRED'
                AND s.signal_timestamp > NOW() - INTERVAL '7 days'
                AND s.signal_type = 'forward_test'
                """
            )
            count = cur.fetchone()[0]
            cur.close()
            conn.close()

            # This is a detection-only check; routing fix requires signal-router restart
            logging.info(
                "Signal-impl mismatches: %d retired impls still receiving signals",
                count,
            )
            return RepairResult(
                check_name="signal_impl_mismatch",
                inconsistencies_found=count,
                repaired=0,
                details=f"Found {count} retired implementations still receiving signals (requires signal-router restart)",
            )
        except Exception as e:
            logging.error("Failed to check signal-impl mismatch: %s", e)
            return RepairResult(
                check_name="signal_impl_mismatch",
                inconsistencies_found=0,
                repaired=0,
                details="Failed to check signal-impl mismatch",
                success=False,
                error=str(e),
            )

    def repair_duplicate_retirement_logs(self) -> RepairResult:
        """Clean up duplicate retirement log entries."""
        try:
            conn = self._get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                WITH duplicates AS (
                    SELECT log_id, ROW_NUMBER() OVER (
                        PARTITION BY impl_id, retirement_type
                        ORDER BY retired_at DESC
                    ) as rn
                    FROM retirement_log
                )
                DELETE FROM retirement_log
                WHERE log_id IN (
                    SELECT log_id FROM duplicates WHERE rn > 1
                )
                """
            )
            rows = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()

            logging.info("Cleaned up %d duplicate retirement log entries", rows)
            return RepairResult(
                check_name="duplicate_retirement_logs",
                inconsistencies_found=rows,
                repaired=rows,
                details=f"Removed {rows} duplicate retirement log entries",
            )
        except Exception as e:
            logging.error("Failed to clean up duplicate retirement logs: %s", e)
            return RepairResult(
                check_name="duplicate_retirement_logs",
                inconsistencies_found=0,
                repaired=0,
                details="Failed to clean up duplicate retirement logs",
                success=False,
                error=str(e),
            )

    def run_all_repairs(self) -> list[RepairResult]:
        """Run all state repair checks."""
        return [
            self.repair_orphaned_implementations(),
            self.repair_stale_validated_status(),
            self.repair_signal_impl_mismatch(),
            self.repair_duplicate_retirement_logs(),
        ]
