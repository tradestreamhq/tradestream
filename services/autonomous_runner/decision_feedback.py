"""Decision feedback service for collecting user feedback on autonomous decisions.

Supports the learning feedback loop by recording whether decisions were
helpful, executed, or incorrect. Feedback data feeds into the learning
engine for model improvement.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of feedback a user can submit."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    INCORRECT = "incorrect"
    EXECUTED = "executed"


@dataclass
class DecisionFeedback:
    """User feedback on an autonomous decision."""

    feedback_id: str
    decision_id: str
    user_id: str
    feedback_type: str
    comment: Optional[str] = None
    created_at: Optional[float] = None

    def __post_init__(self):
        if not self.feedback_id:
            self.feedback_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()


class DecisionFeedbackService:
    """Manages decision feedback collection and retrieval.

    Works with an existing database connection pool. Falls back
    gracefully when DB is unavailable, storing feedback in memory.
    """

    def __init__(self, db_pool=None):
        self._pool = db_pool
        self._in_memory: list[DecisionFeedback] = []
        self._stats = {
            "total_submitted": 0,
            "by_type": {t.value: 0 for t in FeedbackType},
        }

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

    def submit_feedback(
        self,
        decision_id: str,
        user_id: str,
        feedback_type: str,
        comment: Optional[str] = None,
    ) -> DecisionFeedback:
        """Submit feedback for a decision.

        Validates the feedback type and persists to DB if available,
        otherwise stores in memory.
        """
        if feedback_type not in [t.value for t in FeedbackType]:
            raise ValueError(
                f"Invalid feedback type: {feedback_type}. "
                f"Must be one of: {[t.value for t in FeedbackType]}"
            )

        feedback = DecisionFeedback(
            feedback_id=str(uuid.uuid4()),
            decision_id=decision_id,
            user_id=user_id,
            feedback_type=feedback_type,
            comment=comment,
        )

        if self.is_available:
            self._persist_feedback(feedback)
        else:
            self._in_memory.append(feedback)

        self._stats["total_submitted"] += 1
        self._stats["by_type"][feedback_type] = (
            self._stats["by_type"].get(feedback_type, 0) + 1
        )

        logger.info(
            "Feedback submitted: decision=%s type=%s user=%s",
            decision_id,
            feedback_type,
            user_id,
        )
        return feedback

    def _persist_feedback(self, feedback: DecisionFeedback):
        """Persist feedback to the database."""
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO decision_feedback
                        (feedback_id, decision_id, user_id, feedback_type, comment, created_at)
                    VALUES (%s, %s, %s, %s, %s, TO_TIMESTAMP(%s))
                    ON CONFLICT (feedback_id) DO NOTHING
                    """,
                    (
                        feedback.feedback_id,
                        feedback.decision_id,
                        feedback.user_id,
                        feedback.feedback_type,
                        feedback.comment,
                        feedback.created_at,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error("Failed to persist feedback: %s", e)
            self._in_memory.append(feedback)

    def get_feedback_for_decision(self, decision_id: str) -> list[dict]:
        """Get all feedback for a specific decision."""
        if not self.is_available:
            return [
                _feedback_to_dict(f)
                for f in self._in_memory
                if f.decision_id == decision_id
            ]

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT feedback_id, decision_id, user_id, feedback_type,
                           comment, created_at
                    FROM decision_feedback
                    WHERE decision_id = %s
                    ORDER BY created_at DESC
                    """,
                    (decision_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "feedback_id": r[0],
                        "decision_id": r[1],
                        "user_id": r[2],
                        "feedback_type": r[3],
                        "comment": r[4],
                        "created_at": (
                            r[5].isoformat() if hasattr(r[5], "isoformat") else r[5]
                        ),
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("Failed to get feedback for %s: %s", decision_id, e)
            return []

    def get_feedback_summary(self, hours: int = 24) -> dict:
        """Get aggregated feedback summary."""
        if not self.is_available:
            return self._stats

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT feedback_type, COUNT(*) as count
                    FROM decision_feedback
                    WHERE created_at >= NOW() - INTERVAL '%s hours'
                    GROUP BY feedback_type
                    """,
                    (hours,),
                )
                by_type = {row[0]: row[1] for row in cur.fetchall()}

                cur.execute(
                    """
                    SELECT COUNT(*) FROM decision_feedback
                    WHERE created_at >= NOW() - INTERVAL '%s hours'
                    """,
                    (hours,),
                )
                total = cur.fetchone()[0]

                return {
                    "total_submitted": total,
                    "by_type": by_type,
                    "period_hours": hours,
                }
        except Exception as e:
            logger.error("Failed to get feedback summary: %s", e)
            return self._stats

    def get_stats(self) -> dict:
        """Return feedback service statistics."""
        return {
            **self._stats,
            "in_memory_count": len(self._in_memory),
            "db_available": self.is_available,
        }


def _feedback_to_dict(feedback: DecisionFeedback) -> dict:
    """Convert a DecisionFeedback to a dictionary."""
    return {
        "feedback_id": feedback.feedback_id,
        "decision_id": feedback.decision_id,
        "user_id": feedback.user_id,
        "feedback_type": feedback.feedback_type,
        "comment": feedback.comment,
        "created_at": feedback.created_at,
    }
