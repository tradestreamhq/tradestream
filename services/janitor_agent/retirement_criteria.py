"""Retirement criteria for strategy implementations and specs.

Evaluates implementations against configurable thresholds and protects
CANONICAL specs from retirement. Considers market regime, grace periods,
and requires better alternatives before recommending retirement.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SharpeTrend(Enum):
    DECLINING = "DECLINING"
    STABLE = "STABLE"
    IMPROVING = "IMPROVING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_vol"
    LOW_VOLATILITY = "low_vol"


@dataclass
class RetirementConfig:
    """Configurable thresholds for retirement decisions."""

    min_signals: int = 100
    min_age_days: int = 180
    max_sharpe: float = 0.5
    max_accuracy: float = 0.45
    required_trend: str = "DECLINING"
    require_better_alternative: bool = True
    min_alternative_sharpe: float = 1.0
    max_retirements_per_run: int = 50
    max_specs_per_run: int = 10
    max_retirement_percentage: float = 10.0
    grace_period_days: int = 180
    modification_grace_days: int = 30
    max_reactivation_attempts: int = 2
    reactivation_cooldown_days: int = 30


@dataclass
class Implementation:
    """Strategy implementation data for retirement evaluation."""

    impl_id: str
    spec_id: str
    symbol: str
    status: str
    forward_sharpe: float
    forward_accuracy: float
    forward_trades: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    sharpe_trend: str = "INSUFFICIENT_DATA"
    spec_source: str = ""
    spec_name: str = ""
    preferred_regime: Optional[str] = None

    @property
    def age_days(self) -> int:
        now = datetime.now(timezone.utc)
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (now - created).days

    @property
    def days_since_modification(self) -> Optional[int]:
        if not self.updated_at:
            return None
        now = datetime.now(timezone.utc)
        updated = self.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return (now - updated).days


@dataclass
class Spec:
    """Strategy spec data for retirement evaluation."""

    spec_id: str
    name: str
    source: str
    preferred_regime: Optional[str] = None


@dataclass
class RetirementDecision:
    """Result of a retirement evaluation."""

    should_retire: bool
    reason: str
    impl_id: str = ""
    spec_id: str = ""
    decision_type: str = "implementation"  # or "spec"
    final_sharpe: Optional[float] = None
    final_accuracy: Optional[float] = None
    age_days: Optional[int] = None
    signal_count: Optional[int] = None


def evaluate_implementation(
    impl: Implementation,
    config: RetirementConfig,
    better_alternative_exists: bool = False,
    current_regime: Optional[str] = None,
) -> RetirementDecision:
    """Evaluate whether an implementation should be retired.

    All criteria must be met for retirement. Returns a decision with reasoning.
    """
    base = dict(
        impl_id=impl.impl_id,
        spec_id=impl.spec_id,
        decision_type="implementation",
        final_sharpe=impl.forward_sharpe,
        final_accuracy=impl.forward_accuracy,
        age_days=impl.age_days,
        signal_count=impl.forward_trades,
    )

    # Protection: CANONICAL specs never retired
    if impl.spec_source == "CANONICAL":
        return RetirementDecision(
            should_retire=False,
            reason="CANONICAL spec protected from retirement",
            **base,
        )

    # Criterion 1: Enough data to judge
    if impl.forward_trades < config.min_signals:
        return RetirementDecision(
            should_retire=False,
            reason=f"Insufficient signals ({impl.forward_trades} < {config.min_signals})",
            **base,
        )

    if impl.age_days < config.min_age_days:
        return RetirementDecision(
            should_retire=False,
            reason=f"Too young ({impl.age_days}d < {config.min_age_days}d)",
            **base,
        )

    # Grace period for recently modified strategies
    if impl.days_since_modification is not None:
        if impl.days_since_modification < config.modification_grace_days:
            return RetirementDecision(
                should_retire=False,
                reason=f"Recently modified ({impl.days_since_modification}d ago, grace: {config.modification_grace_days}d)",
                **base,
            )

    # Criterion 2: Consistently poor performance
    if impl.forward_sharpe >= config.max_sharpe:
        return RetirementDecision(
            should_retire=False,
            reason=f"Sharpe acceptable ({impl.forward_sharpe:.2f} >= {config.max_sharpe})",
            **base,
        )

    if impl.forward_accuracy >= config.max_accuracy:
        return RetirementDecision(
            should_retire=False,
            reason=f"Accuracy acceptable ({impl.forward_accuracy:.0%} >= {config.max_accuracy:.0%})",
            **base,
        )

    # Criterion 3: Not improving
    if impl.sharpe_trend != config.required_trend:
        return RetirementDecision(
            should_retire=False,
            reason=f"Performance not {config.required_trend} ({impl.sharpe_trend})",
            **base,
        )

    # Criterion 4: Market regime consideration
    if impl.preferred_regime and current_regime:
        if impl.preferred_regime != current_regime:
            return RetirementDecision(
                should_retire=False,
                reason=f"Deferring: strategy prefers {impl.preferred_regime}, current regime is {current_regime}",
                **base,
            )

    # Criterion 5: Better alternatives exist
    if config.require_better_alternative and not better_alternative_exists:
        return RetirementDecision(
            should_retire=False,
            reason="No better alternatives available",
            **base,
        )

    # All criteria met
    reason = (
        f"Retired: Sharpe={impl.forward_sharpe:.2f}, "
        f"Accuracy={impl.forward_accuracy:.0%}, "
        f"Trend={impl.sharpe_trend}, "
        f"Age={impl.age_days}d, "
        f"Signals={impl.forward_trades}"
    )
    return RetirementDecision(should_retire=True, reason=reason, **base)


def evaluate_spec(
    spec: Spec,
    active_impl_count: int,
    total_impl_count: int,
) -> RetirementDecision:
    """Evaluate whether a spec should be retired.

    Only retires if ALL implementations are retired and spec is not CANONICAL.
    """
    base = dict(
        spec_id=spec.spec_id,
        decision_type="spec",
    )

    if spec.source == "CANONICAL":
        return RetirementDecision(
            should_retire=False,
            reason="CANONICAL specs protected from retirement",
            **base,
        )

    if total_impl_count == 0:
        return RetirementDecision(
            should_retire=False,
            reason="No implementations to evaluate",
            **base,
        )

    if active_impl_count > 0:
        return RetirementDecision(
            should_retire=False,
            reason=f"{active_impl_count} active implementations remain",
            **base,
        )

    return RetirementDecision(
        should_retire=True,
        reason=f"All {total_impl_count} implementations retired",
        **base,
    )


def can_reactivate(
    reactivation_count: int,
    days_since_retirement: int,
    can_reactivate_flag: bool,
    config: RetirementConfig,
) -> tuple[bool, str]:
    """Check if a retired implementation can be reactivated."""
    if not can_reactivate_flag:
        return False, "Implementation marked as non-reactivatable"

    if reactivation_count >= config.max_reactivation_attempts:
        return False, f"Maximum reactivation attempts ({config.max_reactivation_attempts}) exceeded"

    if days_since_retirement < config.reactivation_cooldown_days:
        remaining = config.reactivation_cooldown_days - days_since_retirement
        return False, f"Cooling off period: {remaining} days remaining"

    return True, "Eligible for reactivation"


def apply_batch_limits(
    candidates: list[RetirementDecision],
    total_active: int,
    config: RetirementConfig,
) -> tuple[list[RetirementDecision], list[RetirementDecision]]:
    """Apply batch limits to retirement candidates.

    Returns (approved, skipped) lists.
    """
    max_by_percentage = int(total_active * config.max_retirement_percentage / 100)
    effective_limit = min(config.max_retirements_per_run, max_by_percentage)
    effective_limit = max(effective_limit, 1)  # Always allow at least 1

    approved = []
    skipped = []

    for candidate in candidates:
        if not candidate.should_retire:
            continue
        if len(approved) >= effective_limit:
            skipped.append(
                RetirementDecision(
                    should_retire=False,
                    reason=f"Batch limit reached ({effective_limit})",
                    impl_id=candidate.impl_id,
                    spec_id=candidate.spec_id,
                    decision_type=candidate.decision_type,
                )
            )
        else:
            approved.append(candidate)

    return approved, skipped
