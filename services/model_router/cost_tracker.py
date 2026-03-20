"""Cost Tracker — tracks LLM usage costs per model per agent type.

Stores usage records in-memory with optional persistence to PostgreSQL.
Provides monthly aggregation for budget enforcement.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from services.model_router.model_registry import get_model

logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Single LLM call usage record."""

    agent_type: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    success: bool
    retries: int = 0
    fallback_used: bool = False
    timestamp: float = field(default_factory=time.time)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class CostSummary:
    """Aggregated cost summary."""

    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_retries: int = 0
    fallback_count: int = 0
    by_model: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    by_agent: dict[str, float] = field(default_factory=lambda: defaultdict(float))


class CostTracker:
    """Tracks LLM API costs in-memory with monthly aggregation.

    Usage:
        tracker = CostTracker()
        tracker.record_usage(
            agent_type="signal-generator",
            model_id="google/gemini-3.0-flash",
            input_tokens=1000,
            output_tokens=500,
        )
        summary = tracker.get_monthly_summary()
        print(f"Month cost: ${summary.total_cost_usd:.2f}")
    """

    def __init__(self):
        self._records: list[UsageRecord] = []

    def record_usage(
        self,
        agent_type: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        success: bool = True,
        retries: int = 0,
        fallback_used: bool = False,
    ) -> UsageRecord:
        """Record a model call and calculate its cost."""
        profile = get_model(model_id)
        if profile:
            cost = (
                input_tokens * profile.pricing.input_per_token
                + output_tokens * profile.pricing.output_per_token
            )
        else:
            # Unknown model — estimate conservatively
            cost = (input_tokens + output_tokens) * 0.00001
            logger.warning(
                "Unknown model %s, using conservative cost estimate", model_id
            )

        record = UsageRecord(
            agent_type=agent_type,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            success=success,
            retries=retries,
            fallback_used=fallback_used,
        )
        self._records.append(record)
        logger.debug(
            "Usage: agent=%s model=%s tokens=%d cost=$%.6f",
            agent_type,
            model_id,
            record.total_tokens,
            cost,
        )
        return record

    def get_monthly_cost(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> float:
        """Get total cost for a given month (defaults to current month)."""
        now = datetime.now(timezone.utc)
        target_year = year or now.year
        target_month = month or now.month
        total = 0.0
        for r in self._records:
            dt = datetime.fromtimestamp(r.timestamp, tz=timezone.utc)
            if dt.year == target_year and dt.month == target_month:
                total += r.cost_usd
        return total

    def get_monthly_summary(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> CostSummary:
        """Get aggregated cost summary for a month."""
        now = datetime.now(timezone.utc)
        target_year = year or now.year
        target_month = month or now.month

        summary = CostSummary()
        for r in self._records:
            dt = datetime.fromtimestamp(r.timestamp, tz=timezone.utc)
            if dt.year != target_year or dt.month != target_month:
                continue
            summary.total_cost_usd += r.cost_usd
            summary.total_input_tokens += r.input_tokens
            summary.total_output_tokens += r.output_tokens
            summary.total_requests += 1
            if r.success:
                summary.successful_requests += 1
            else:
                summary.failed_requests += 1
            summary.total_retries += r.retries
            if r.fallback_used:
                summary.fallback_count += 1
            summary.by_model[r.model_id] += r.cost_usd
            summary.by_agent[r.agent_type] += r.cost_usd

        return summary

    def get_cost_by_agent(self) -> dict[str, float]:
        """Get current month cost broken down by agent type."""
        summary = self.get_monthly_summary()
        return dict(summary.by_agent)

    def get_cost_by_model(self) -> dict[str, float]:
        """Get current month cost broken down by model."""
        summary = self.get_monthly_summary()
        return dict(summary.by_model)

    def clear(self):
        """Clear all records (for testing)."""
        self._records.clear()
