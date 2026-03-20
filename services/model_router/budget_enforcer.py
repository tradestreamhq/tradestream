"""Budget Enforcer — monitors monthly LLM spend and applies degradation tiers.

Degradation tiers per spec:
  80% → alert only
  90% → disable Opus, cap at Sonnet
  95% → reduce signal frequency to 5-min
  100% → emergency mode (Flash-only, 15-min frequency)
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DegradationTier:
    """A budget degradation tier."""

    threshold_pct: int
    action: str
    description: str


DEFAULT_DEGRADATION_TIERS = [
    DegradationTier(80, "alert", "Send warning notification"),
    DegradationTier(90, "reduce_premium", "Disable Opus escalation, cap at Sonnet"),
    DegradationTier(
        95, "reduce_frequency", "Reduce signal frequency from 1-min to 5-min"
    ),
    DegradationTier(
        100, "emergency_mode", "Flash-only mode, 15-min frequency, critical alerts only"
    ),
]


class BudgetEnforcer:
    """Monitors monthly budget and activates degradation tiers.

    Usage:
        enforcer = BudgetEnforcer(monthly_limit_usd=3000)
        tier = enforcer.check(current_cost=2500)
        if tier:
            print(f"Degradation active: {tier.action}")
    """

    def __init__(
        self,
        monthly_limit_usd: float = 3000.0,
        tiers: Optional[list[DegradationTier]] = None,
    ):
        self.monthly_limit_usd = monthly_limit_usd
        self.tiers = tiers or list(DEFAULT_DEGRADATION_TIERS)
        self.current_tier: Optional[DegradationTier] = None
        self._alert_callback = None

    def set_alert_callback(self, callback):
        """Set a callback for budget alerts: callback(message, severity, details)."""
        self._alert_callback = callback

    def check(self, current_cost: float) -> Optional[DegradationTier]:
        """Check budget and return the active degradation tier (if any).

        Returns the newly activated tier if it changed, else None.
        """
        if self.monthly_limit_usd <= 0:
            return None

        usage_pct = (current_cost / self.monthly_limit_usd) * 100

        # Find highest applicable tier
        applicable_tier = None
        for tier in sorted(self.tiers, key=lambda t: t.threshold_pct, reverse=True):
            if usage_pct >= tier.threshold_pct:
                applicable_tier = tier
                break

        if applicable_tier != self.current_tier:
            old_tier = self.current_tier
            self.current_tier = applicable_tier

            if applicable_tier:
                severity = (
                    "critical" if applicable_tier.threshold_pct >= 95 else "warning"
                )
                logger.warning(
                    "Budget degradation tier changed: %s → %s (usage=%.1f%%)",
                    old_tier.action if old_tier else "none",
                    applicable_tier.action,
                    usage_pct,
                )
                if self._alert_callback:
                    self._alert_callback(
                        f"Budget degradation: {applicable_tier.action}",
                        severity,
                        {
                            "usage_pct": round(usage_pct, 1),
                            "tier": applicable_tier.action,
                            "description": applicable_tier.description,
                            "current_cost": round(current_cost, 2),
                            "limit": self.monthly_limit_usd,
                        },
                    )
            else:
                logger.info("Budget degradation cleared (usage=%.1f%%)", usage_pct)

            return applicable_tier

        return self.current_tier

    def get_routing_constraints(self) -> dict:
        """Get current routing constraints based on active tier.

        Returns a dict that can be applied to the ModelRouter:
          - max_model: maximum model tier allowed (or None)
          - force_model: force all requests to this model (or None)
        """
        if not self.current_tier:
            return {"max_model": None, "force_model": None}

        if self.current_tier.action == "alert":
            return {"max_model": None, "force_model": None}

        if self.current_tier.action == "reduce_premium":
            return {"max_model": "anthropic/claude-sonnet-4.5", "force_model": None}

        if self.current_tier.action == "reduce_frequency":
            return {"max_model": "anthropic/claude-sonnet-4.5", "force_model": None}

        if self.current_tier.action == "emergency_mode":
            return {"max_model": None, "force_model": "google/gemini-3.0-flash"}

        return {"max_model": None, "force_model": None}

    @property
    def usage_pct(self) -> float:
        """Return the threshold percentage of the current tier, or 0."""
        if self.current_tier:
            return float(self.current_tier.threshold_pct)
        return 0.0

    def to_dict(self) -> dict:
        """Serialize state for monitoring."""
        return {
            "monthly_limit_usd": self.monthly_limit_usd,
            "current_tier": self.current_tier.action if self.current_tier else None,
            "tier_threshold_pct": (
                self.current_tier.threshold_pct if self.current_tier else None
            ),
        }
