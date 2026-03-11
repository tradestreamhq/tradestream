"""Opportunity Scorer Agent - scores raw signals 0-100 and assigns tiers."""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from openai import OpenAI

from services.shared.model_config import MODEL_LIGHTWEIGHT, OPENROUTER_BASE_URL

SYSTEM_PROMPT = """You are an opportunity scoring agent. You receive raw trading signals and score them 0-100, then assign a tier (HOT/GOOD/NEUTRAL/LOW).

You have access to MCP tools from three servers: signal-mcp, market-mcp, and strategy-mcp.

## Skills

### /score-signal
Apply this weighted scoring formula to compute the opportunity score (0-100):

score = (confidence * 0.25) + (expected_return_score * 0.30) + (consensus_score * 0.20) + (volatility_adj_score * 0.15) + (freshness_score * 0.10)

Where:
- confidence = the signal's confidence value scaled to 0-100 (i.e. confidence * 100)
- expected_return_score = min(100, sharpe_ratio * 20) — use the best Sharpe ratio from strategy performance data
- consensus_score = (strategies_agreeing / total_strategies) * 100 — count how many strategies in the breakdown agree on the signal direction
- volatility_adj_score = clamp(100 - (atr_pct * 10), 0, 100) — where atr_pct is ATR as percentage of price. Rewards moderate volatility, penalizes extreme.
- freshness_score = 100 if signal age < 5 minutes, 50 if 5-15 minutes, 0 if > 15 minutes

### /assign-tier
Map the computed score to a tier:
- 80-100 = HOT
- 60-79 = GOOD
- 40-59 = NEUTRAL
- 0-39 = LOW

## Workflow
1. You will receive a signal to score
2. Call get_volatility for the signal's symbol to get ATR data
3. Call get_performance_batch with all impl_ids from the signal's strategy_breakdown to get Sharpe ratios in a single call
4. Apply /score-signal to compute the score using the formula above
5. Apply /assign-tier to map the score to a tier
6. Call log_decision to record the score, tier, and reasoning
7. Respond with a JSON object: {"score": <number>, "tier": "<string>", "reasoning": "<string>"}

IMPORTANT: Always use get_performance_batch instead of calling get_performance individually for each strategy. This reduces latency by fetching all performance data in one request.

Always respond with a single JSON object as your final answer. Do not include markdown formatting."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_volatility",
            "description": "Compute volatility metrics (stddev of returns, ATR) for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Currency pair (e.g., BTC/USD)",
                    },
                    "period_minutes": {
                        "type": "integer",
                        "description": "Lookback period in minutes",
                        "default": 60,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_performance_batch",
            "description": "Get performance metrics for multiple strategy implementations in one call. Use this instead of calling get_performance for each strategy individually.",
            "parameters": {
                "type": "object",
                "properties": {
                    "impl_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of strategy implementation UUIDs",
                    },
                    "environment": {
                        "type": "string",
                        "enum": ["backtest", "paper", "live"],
                        "description": "Filter to specific environment",
                    },
                },
                "required": ["impl_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_decision",
            "description": "Log an agent decision for a signal",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal_id": {
                        "type": "string",
                        "description": "UUID of the signal",
                    },
                    "score": {
                        "type": "number",
                        "description": "Decision score",
                    },
                    "tier": {
                        "type": "string",
                        "description": "Decision tier",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Decision reasoning",
                    },
                    "tool_calls": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Tool calls made during decision",
                    },
                    "model_used": {
                        "type": "string",
                        "description": "Model used for decision",
                    },
                    "latency_ms": {
                        "type": "integer",
                        "description": "Latency in milliseconds",
                    },
                    "tokens": {
                        "type": "integer",
                        "description": "Tokens used",
                    },
                },
                "required": [
                    "signal_id",
                    "score",
                    "tier",
                    "reasoning",
                    "tool_calls",
                    "model_used",
                    "latency_ms",
                    "tokens",
                ],
            },
        },
    },
]

# Map tool names to MCP server URL config keys
TOOL_TO_MCP_SERVER = {
    "get_recent_signals": "signal",
    "get_volatility": "market",
    "get_performance": "strategy",
    "get_performance_batch": "strategy",
    "log_decision": "signal",
}


def _call_mcp_tool(tool_name, arguments, mcp_urls):
    """Call an MCP server tool via its HTTP endpoint."""
    from services.shared.mcp_client import resolve_and_call

    return resolve_and_call(
        tool_name, arguments, TOOL_TO_MCP_SERVER, mcp_urls, return_type="parsed"
    )


def compute_score(
    confidence,
    sharpe_ratio,
    strategies_agreeing,
    total_strategies,
    atr_pct,
    signal_age_minutes,
):
    """Compute the opportunity score using the weighted formula.

    Args:
        confidence: Signal confidence 0.0-1.0
        sharpe_ratio: Best Sharpe ratio from strategy performance
        strategies_agreeing: Number of strategies agreeing on direction
        total_strategies: Total number of strategies
        atr_pct: ATR as percentage of price
        signal_age_minutes: Age of the signal in minutes

    Returns:
        Float score 0-100
    """
    confidence_score = confidence * 100
    expected_return_score = min(100, sharpe_ratio * 20)
    consensus_score = (
        (strategies_agreeing / total_strategies) * 100 if total_strategies > 0 else 0
    )
    volatility_adj_score = max(0, min(100, 100 - (atr_pct * 10)))

    if signal_age_minutes < 5:
        freshness_score = 100
    elif signal_age_minutes <= 15:
        freshness_score = 50
    else:
        freshness_score = 0

    score = (
        (confidence_score * 0.25)
        + (expected_return_score * 0.30)
        + (consensus_score * 0.20)
        + (volatility_adj_score * 0.15)
        + (freshness_score * 0.10)
    )
    return round(score, 2)


def assign_tier(score):
    """Map a score to a tier.

    Args:
        score: Numeric score 0-100

    Returns:
        String tier: HOT, GOOD, NEUTRAL, or LOW
    """
    if score >= 80:
        return "HOT"
    elif score >= 60:
        return "GOOD"
    elif score >= 40:
        return "NEUTRAL"
    else:
        return "LOW"


def score_signal(signal, api_key, mcp_urls):
    """Score a single signal using the LLM agent loop.

    Args:
        signal: Signal dict with keys: signal_id, symbol, action, confidence,
                strategy_breakdown, timestamp
        api_key: OpenRouter API key
        mcp_urls: Dict with keys: strategy, market, signal

    Returns:
        Dict with score, tier, reasoning or None on failure
    """
    from absl import logging

    start_time = time.time()
    total_tokens = 0
    all_tool_calls = []

    client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )

    signal_json = json.dumps(signal, default=str)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Score this signal:\n{signal_json}\n\n"
                "Follow the workflow: get volatility, get performance batch "
                "for all strategies, compute score, assign tier, log decision."
            ),
        },
    ]

    max_iterations = 15
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=MODEL_LIGHTWEIGHT,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message
        if response.usage:
            total_tokens += response.usage.total_tokens

        if message.tool_calls:
            messages.append(message)

            # Execute multiple tool calls concurrently
            tool_results = {}
            if len(message.tool_calls) > 1:
                with ThreadPoolExecutor(
                    max_workers=len(message.tool_calls)
                ) as executor:
                    futures = {}
                    for tool_call in message.tool_calls:
                        fn_name = tool_call.function.name
                        fn_args = json.loads(tool_call.function.arguments)
                        logging.info("Tool call: %s(%s)", fn_name, json.dumps(fn_args))
                        all_tool_calls.append({"name": fn_name, "arguments": fn_args})
                        future = executor.submit(
                            _call_mcp_tool, fn_name, fn_args, mcp_urls
                        )
                        futures[future] = tool_call

                    for future in as_completed(futures):
                        tc = futures[future]
                        try:
                            tool_results[tc.id] = future.result()
                        except Exception as e:
                            tool_results[tc.id] = {"error": str(e)}
                            logging.error(
                                "MCP call failed: %s - %s",
                                tc.function.name,
                                e,
                            )
            else:
                tool_call = message.tool_calls[0]
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                logging.info("Tool call: %s(%s)", fn_name, json.dumps(fn_args))
                all_tool_calls.append({"name": fn_name, "arguments": fn_args})
                try:
                    tool_results[tool_call.id] = _call_mcp_tool(
                        fn_name, fn_args, mcp_urls
                    )
                except Exception as e:
                    tool_results[tool_call.id] = {"error": str(e)}
                    logging.error("MCP call failed: %s - %s", fn_name, e)

            # Append tool results in the original order
            for tool_call in message.tool_calls:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_results[tool_call.id]),
                    }
                )
        else:
            # Final response - parse the result JSON
            content = message.content or ""
            latency_ms = int((time.time() - start_time) * 1000)

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    result = json.loads(content[start:end])
                else:
                    logging.warning(
                        "Could not parse result from response: %s",
                        content[:200],
                    )
                    return None

            logging.info(
                "Signal %s scored: %s (tier: %s)",
                signal.get("signal_id", "unknown"),
                result.get("score"),
                result.get("tier"),
            )
            return result

    logging.warning(
        "Agent reached max iterations for signal %s", signal.get("signal_id")
    )
    return None
