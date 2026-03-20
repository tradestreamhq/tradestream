"""Retention policy enforcement for agent decisions.

Implements the spec-defined data lifecycle:
- Hot (0-30 days): Primary DB, real-time queries
- Warm (30-90 days): Primary DB, historical analysis
- Cold (90+ days): Archived and deleted from primary DB
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RetentionConfig:
    """Configuration for decision retention policy."""

    hot_retention_days: int = 30
    warm_retention_days: int = 90
    archive_enabled: bool = True
    archive_destination: str = "s3://tradestream-archive/decisions/"
    delete_after_archive: bool = True
    vacuum_after_delete: bool = True


class RetentionManager:
    """Manages data lifecycle for agent decisions."""

    def __init__(self, config: Optional[RetentionConfig] = None):
        self.config = config or RetentionConfig()
        self._last_cleanup_result = {}

    def get_cleanup_sql(self) -> list:
        """Generate SQL statements for retention cleanup.

        Returns list of (description, sql) tuples to execute in order.
        """
        days = self.config.warm_retention_days
        statements = []

        # Count records to be cleaned
        statements.append(
            (
                "count_expired",
                f"""
            SELECT COUNT(*) as expired_count
            FROM agent_decisions
            WHERE created_at < NOW() - INTERVAL '{days} days'
            """,
            )
        )

        # Delete expired feedback first (foreign key)
        statements.append(
            (
                "delete_expired_feedback",
                f"""
            DELETE FROM decision_feedback
            WHERE decision_id IN (
                SELECT decision_id FROM agent_decisions
                WHERE created_at < NOW() - INTERVAL '{days} days'
            )
            """,
            )
        )

        # Delete expired outcomes (foreign key)
        statements.append(
            (
                "delete_expired_outcomes",
                f"""
            DELETE FROM decision_outcomes
            WHERE decision_id IN (
                SELECT decision_id FROM agent_decisions
                WHERE created_at < NOW() - INTERVAL '{days} days'
            )
            """,
            )
        )

        # Delete expired decisions
        statements.append(
            (
                "delete_expired_decisions",
                f"""
            DELETE FROM agent_decisions
            WHERE created_at < NOW() - INTERVAL '{days} days'
            """,
            )
        )

        if self.config.vacuum_after_delete:
            statements.append(
                (
                    "vacuum_decisions",
                    "VACUUM ANALYZE agent_decisions",
                )
            )

        return statements

    def get_archive_query(self) -> str:
        """Generate the COPY query for archiving decisions before deletion."""
        days = self.config.warm_retention_days
        return f"""
        SELECT decision_id, session_id, user_id, symbol, action,
               confidence, opportunity_score, opportunity_tier,
               reasoning, model_used, agent_type, latency_ms,
               created_at
        FROM agent_decisions
        WHERE created_at < NOW() - INTERVAL '{days} days'
        ORDER BY created_at ASC
        """

    def get_status(self) -> dict:
        """Return current retention configuration status."""
        return {
            "hot_retention_days": self.config.hot_retention_days,
            "warm_retention_days": self.config.warm_retention_days,
            "archive_enabled": self.config.archive_enabled,
            "archive_destination": self.config.archive_destination,
            "last_cleanup": self._last_cleanup_result,
        }
