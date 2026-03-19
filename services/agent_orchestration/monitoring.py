"""Monitoring phase — tracks live performance, adjusts allocations, retires losers."""

from absl import logging

from services.agent_orchestration import config
from services.shared.mcp_client import resolve_and_call

TOOL_TO_SERVER = {
    "get_performance": "strategy",
    "get_signal_accuracy": "signal",
    "log_decision": "signal",
}


def monitor_promoted_strategies(state, mcp_urls):
    """Check live performance of promoted strategies and adjust allocations.

    - Winners (high Sharpe): increase allocation up to MAX_ALLOCATION_WEIGHT
    - Losers (low Sharpe): decrease allocation
    - Failures (negative Sharpe for RETIREMENT_LOOKBACK_DAYS): retire

    Args:
        state: OrchestrationState instance.
        mcp_urls: Dict of MCP server URLs.

    Returns:
        Dict with monitoring results: {adjusted: [...], retired: [...]}.
    """
    promoted = state.get_promoted_strategies()
    if not promoted:
        logging.info("Monitoring: no promoted strategies to monitor")
        return {"adjusted": [], "retired": []}

    adjusted = []
    retired = []

    for candidate in promoted:
        name = candidate.name
        logging.info("Monitoring: checking %s", name)

        live_metrics = _get_live_metrics(mcp_urls, name)
        if not live_metrics:
            logging.warning("Monitoring: no live metrics for %s", name)
            continue

        current_sharpe = live_metrics.get("sharpe_ratio", 0.0)
        old_allocation = candidate.allocation_weight

        # Retirement check
        if current_sharpe < config.RETIREMENT_SHARPE_THRESHOLD:
            logging.info(
                "Monitoring: retiring %s (sharpe=%.2f < threshold=%.2f)",
                name, current_sharpe, config.RETIREMENT_SHARPE_THRESHOLD,
            )
            state.retire(name, reason=f"sharpe={current_sharpe:.2f}")
            _log_monitoring_decision(
                mcp_urls, name, "RETIRED",
                f"Sharpe {current_sharpe:.2f} below threshold",
            )
            retired.append(name)
            continue

        # Allocation adjustment
        new_allocation = old_allocation
        if current_sharpe >= config.ALLOCATION_INCREASE_THRESHOLD:
            new_allocation = min(
                old_allocation * 1.25,
                config.MAX_ALLOCATION_WEIGHT,
            )
        elif current_sharpe <= config.ALLOCATION_DECREASE_THRESHOLD:
            new_allocation = max(old_allocation * 0.75, 0.01)

        if abs(new_allocation - old_allocation) > 0.001:
            candidate.allocation_weight = new_allocation
            adjusted.append({
                "name": name,
                "old_allocation": old_allocation,
                "new_allocation": new_allocation,
                "sharpe": current_sharpe,
            })
            logging.info(
                "Monitoring: %s allocation %.2f -> %.2f (sharpe=%.2f)",
                name, old_allocation, new_allocation, current_sharpe,
            )

        # Update stored metrics
        candidate.metrics.update(live_metrics)

    return {"adjusted": adjusted, "retired": retired}


def _get_live_metrics(mcp_urls, strategy_name):
    """Get live performance metrics for a strategy."""
    try:
        result = resolve_and_call(
            "get_signal_accuracy",
            {
                "strategy_name": strategy_name,
                "lookback_days": config.PERFORMANCE_LOOKBACK_DAYS,
            },
            TOOL_TO_SERVER,
            mcp_urls,
            return_type="parsed",
        )
        if isinstance(result, dict) and "error" not in result:
            return result
    except Exception as e:
        logging.warning("Failed to get live metrics for %s: %s", strategy_name, e)

    return None


def _log_monitoring_decision(mcp_urls, name, action, reason):
    """Log a monitoring decision."""
    try:
        resolve_and_call(
            "log_decision",
            {
                "signal_id": f"orchestration-monitor-{name}",
                "score": 0,
                "tier": "MONITORING",
                "reasoning": f"{action}: {name} - {reason}",
                "tool_calls": [],
                "model_used": "orchestration_agent",
                "latency_ms": 0,
                "tokens": 0,
            },
            TOOL_TO_SERVER,
            mcp_urls,
            return_type="parsed",
        )
    except Exception as e:
        logging.warning("Failed to log monitoring decision for %s: %s", name, e)
