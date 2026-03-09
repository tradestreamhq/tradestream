"""Signal Generator Agent - produces BUY/SELL/HOLD signals via LLM + MCP tools."""

import json
import time
from datetime import datetime, timezone

from absl import logging
from openai import OpenAI


SYSTEM_PROMPT = """You are a trading signal generator agent. You analyze market data, strategy signals, and recent signals to produce BUY, SELL, or HOLD recommendations.

You have access to MCP tools from three servers. Follow this exact workflow:

1. Call get_top_strategies(symbol, limit=10) to get the best-performing strategies
2. Call get_market_summary(symbol) and get_candles(symbol, limit=50) for current market state
3. Call get_recent_signals(symbol, limit=5) to check what signals were recently emitted
4. Analyze all data using the skills below
5. Call emit_signal(symbol, action, confidence, reasoning, strategy_breakdown) with the final signal

## Skill: /analyze-consensus
Weigh the top 10 strategies to compute a consensus direction and average confidence:
- Count how many strategies signal BUY, SELL, or HOLD
- Compute average confidence across all strategies
- The consensus direction is the one with the most agreement
- If BUY and SELL are tied, default to HOLD
- Record each strategy's contribution in strategy_breakdown

## Skill: /read-market
Assess market conditions from candle data:
- Volume deviation: compare latest volume to the 20-period average volume. Flag if >1.5x or <0.5x.
- Volatility classification using ATR (Average True Range) of last 14 candles:
  - low: ATR < 0.5% of price
  - moderate: ATR 0.5%-1.5% of price
  - high: ATR > 1.5% of price
- Momentum: compute price change over the last 5 candles as a percentage. Positive = bullish, negative = bearish.

## Skill: /avoid-overfit
For each strategy, check its walk-forward validation:
- If walk_forward validation_status is "FAILED", downweight that strategy's confidence by 0.5x
- If sharpe_degradation > 0.5, downweight that strategy's confidence by 0.5x
- This affects consensus computation - apply before computing averages

## Skill: /format-signal
Format the final output as JSON:
{
  "symbol": "<symbol>",
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation>",
  "strategy_breakdown": [{"strategy_type": "<type>", "signal": "<direction>", "confidence": <value>}]
}

Deduplication rule: If any of the recent signals (from get_recent_signals) has the SAME direction/action
and was emitted within the last 15 minutes, do NOT call emit_signal. Instead, respond with
{"skipped": true, "reason": "duplicate signal within 15 minutes"}.

IMPORTANT: Always call the tools in order. Always produce a final signal or skip decision.
"""

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_top_strategies",
            "description": "Get top-performing strategies for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol"},
                    "limit": {
                        "type": "integer",
                        "description": "Max strategies to return",
                        "default": 10,
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum score threshold",
                        "default": 0.0,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_summary",
            "description": "Get market summary for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_candles",
            "description": "Get OHLCV candle data for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol"},
                    "timeframe": {
                        "type": "string",
                        "description": "Candle timeframe",
                        "default": "1m",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of candles",
                        "default": 100,
                    },
                },
                "required": ["symbol"],
            },
        },
    },
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
            "name": "get_walk_forward",
            "description": "Get walk-forward validation results for a strategy implementation",
            "parameters": {
                "type": "object",
                "properties": {
                    "impl_id": {
                        "type": "string",
                        "description": "Strategy implementation ID",
                    },
                },
                "required": ["impl_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "emit_signal",
            "description": "Emit a trading signal",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading symbol"},
                    "action": {
                        "type": "string",
                        "enum": ["BUY", "SELL", "HOLD"],
                        "description": "Signal action",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score 0.0-1.0",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Explanation for the signal",
                    },
                    "strategy_breakdown": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "strategy_type": {"type": "string"},
                                "signal": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                        },
                        "description": "Per-strategy signal breakdown",
                    },
                },
                "required": [
                    "symbol",
                    "action",
                    "confidence",
                    "reasoning",
                    "strategy_breakdown",
                ],
            },
        },
    },
]

# Map tool names to their MCP server URLs
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


def run_agent_for_symbol(symbol, api_key, mcp_urls):
    """Run the signal generator agent for a single symbol.

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
            "content": f"Generate a trading signal for {symbol}. Follow the workflow exactly.",
        },
    ]

    max_iterations = 15
    for iteration in range(max_iterations):
        logging.info("Symbol %s: LLM iteration %d", symbol, iteration + 1)

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
                "Symbol %s: agent finished after %d iterations", symbol, iteration + 1
            )
            return message.content

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            logging.info("Symbol %s: calling tool %s(%s)", symbol, fn_name, fn_args)

            result = _call_mcp_tool(fn_name, fn_args, mcp_urls)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    logging.warning("Symbol %s: reached max iterations (%d)", symbol, max_iterations)
    return None
