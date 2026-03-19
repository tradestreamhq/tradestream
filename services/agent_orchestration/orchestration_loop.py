"""Main orchestration loop — continuous discovery -> backtest -> promote -> monitor cycle."""

import time

from absl import logging

from services.agent_orchestration import config
from services.agent_orchestration.discovery import run_discovery
from services.agent_orchestration.monitoring import monitor_promoted_strategies
from services.agent_orchestration.promotion import promote_winners
from services.agent_orchestration.state import OrchestrationState
from services.agent_orchestration.validation import validate_candidates


def run_cycle(api_key, mcp_urls, state):
    """Execute one complete orchestration cycle.

    Phases:
    1. Discovery: generate N new strategy candidates via LLM
    2. Validation: backtest candidates, filter by Sharpe/win-rate/drawdown
    3. Promotion: add top performers to signal pipeline
    4. Monitoring: check live strategies, adjust allocations, retire losers

    Args:
        api_key: LLM API key for discovery phase.
        mcp_urls: Dict of MCP server URLs.
        state: OrchestrationState instance.

    Returns:
        Dict with cycle summary stats.
    """
    state.cycle_number += 1
    cycle_num = state.cycle_number
    logging.info("=== Orchestration Cycle %d START ===", cycle_num)

    stats = {
        "discovered": 0,
        "validated": 0,
        "promoted": 0,
        "monitored_adjusted": 0,
        "monitored_retired": 0,
    }

    # Phase 1: Discovery
    logging.info("[Cycle %d] Phase 1: Discovery", cycle_num)
    try:
        discovered_names = run_discovery(api_key, mcp_urls)
        stats["discovered"] = len(discovered_names)
        for name in discovered_names:
            state.add_candidate(name, {"source": "discovery", "cycle": cycle_num})
        logging.info(
            "[Cycle %d] Discovered %d candidates", cycle_num, len(discovered_names)
        )
    except Exception as e:
        logging.error("[Cycle %d] Discovery failed: %s", cycle_num, e)
        discovered_names = []

    # Phase 2: Validation
    logging.info("[Cycle %d] Phase 2: Validation", cycle_num)
    try:
        validated = validate_candidates(discovered_names, mcp_urls)
        stats["validated"] = len(validated)
        for name, metrics in validated:
            state.advance_to_validation(name, metrics)
        logging.info("[Cycle %d] Validated %d candidates", cycle_num, len(validated))
    except Exception as e:
        logging.error("[Cycle %d] Validation failed: %s", cycle_num, e)
        validated = []

    # Phase 3: Promotion
    logging.info("[Cycle %d] Phase 3: Promotion", cycle_num)
    try:
        promoted = promote_winners(validated, state, mcp_urls)
        stats["promoted"] = len(promoted)
        logging.info("[Cycle %d] Promoted %d strategies", cycle_num, len(promoted))
    except Exception as e:
        logging.error("[Cycle %d] Promotion failed: %s", cycle_num, e)

    # Phase 4: Monitoring (all promoted strategies, not just this cycle's)
    logging.info("[Cycle %d] Phase 4: Monitoring", cycle_num)
    try:
        monitor_result = monitor_promoted_strategies(state, mcp_urls)
        stats["monitored_adjusted"] = len(monitor_result.get("adjusted", []))
        stats["monitored_retired"] = len(monitor_result.get("retired", []))
        logging.info(
            "[Cycle %d] Monitoring: %d adjusted, %d retired",
            cycle_num,
            stats["monitored_adjusted"],
            stats["monitored_retired"],
        )
    except Exception as e:
        logging.error("[Cycle %d] Monitoring failed: %s", cycle_num, e)

    # Record stats and persist
    state.last_cycle_time = time.time()
    state.record_cycle_stats(stats)
    state.save()

    logging.info(
        "=== Orchestration Cycle %d COMPLETE === "
        "discovered=%d, validated=%d, promoted=%d",
        cycle_num,
        stats["discovered"],
        stats["validated"],
        stats["promoted"],
    )
    return stats


def run_orchestration_loop(
    api_key,
    mcp_urls,
    state,
    cycle_interval_seconds=None,
    shutdown_check=None,
):
    """Run the continuous orchestration loop.

    Args:
        api_key: LLM API key.
        mcp_urls: Dict of MCP server URLs.
        state: OrchestrationState instance.
        cycle_interval_seconds: Seconds between cycles. Defaults to config value.
        shutdown_check: Callable returning True when shutdown is requested.
    """
    interval = cycle_interval_seconds or config.DEFAULT_CYCLE_INTERVAL_SECONDS
    shutdown_check = shutdown_check or (lambda: False)

    logging.info(
        "Orchestration loop starting (interval=%ds, state_file=%s)",
        interval,
        state.state_file,
    )
    state.load()

    while not shutdown_check():
        cycle_start = time.time()

        try:
            run_cycle(api_key, mcp_urls, state)
        except Exception as e:
            logging.error("Orchestration cycle failed: %s", e)
            state.save()

        # Sleep until next cycle
        elapsed = time.time() - cycle_start
        sleep_time = max(0, interval - elapsed)
        logging.info("Next cycle in %.0f seconds", sleep_time)

        sleep_until = time.time() + sleep_time
        while time.time() < sleep_until and not shutdown_check():
            time.sleep(1)

    logging.info("Orchestration loop stopped.")
    state.save()
