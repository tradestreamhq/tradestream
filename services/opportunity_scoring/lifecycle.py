"""Opportunity lifecycle tracking.

Tracks opportunities through their lifecycle:
scored → signaled → entered → closed/expired
"""

from datetime import datetime, timezone
from typing import Optional

from .models import OpportunityStatus, ScoredOpportunity


class OpportunityTracker:
    """Tracks opportunity lifecycle state transitions.

    Thread-safe in-memory tracker. In production, this would be backed
    by a database, but the interface remains the same.
    """

    def __init__(self):
        self._opportunities: dict[str, ScoredOpportunity] = {}

    def track(self, opportunity: ScoredOpportunity) -> None:
        """Add a newly scored opportunity to tracking."""
        self._opportunities[opportunity.opportunity_id] = opportunity

    def get(self, opportunity_id: str) -> Optional[ScoredOpportunity]:
        """Get an opportunity by ID."""
        return self._opportunities.get(opportunity_id)

    def mark_signaled(self, opportunity_id: str) -> bool:
        """Mark an opportunity as signaled (alert sent to user).

        Returns:
            True if transition succeeded, False if not found or invalid state.
        """
        opp = self._opportunities.get(opportunity_id)
        if opp is None or opp.status != OpportunityStatus.SCORED.value:
            return False
        opp.status = OpportunityStatus.SIGNALED.value
        return True

    def mark_entered(self, opportunity_id: str) -> bool:
        """Mark an opportunity as entered (trade placed).

        Returns:
            True if transition succeeded.
        """
        opp = self._opportunities.get(opportunity_id)
        if opp is None or opp.status not in (
            OpportunityStatus.SCORED.value,
            OpportunityStatus.SIGNALED.value,
        ):
            return False
        opp.status = OpportunityStatus.ENTERED.value
        opp.entered_at = datetime.now(timezone.utc)
        return True

    def mark_closed(
        self, opportunity_id: str, outcome_return: Optional[float] = None
    ) -> bool:
        """Mark an opportunity as closed (trade completed).

        Args:
            opportunity_id: ID of the opportunity.
            outcome_return: Realized return (e.g. 0.025 for 2.5%).

        Returns:
            True if transition succeeded.
        """
        opp = self._opportunities.get(opportunity_id)
        if opp is None or opp.status != OpportunityStatus.ENTERED.value:
            return False
        opp.status = OpportunityStatus.CLOSED.value
        opp.closed_at = datetime.now(timezone.utc)
        opp.outcome_return = outcome_return
        return True

    def mark_expired(self, opportunity_id: str) -> bool:
        """Mark a stale opportunity as expired.

        Returns:
            True if transition succeeded.
        """
        opp = self._opportunities.get(opportunity_id)
        if opp is None or opp.status in (
            OpportunityStatus.CLOSED.value,
            OpportunityStatus.EXPIRED.value,
        ):
            return False
        opp.status = OpportunityStatus.EXPIRED.value
        return True

    def expire_stale(self) -> int:
        """Expire all stale opportunities that haven't been acted on.

        Returns:
            Number of opportunities expired.
        """
        count = 0
        for opp in list(self._opportunities.values()):
            if opp.is_stale and opp.status in (
                OpportunityStatus.SCORED.value,
                OpportunityStatus.SIGNALED.value,
            ):
                opp.status = OpportunityStatus.EXPIRED.value
                count += 1
        return count

    def list_active(self) -> list[ScoredOpportunity]:
        """List all non-expired, non-closed opportunities."""
        return [
            opp
            for opp in self._opportunities.values()
            if opp.status not in (
                OpportunityStatus.CLOSED.value,
                OpportunityStatus.EXPIRED.value,
            )
        ]

    def list_all(self) -> list[ScoredOpportunity]:
        """List all tracked opportunities."""
        return list(self._opportunities.values())

    def get_stats(self) -> dict:
        """Get summary statistics of tracked opportunities."""
        by_status: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        total_score = 0.0
        count = 0

        for opp in self._opportunities.values():
            by_status[opp.status] = by_status.get(opp.status, 0) + 1
            by_tier[opp.tier] = by_tier.get(opp.tier, 0) + 1
            total_score += opp.opportunity_score
            count += 1

        return {
            "total": count,
            "by_status": by_status,
            "by_tier": by_tier,
            "avg_score": round(total_score / count, 1) if count > 0 else 0.0,
        }
