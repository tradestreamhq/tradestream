"""Main orchestrator loop - coordinates Signal Generator, Opportunity Scorer, and Strategy Proposer agents."""

import json
import time

import requests
from absl import logging

from services.orchestrator_agent import config
from services.orchestrator_agent.health_monitor import HealthMonitor
from services.orchestrator_agent.retry_handler import retry_with_backoff
from services.orchestrator_agent.scheduler import Scheduler

# MCP tool to server mapping (for fetching symbols)
TOOL_TO_SERVER = {
    "get_symbols": "market",
    "log_decision": "signal",
}


def _call_mcp_tool(tool_name, arguments, mcp_urls):
    """Call an MCP tool by dispatching to the correct MCP server via HTTP."""
    server_key = TOOL_TO_SERVER.get(tool_name)
    if not server_key:
        return {"error": f"Unknown tool: {tool_name}"}

    base_url = mcp_urls.get(server_key)
    if not base_url:
        return {"error": f"No URL configured for MCP server: {server_key}"}

    url = f"{base_url}/call-tool"
    payload = {"name": tool_name, "arguments": arguments or {}}

    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    if "content" in result and isinstance(result["content"], list):
        texts = [
            c.get("text", "") for c in result["content"] if c.get("type") == "text"
        ]
        combined = "\n".join(texts) if texts else json.dumps(result)
        try:
            return json.loads(combined)
        except (json.JSONDecodeError, TypeError):
            return {"raw": combined}
    return result


def fetch_active_symbols(mcp_urls):
    """Fetch active trading symbols from market-mcp."""
    result = _call_mcp_tool("get_symbols", {}, mcp_urls)
    if isinstance(result, dict) and "error" in result:
        raise ConnectionError(f"Failed to fetch symbols: {result['error']}")
    if isinstance(result, dict) and "symbols" in result:
        return result["symbols"]
    if isinstance(result, list):
        return result
    raise ValueError(f"Unexpected symbols response: {result}")


def _invoke_agent_http(agent_url, payload, timeout=120):
    """Invoke an agent service via HTTP POST.

    Each agent service exposes a /run endpoint that accepts a JSON payload
    and returns the agent's result.
    """
    resp = requests.post(f"{agent_url}/run", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _log_health_decision(mcp_urls, agent_name, status, details):
    """Log an orchestrator health decision to the agent_decisions table via signal-mcp."""
    try:
        _call_mcp_tool(
            "log_decision",
            {
                "signal_id": f"orchestrator-{agent_name}-{int(time.time())}",
                "score": 0,
                "tier": "SYSTEM",
                "reasoning": f"{agent_name}: {status} - {details}",
                "tool_calls": [],
                "model_used": "orchestrator",
                "latency_ms": 0,
                "tokens": 0,
            },
            mcp_urls,
        )
    except Exception as e:
        logging.warning("Failed to log health decision: %s", e)


def run_signal_pipeline(symbol, agent_urls, mcp_urls, health_monitor):
    """Run signal generation + opportunity scoring for a single symbol.

    1. Invoke Signal Generator for the symbol
    2. If a signal is produced, invoke Opportunity Scorer to score it
    """
    # Step 1: Signal Generator
    agent_name = config.AGENT_SIGNAL_GENERATOR
    if not health_monitor.is_healthy(agent_name):
        logging.warning(
            "%s: circuit breaker open, skipping symbol %s", agent_name, symbol
        )
        return

    start = time.time()
    try:
        signal_result = retry_with_backoff(
            lambda: _invoke_agent_http(
                agent_urls["signal_generator"],
                {"symbol": symbol},
            ),
            agent_name,
        )
        latency_ms = int((time.time() - start) * 1000)
        health_monitor.record_success(agent_name, latency_ms)
        logging.info("%s: signal for %s: %s", agent_name, symbol, signal_result)
    except Exception as e:
        health_monitor.record_failure(agent_name)
        _log_health_decision(mcp_urls, agent_name, "failure", str(e))
        logging.error("%s: failed for %s: %s", agent_name, symbol, e)
        return

    # Check if a signal was produced (not skipped)
    if not signal_result or signal_result.get("skipped"):
        logging.info("%s: no actionable signal for %s", agent_name, symbol)
        return

    # Step 2: Opportunity Scorer
    scorer_name = config.AGENT_OPPORTUNITY_SCORER
    if not health_monitor.is_healthy(scorer_name):
        logging.warning("%s: circuit breaker open, skipping scoring", scorer_name)
        return

    start = time.time()
    try:
        score_result = retry_with_backoff(
            lambda: _invoke_agent_http(
                agent_urls["opportunity_scorer"],
                {"signal": signal_result},
            ),
            scorer_name,
        )
        latency_ms = int((time.time() - start) * 1000)
        health_monitor.record_success(scorer_name, latency_ms)
        logging.info("%s: score for %s: %s", scorer_name, symbol, score_result)
    except Exception as e:
        health_monitor.record_failure(scorer_name)
        _log_health_decision(mcp_urls, scorer_name, "failure", str(e))
        logging.error("%s: failed for %s: %s", scorer_name, symbol, e)


def run_strategy_proposer(agent_urls, mcp_urls, health_monitor):
    """Run the Strategy Proposer agent to generate novel strategies."""
    agent_name = config.AGENT_STRATEGY_PROPOSER
    if not health_monitor.is_healthy(agent_name):
        logging.warning("%s: circuit breaker open, skipping", agent_name)
        return

    start = time.time()
    try:
        result = retry_with_backoff(
            lambda: _invoke_agent_http(
                agent_urls["strategy_proposer"],
                {},
                timeout=300,
            ),
            agent_name,
        )
        latency_ms = int((time.time() - start) * 1000)
        health_monitor.record_success(agent_name, latency_ms)
        logging.info("%s: result: %s", agent_name, result)
    except Exception as e:
        health_monitor.record_failure(agent_name)
        _log_health_decision(mcp_urls, agent_name, "failure", str(e))
        logging.error("%s: failed: %s", agent_name, e)


def run_orchestrator_loop(
    mcp_urls,
    agent_urls,
    scheduler,
    health_monitor,
    shutdown_check,
    fallback_symbols=None,
):
    """Main orchestrator loop.

    Args:
        mcp_urls: Dict with keys: strategy, market, signal -> base URLs.
        agent_urls: Dict with keys: signal_generator, opportunity_scorer,
                    strategy_proposer -> base URLs.
        scheduler: Scheduler instance.
        health_monitor: HealthMonitor instance.
        shutdown_check: Callable returning True when shutdown is requested.
        fallback_symbols: Symbols to use if fetching from market-mcp fails.
    """
    logging.info("Orchestrator loop starting.")

    while not shutdown_check():
        # Signal Generator + Opportunity Scorer pipeline
        if scheduler.should_run_signal_generator():
            try:
                symbols = fetch_active_symbols(mcp_urls)
            except Exception as e:
                logging.error("Failed to fetch symbols: %s", e)
                symbols = fallback_symbols or []

            for symbol in symbols:
                if shutdown_check():
                    break
                run_signal_pipeline(symbol, agent_urls, mcp_urls, health_monitor)

            scheduler.mark_signal_generator_run()

        # Strategy Proposer
        if scheduler.should_run_strategy_proposer():
            if not shutdown_check():
                run_strategy_proposer(agent_urls, mcp_urls, health_monitor)
            scheduler.mark_strategy_proposer_run()

        # Sleep until next task is due (check shutdown every second)
        wait = scheduler.seconds_until_next_task()
        sleep_until = time.time() + wait
        while time.time() < sleep_until and not shutdown_check():
            time.sleep(1)

    logging.info("Orchestrator loop stopped.")
