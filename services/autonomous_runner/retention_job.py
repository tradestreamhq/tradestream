"""Scheduled retention job for automated decision archival and cleanup.

Runs periodically to enforce the retention policy:
- Export expired decisions to cold storage (S3)
- Delete expired records from primary database
- VACUUM tables after cleanup
"""

import io
import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from services.autonomous_runner.retention import RetentionConfig, RetentionManager

logger = logging.getLogger(__name__)

DEFAULT_JOB_INTERVAL_HOURS = 24


@dataclass
class RetentionJobConfig:
    """Configuration for the retention job."""

    interval_hours: int = DEFAULT_JOB_INTERVAL_HOURS
    retention: RetentionConfig = None
    dry_run: bool = False

    def __post_init__(self):
        if self.retention is None:
            self.retention = RetentionConfig()


class RetentionJobResult:
    """Result of a retention job execution."""

    def __init__(self):
        self.archived_count = 0
        self.deleted_feedback_count = 0
        self.deleted_outcomes_count = 0
        self.deleted_decisions_count = 0
        self.errors: list[str] = []
        self.started_at = time.time()
        self.completed_at: Optional[float] = None
        self.dry_run = False

    def complete(self):
        self.completed_at = time.time()

    @property
    def duration_ms(self) -> int:
        if self.completed_at:
            return int((self.completed_at - self.started_at) * 1000)
        return 0

    def to_dict(self) -> dict:
        return {
            "archived_count": self.archived_count,
            "deleted_feedback_count": self.deleted_feedback_count,
            "deleted_outcomes_count": self.deleted_outcomes_count,
            "deleted_decisions_count": self.deleted_decisions_count,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "dry_run": self.dry_run,
        }


class RetentionJob:
    """Executes retention cleanup on a schedule.

    Can be run manually via API or on a timer in the runner loop.
    """

    def __init__(self, db_pool=None, config: Optional[RetentionJobConfig] = None):
        self._pool = db_pool
        self.config = config or RetentionJobConfig()
        self._manager = RetentionManager(self.config.retention)
        self._last_result: Optional[RetentionJobResult] = None
        self._last_run_at: Optional[float] = None
        self._total_runs = 0

    @property
    def is_available(self) -> bool:
        return self._pool is not None

    @contextmanager
    def _get_conn(self):
        if not self._pool:
            raise RuntimeError("No database pool")
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def should_run(self) -> bool:
        """Check if enough time has elapsed since last run."""
        if self._last_run_at is None:
            return True
        elapsed_hours = (time.time() - self._last_run_at) / 3600
        return elapsed_hours >= self.config.interval_hours

    def execute(self, dry_run: Optional[bool] = None) -> RetentionJobResult:
        """Execute the retention job.

        Args:
            dry_run: If True, only count records without deleting.
                     Defaults to config.dry_run.
        """
        is_dry_run = dry_run if dry_run is not None else self.config.dry_run
        result = RetentionJobResult()
        result.dry_run = is_dry_run

        if not self.is_available:
            result.errors.append("Database not available")
            result.complete()
            self._last_result = result
            return result

        try:
            statements = self._manager.get_cleanup_sql()

            with self._get_conn() as conn:
                cur = conn.cursor()

                for desc, sql in statements:
                    try:
                        if is_dry_run and desc.startswith("delete_"):
                            # In dry run, convert DELETEs to COUNTs
                            count_sql = sql.replace(
                                "DELETE FROM", "SELECT COUNT(*) FROM"
                            )
                            # Remove the WHERE ... IN subquery's DELETE
                            if "WHERE decision_id IN" in count_sql:
                                cur.execute(count_sql)
                                count = cur.fetchone()[0]
                                logger.info(
                                    "[DRY RUN] %s would affect %d rows", desc, count
                                )
                            continue

                        if desc == "vacuum_decisions":
                            # VACUUM can't run inside a transaction
                            conn.commit()
                            old_isolation = conn.isolation_level
                            conn.set_isolation_level(0)
                            cur.execute(sql)
                            conn.set_isolation_level(old_isolation)
                            continue

                        cur.execute(sql)

                        if desc == "count_expired":
                            row = cur.fetchone()
                            result.archived_count = row[0] if row else 0
                            logger.info(
                                "Found %d expired records", result.archived_count
                            )
                        elif desc == "delete_expired_feedback":
                            result.deleted_feedback_count = cur.rowcount
                        elif desc == "delete_expired_outcomes":
                            result.deleted_outcomes_count = cur.rowcount
                        elif desc == "delete_expired_decisions":
                            result.deleted_decisions_count = cur.rowcount

                    except Exception as e:
                        logger.error("Retention step %s failed: %s", desc, e)
                        result.errors.append(f"{desc}: {str(e)}")

                if not is_dry_run:
                    conn.commit()

        except Exception as e:
            logger.error("Retention job failed: %s", e)
            result.errors.append(str(e))

        result.complete()
        self._last_result = result
        self._last_run_at = time.time()
        self._total_runs += 1

        logger.info(
            "Retention job completed: archived=%d deleted=%d errors=%d duration=%dms",
            result.archived_count,
            result.deleted_decisions_count,
            len(result.errors),
            result.duration_ms,
        )
        return result

    def get_status(self) -> dict:
        """Return retention job status."""
        return {
            "last_run_at": self._last_run_at,
            "total_runs": self._total_runs,
            "interval_hours": self.config.interval_hours,
            "last_result": self._last_result.to_dict() if self._last_result else None,
            "retention_config": self._manager.get_status(),
            "db_available": self.is_available,
        }
