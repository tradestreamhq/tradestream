"""Validation phase — backtests strategy candidates and filters by quality metrics."""

import json

from absl import logging

from services.agent_orchestration import config
from services.shared.mcp_client import resolve_and_call

TOOL_TO_SERVER = {
    "run_backtest": "backtest",
    "get_walk_forward": "strategy",
    "get_spec": "strategy",
}


def _run_backtest(mcp_urls, strategy_name, symbol, period_days=90):
    """Run a single backtest via the backtest MCP server."""
    result = resolve_and_call(
        "run_backtest",
        {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "period_days": period_days,
        },
        TOOL_TO_SERVER,
        mcp_urls,
        return_type="parsed",
    )
    if isinstance(result, dict) and "error" in result:
        logging.warning("Backtest failed for %s on %s: %s", strategy_name, symbol, result["error"])
        return None
    return result


def _extract_metrics(backtest_result):
    """Extract key metrics from a backtest result dict."""
    if not backtest_result or not isinstance(backtest_result, dict):
        return None

    return {
        "sharpe_ratio": backtest_result.get("sharpe_ratio", 0.0),
        "win_rate": backtest_result.get("win_rate", 0.0),
        "max_drawdown": backtest_result.get("max_drawdown", 0.0),
        "cumulative_return": backtest_result.get("cumulative_return", 0.0),
        "total_trades": backtest_result.get("total_trades", 0),
        "profit_factor": backtest_result.get("profit_factor", 0.0),
        "sortino_ratio": backtest_result.get("sortino_ratio", 0.0),
    }


def _passes_minimum_criteria(metrics):
    """Check if metrics pass minimum quality thresholds."""
    if not metrics:
        return False

    if metrics["sharpe_ratio"] < config.MIN_SHARPE_RATIO:
        return False

    if metrics["win_rate"] < config.MIN_WIN_RATE:
        return False

    if metrics["max_drawdown"] < config.MAX_DRAWDOWN:
        return False

    if metrics["total_trades"] < 5:
        return False

    return True


def validate_candidates(candidate_names, mcp_urls):
    """Backtest all candidates across configured symbols, filter by quality.

    Args:
        candidate_names: List of strategy names to validate.
        mcp_urls: Dict of MCP server URLs.

    Returns:
        List of (name, aggregated_metrics) tuples for candidates that pass.
    """
    validated = []

    for name in candidate_names:
        logging.info("Validation: backtesting candidate %s", name)

        symbol_metrics = {}
        all_pass = True

        for symbol in config.BACKTEST_SYMBOLS:
            result = _run_backtest(mcp_urls, name, symbol)
            metrics = _extract_metrics(result)

            if not metrics:
                logging.warning("Validation: no metrics for %s on %s", name, symbol)
                all_pass = False
                break

            symbol_metrics[symbol] = metrics

            if not _passes_minimum_criteria(metrics):
                logging.info(
                    "Validation: %s failed criteria on %s (sharpe=%.2f, wr=%.2f, dd=%.2f)",
                    name, symbol,
                    metrics["sharpe_ratio"],
                    metrics["win_rate"],
                    metrics["max_drawdown"],
                )
                all_pass = False
                break

        if not all_pass or not symbol_metrics:
            logging.info("Validation: %s did not pass", name)
            continue

        # Aggregate metrics across symbols (average)
        agg = _aggregate_metrics(symbol_metrics)
        logging.info(
            "Validation: %s PASSED (avg sharpe=%.2f, avg wr=%.2f)",
            name, agg["sharpe_ratio"], agg["win_rate"],
        )
        validated.append((name, agg))

    # Sort by Sharpe ratio descending
    validated.sort(key=lambda x: x[1]["sharpe_ratio"], reverse=True)
    return validated


def _aggregate_metrics(symbol_metrics):
    """Average metrics across symbols."""
    if not symbol_metrics:
        return {}

    keys = ["sharpe_ratio", "win_rate", "max_drawdown", "cumulative_return",
            "profit_factor", "sortino_ratio"]
    n = len(symbol_metrics)
    agg = {}

    for key in keys:
        total = sum(m.get(key, 0.0) for m in symbol_metrics.values())
        agg[key] = total / n

    agg["total_trades"] = sum(
        m.get("total_trades", 0) for m in symbol_metrics.values()
    )
    agg["symbols_tested"] = list(symbol_metrics.keys())
    agg["per_symbol"] = symbol_metrics

    return agg
