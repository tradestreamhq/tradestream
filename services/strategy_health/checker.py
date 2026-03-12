"""Strategy health checker — evaluates performance metrics and flags degradation."""

from typing import Optional

from services.strategy_health.models import (
    HealthState,
    MetricSnapshot,
    StrategyHealthReport,
)

# Thresholds
SHARPE_DROP_THRESHOLD = 0.30  # 30% drop from 90d avg triggers degrading
DRAWDOWN_CRITICAL_MULTIPLIER = 2.0  # 2x historical max triggers critical
WIN_RATE_DROP_THRESHOLD = 0.15  # 15pp drop triggers degrading
SHARPE_CRITICAL_THRESHOLD = 0.50  # 50% drop from 90d avg triggers critical


def evaluate_health(
    strategy_id: str,
    metrics: MetricSnapshot,
    checked_at: str,
    previous_state: Optional[HealthState] = None,
) -> StrategyHealthReport:
    """Evaluate strategy health based on current metrics.

    Transition rules:
    - degrading: Sharpe drops >30% from 90d avg, OR win rate drops >15pp
    - critical: drawdown >2x historical max, OR Sharpe drops >50% from 90d avg
    - disabled: only set externally (not by the checker)
    - healthy: none of the above conditions met
    """
    if previous_state == HealthState.DISABLED:
        return StrategyHealthReport(
            strategy_id=strategy_id,
            state=HealthState.DISABLED,
            metrics=metrics,
            reasons=["Strategy is disabled"],
            checked_at=checked_at,
        )

    reasons: list[str] = []
    is_critical = False
    is_degrading = False

    # Check drawdown against historical max
    if (
        metrics.drawdown_depth is not None
        and metrics.historical_max_drawdown is not None
        and metrics.historical_max_drawdown > 0
    ):
        ratio = metrics.drawdown_depth / metrics.historical_max_drawdown
        if ratio >= DRAWDOWN_CRITICAL_MULTIPLIER:
            is_critical = True
            reasons.append(
                f"Drawdown {metrics.drawdown_depth:.2%} exceeds "
                f"{DRAWDOWN_CRITICAL_MULTIPLIER}x historical max "
                f"({metrics.historical_max_drawdown:.2%})"
            )

    # Check Sharpe ratio degradation
    if (
        metrics.rolling_sharpe is not None
        and metrics.sharpe_90d_avg is not None
        and metrics.sharpe_90d_avg > 0
    ):
        drop_pct = 1 - (metrics.rolling_sharpe / metrics.sharpe_90d_avg)
        if drop_pct >= SHARPE_CRITICAL_THRESHOLD:
            is_critical = True
            reasons.append(
                f"Sharpe ratio dropped {drop_pct:.0%} from 90d average "
                f"({metrics.rolling_sharpe:.2f} vs {metrics.sharpe_90d_avg:.2f})"
            )
        elif drop_pct >= SHARPE_DROP_THRESHOLD:
            is_degrading = True
            reasons.append(
                f"Sharpe ratio dropped {drop_pct:.0%} from 90d average "
                f"({metrics.rolling_sharpe:.2f} vs {metrics.sharpe_90d_avg:.2f})"
            )

    # Check win rate trend
    if metrics.win_rate_trend is not None and metrics.win_rate_trend < -WIN_RATE_DROP_THRESHOLD:
        is_degrading = True
        reasons.append(
            f"Win rate declining: {metrics.win_rate_trend:+.2%} over trailing period"
        )

    if is_critical:
        state = HealthState.CRITICAL
    elif is_degrading:
        state = HealthState.DEGRADING
    else:
        state = HealthState.HEALTHY
        if not reasons:
            reasons.append("All metrics within normal ranges")

    return StrategyHealthReport(
        strategy_id=strategy_id,
        state=state,
        metrics=metrics,
        reasons=reasons,
        checked_at=checked_at,
    )
