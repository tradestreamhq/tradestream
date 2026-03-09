"""Opportunity Scorer Agent - scores raw signals 0-100 and assigns tiers."""

import json
import time
from datetime import datetime, timezone

from absl import logging
from openai import OpenAI


SYSTEM_PROMPT = """You are an opportunity scoring agent. You receive raw trading signals and score them 0-100, then assign a tier.

You have access to MCP tools from three servers. Follow this exact workflow:

1. Call get_recent_signals(limit=1) to get the most recent unscored signal
2. Call get_volatility(symbol) for the signal's symbol
3. Call get_performance(impl_id) for each strategy in the signal's strategy_breakdown
4. Apply the /score-signal skill to compute a weighted score
5. Apply the /assign-tier skill to map the score to a tier
6. Call log_decision(signal_id, score, tier, reasoning, tool_calls, model_used, latency_ms, tokens)

## Skill: /score-signal
Compute the opportunity score using this weighted formula:

score = (confidence * 0.25) + (expected_return_score * 0.30) + (consensus_score * 0.20) + (volatility_adj_score * 0.15) + (freshness_score * 0.10)

Where:
- confidence = the signal's confidence value scaled to 0-100 (multiply by 100)
- expected_return_score = min(100, sharpe_ratio * 20). Use the average sharpe_ratio from get_performance results.
- consensus_score = (strategies_agreeing / total_strategies) * 100. Count strategies whose signal matches the overall signal action.
- volatility_adj_score = max(0, min(100, 100 - (atr_pct * 10))). atr_pct is ATR as percentage of price from get_volatility. Rewards moderate volatility, penalizes extreme.
- freshness_score = 100 if signal is < 5 minutes old, 50 if 5-15 minutes old, 0 if > 15 minutes old. Use signal's created_at timestamp.

## Skill: /assign-tier
Map the computed score to a tier:
- 80-100 = HOT
- 60-79 = GOOD
- 40-59 = NEUTRAL
- 0-39 = LOW

After computing the score and tier, provide clear reasoning explaining:
- The breakdown of each component score
- Which strategies agreed/disagreed
- How volatility affected the score
- The final tier assignment

Then call log_decision with the results.

IMPORTANT: If get_recent_signals returns an empty list or no unscored signals, respond with {"skipped": true, "reason": "no unscored signals available"}.
IMPORTANT: Always call the tools in order. Always produce a final decision or skip.
"""

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_recent_signals",
            "description": "Get recently emitted signals",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol"},
                    "limit": {
                        "type": "integer",
                        "description": "Max signals to return",
                        "default": 20,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_volatility",
            "description": "Compute volatility metrics (stddev of returns, ATR) for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol"},
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
            "name": "get_performance",
            "description": "Get performance metrics for a strategy implementation",
            "parameters": {
                "type": "object",
                "properties": {
                    "impl_id": {
                        "type": "string",
                        "description": "Strategy implementation UUID",
                    },
                    "environment": {
                        "type": "string",
                        "description": "Filter to specific environment",
                        "enum": ["backtest", "paper", "live"],
                    },
                },
                "required": ["impl_id"],
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
                    "score": {"type": "number", "description": "Decision score"},
                    "tier": {"type": "string", "description": "Decision tier"},
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

TOOL_TO_SERVER = {
    "get_top_strategies": "strategy",
    "get_spec": "strategy",
    "get_performance": "strategy",
    "list_strategy_types": "strategy",
    "get_walk_forward": "strategy",
    "get_candles": "market",
    "get_latest_price": "market",
    "get_volatility": "market",
    "get_symbols": "market",
    "get_market_summary": "market",
    "emit_signal": "signal",
    "log_decision": "signal",
    "get_recent_signals": "signal",
    "get_paper_pnl": "signal",
    "get_signal_accuracy": "signal",
}


def _call_mcp_tool(tool_name, arguments, mcp_urls):
    """Call an MCP tool by dispatching to the correct MCP server via HTTP."""
    import requests

    server_key = TOOL_TO_SERVER.get(tool_name)
    if not server_key:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    base_url = mcp_urls.get(server_key)
    if not base_url:
        return json.dumps({"error": f"No URL configured for MCP server: {server_key}"})

    url = f"{base_url}/call-tool"
    payload = {"name": tool_name, "arguments": arguments or {}}

    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if "content" in result and isinstance(result["content"], list):
            texts = [
                c.get("text", "") for c in result["content"] if c.get("type") == "text"
            ]
            return "\n".join(texts) if texts else json.dumps(result)
        return json.dumps(result)
    except requests.RequestException as e:
        logging.error("MCP call %s failed: %s", tool_name, e)
        return json.dumps({"error": str(e)})


def compute_score(confidence, sharpe_ratio, strategies_agreeing, total_strategies,
                  atr_pct, signal_age_minutes):
    """Compute the opportunity score using the weighted formula.

    Args:
        confidence: Signal confidence 0.0-1.0.
        sharpe_ratio: Average Sharpe ratio from strategy performance.
        strategies_agreeing: Number of strategies agreeing with signal direction.
        total_strategies: Total number of strategies in breakdown.
        atr_pct: ATR as percentage of price.
        signal_age_minutes: Age of the signal in minutes.

    Returns:
        Float score 0-100.
    """
    confidence_score = confidence * 100
    expected_return_score = min(100, sharpe_ratio * 20)
    consensus_score = (strategies_agreeing / total_strategies * 100) if total_strategies > 0 else 0
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

    return max(0, min(100, score))


def assign_tier(score):
    """Map a score to a tier.

    Args:
        score: Numeric score 0-100.

    Returns:
        Tier string: HOT, GOOD, NEUTRAL, or LOW.
    """
    if score >= 80:
        return "HOT"
    elif score >= 60:
        return "GOOD"
    elif score >= 40:
        return "NEUTRAL"
    else:
        return "LOW"


def run_scorer(api_key, mcp_urls):
    """Run the opportunity scorer agent for one cycle.

    Returns the final assistant message content.
    """
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "Score the most recent unscored signal. Follow the workflow exactly.",
        },
    ]

    max_iterations = 15
    for iteration in range(max_iterations):
        logging.info("Scorer: LLM iteration %d", iteration + 1)

        response = client.chat.completions.create(
            model="anthropic/claude-3-5-haiku",
            messages=messages,
            tools=MCP_TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message

        messages.append(message.model_dump(exclude_none=True))

        if choice.finish_reason == "stop" or not message.tool_calls:
            logging.info(
                "Scorer: agent finished after %d iterations", iteration + 1
            )
            return message.content

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            logging.info("Scorer: calling tool %s(%s)", fn_name, fn_args)

            result = _call_mcp_tool(fn_name, fn_args, mcp_urls)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    logging.warning("Scorer: reached max iterations (%d)", max_iterations)
    return None
