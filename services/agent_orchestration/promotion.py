"""Promotion phase — adds validated winners to the live signal pipeline."""

from absl import logging

from services.agent_orchestration import config
from services.shared.mcp_client import resolve_and_call

TOOL_TO_SERVER = {
    "emit_signal": "signal",
    "log_decision": "signal",
    "get_strategy_consensus": "strategy",
}


def promote_winners(validated_candidates, state, mcp_urls):
    """Promote top validated candidates to the live signal pipeline.

    Args:
        validated_candidates: List of (name, metrics) tuples, sorted by Sharpe.
        state: OrchestrationState instance.
        mcp_urls: Dict of MCP server URLs.

    Returns:
        List of promoted strategy names.
    """
    promoted = []
    max_promote = config.MAX_PROMOTED_PER_CYCLE

    for name, metrics in validated_candidates[:max_promote]:
        # Skip if already promoted
        existing = state.candidates.get(name)
        if existing and existing.phase == config.PHASE_PROMOTION:
            logging.info("Promotion: %s already promoted, skipping", name)
            continue

        allocation = config.INITIAL_ALLOCATION_WEIGHT

        # Record promotion in state
        state.advance_to_validation(name, metrics)
        state.promote(name, allocation)

        # Log the promotion decision
        _log_promotion_decision(mcp_urls, name, metrics, allocation)

        promoted.append(name)
        logging.info(
            "Promotion: %s promoted with allocation=%.2f (sharpe=%.2f)",
            name,
            allocation,
            metrics.get("sharpe_ratio", 0),
        )

    return promoted


def _log_promotion_decision(mcp_urls, name, metrics, allocation):
    """Log promotion decision via signal MCP."""
    try:
        resolve_and_call(
            "log_decision",
            {
                "signal_id": f"orchestration-promote-{name}",
                "score": metrics.get("sharpe_ratio", 0),
                "tier": "PROMOTION",
                "reasoning": (
                    f"Strategy {name} promoted to live pipeline. "
                    f"Sharpe={metrics.get('sharpe_ratio', 0):.2f}, "
                    f"WinRate={metrics.get('win_rate', 0):.2f}, "
                    f"Allocation={allocation:.2f}"
                ),
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
        logging.warning("Failed to log promotion decision for %s: %s", name, e)
