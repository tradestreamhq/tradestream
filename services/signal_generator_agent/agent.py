"""Signal Generator Agent - generates BUY/SELL/HOLD signals per symbol."""

import json
import time
from datetime import datetime, timezone

from openai import OpenAI

SYSTEM_PROMPT = """You are a signal generator agent. You analyze market data, strategy signals, and recent signal history to emit BUY/SELL/HOLD trading signals.

You have access to MCP tools from three servers: strategy-mcp, market-mcp, and signal-mcp.

## Skills

### /analyze-consensus
Weigh the top 10 strategies for a symbol to compute consensus:
- Count how many strategies signal BUY, SELL, or HOLD
- Compute the average confidence across all strategies
- The consensus direction is the direction with the most agreement
- If there is a tie (e.g. 5 BUY vs 5 SELL), default to HOLD
- Output: consensus_direction, avg_confidence, agreement_count, total_count

### /read-market
Assess market conditions from candle data:
- Volume deviation: compare latest volume to 20-period average volume. Compute volume_ratio = latest_volume / avg_volume_20
- Volatility classification using ATR: compute ATR from candles, classify as "low" (ATR < 1% of price), "moderate" (1-3%), or "high" (> 3%)
- Momentum: look at last 5 candles' close prices. If trending up consistently = bullish, down = bearish, mixed = neutral
- Output: volume_ratio, volatility_class, momentum_direction

### /avoid-overfit
Check walk-forward validation status for each strategy:
- Call get_walk_forward for each strategy's impl_id
- If validation_status is "FAILED" or sharpe_degradation > 0.5, that strategy is overfitted
- Downweight overfitted strategies by multiplying their confidence by 0.5
- Flag which strategies were downweighted and why

### /format-signal
Format the final signal output:
- Output must be JSON: {"symbol": str, "action": "BUY"|"SELL"|"HOLD", "confidence": float 0-1, "reasoning": str, "strategy_breakdown": [{"strategy_type": str, "signal": str, "confidence": float}]}
- DEDUPLICATION: Before emitting, check get_recent_signals. If a signal with the same direction (action) for this symbol was emitted within the last 15 minutes, SKIP emission and respond with {"skipped": true, "reason": "duplicate signal within 15 minutes"}

## Workflow
1. Call get_top_strategies(symbol, limit=10) to get the top strategies
2. Call get_market_summary(symbol) and get_candles(symbol, limit=50) for market data
3. Call get_recent_signals(symbol, limit=5) to check for recent signals
4. Apply /analyze-consensus: weigh strategy agreement, compute avg confidence, count agreement
5. Apply /read-market: assess volume vs avg, momentum, volatility from candles
6. Apply /avoid-overfit: check walk_forward status, flag high sharpe_degradation
7. Apply /format-signal: deduplicate (skip if same direction signal within last 15 min)
8. If not skipped, call emit_signal(symbol, action, confidence, reasoning, strategy_breakdown)

Always respond with a single JSON object as your final answer. Do not include markdown formatting."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_top_strategies",
            "description": "Get top-performing strategies for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Currency pair (e.g., BTC-USD)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of strategies to return",
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
            "description": "Get a comprehensive market summary for a symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Currency pair (e.g., BTC-USD)",
                    },
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
                    "symbol": {
                        "type": "string",
                        "description": "Currency pair (e.g., BTC-USD)",
                    },
                    "timeframe": {
                        "type": "string",
                        "description": "Candle timeframe (e.g., 1m, 5m, 1h)",
                        "default": "1m",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of candles to return",
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
            "description": "Get recent signals, optionally filtered by symbol",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Filter by symbol",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of signals to return",
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
            "description": "Get walk-forward validation results for a strategy",
            "parameters": {
                "type": "object",
                "properties": {
                    "impl_id": {
                        "type": "string",
                        "description": "Strategy implementation UUID",
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
                    "symbol": {
                        "type": "string",
                        "description": "Currency pair",
                    },
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
                        "description": "Explanation of the signal",
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
                        "description": "Breakdown by strategy",
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

# Map tool names to MCP server URL config keys
TOOL_TO_MCP_SERVER = {
    "get_top_strategies": "strategy",
    "get_walk_forward": "strategy",
    "get_market_summary": "market",
    "get_candles": "market",
    "get_recent_signals": "signal",
    "emit_signal": "signal",
}


def _call_mcp_tool(tool_name, arguments, mcp_urls):
    """Call an MCP server tool via its HTTP endpoint."""
    import requests

    server_key = TOOL_TO_MCP_SERVER[tool_name]
    base_url = mcp_urls[server_key].rstrip("/")
    url = f"{base_url}/call-tool"

    payload = {
        "name": tool_name,
        "arguments": arguments,
    }

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()

    # MCP responses have a content array with text items
    if "content" in result:
        for item in result["content"]:
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except (json.JSONDecodeError, KeyError):
                    return item["text"]
    return result


def is_duplicate_signal(recent_signals, symbol, action):
    """Check if a signal with the same direction was emitted within 15 minutes.

    Args:
        recent_signals: List of recent signal dicts with 'timestamp' and 'action'
        symbol: Symbol to check
        action: Signal direction (BUY/SELL/HOLD)

    Returns:
        True if a duplicate signal exists within 15 minutes
    """
    if not recent_signals or not isinstance(recent_signals, list):
        return False

    now = datetime.now(timezone.utc)
    for sig in recent_signals:
        if sig.get("action") != action:
            continue
        if sig.get("symbol") != symbol:
            continue
        ts = sig.get("timestamp")
        if not ts:
            continue
        try:
            if isinstance(ts, str):
                sig_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                sig_time = ts
            if sig_time.tzinfo is None:
                sig_time = sig_time.replace(tzinfo=timezone.utc)
            age_minutes = (now - sig_time).total_seconds() / 60.0
            if age_minutes <= 15:
                return True
        except (ValueError, TypeError):
            continue
    return False


def compute_consensus(strategies):
    """Compute consensus direction and average confidence from strategies.

    Args:
        strategies: List of strategy dicts with 'signal' and 'confidence' keys

    Returns:
        Tuple of (direction, avg_confidence, agreement_count, total_count)
    """
    if not strategies:
        return "HOLD", 0.0, 0, 0

    counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
    total_confidence = 0.0

    for s in strategies:
        signal = s.get("signal", "HOLD").upper()
        if signal in counts:
            counts[signal] += 1
        total_confidence += s.get("confidence", 0.0)

    total = len(strategies)
    avg_confidence = total_confidence / total if total > 0 else 0.0

    max_count = max(counts.values())
    directions_with_max = [d for d, c in counts.items() if c == max_count]

    if len(directions_with_max) > 1:
        direction = "HOLD"
        agreement_count = counts["HOLD"]
    else:
        direction = directions_with_max[0]
        agreement_count = max_count

    return direction, avg_confidence, agreement_count, total


def generate_signal(symbol, api_key, mcp_urls):
    """Generate a trading signal for a symbol using the LLM agent loop.

    Args:
        symbol: Trading pair symbol (e.g., BTC-USD)
        api_key: OpenRouter API key
        mcp_urls: Dict with keys: strategy, market, signal

    Returns:
        Dict with signal result or None on failure
    """
    from absl import logging

    start_time = time.time()
    total_tokens = 0

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Generate a trading signal for {symbol}.\n\n"
                "Follow the workflow: get top strategies, get market data, "
                "check recent signals, analyze consensus, read market conditions, "
                "check for overfitting, format and emit the signal."
            ),
        },
    ]

    max_iterations = 20
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model="anthropic/claude-3-5-haiku",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message
        if response.usage:
            total_tokens += response.usage.total_tokens

        if message.tool_calls:
            messages.append(message)
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                logging.info("Tool call: %s(%s)", fn_name, json.dumps(fn_args))

                try:
                    result = _call_mcp_tool(fn_name, fn_args, mcp_urls)
                except Exception as e:
                    result = {"error": str(e)}
                    logging.error("MCP call failed: %s - %s", fn_name, e)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, default=str),
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
                    try:
                        result = json.loads(content[start:end])
                    except json.JSONDecodeError:
                        logging.warning(
                            "Could not parse result from response: %s",
                            content[:200],
                        )
                        return None
                else:
                    logging.warning(
                        "Could not parse result from response: %s",
                        content[:200],
                    )
                    return None

            logging.info(
                "Signal for %s: %s (confidence: %s, tokens: %d, latency: %dms)",
                symbol,
                result.get("action", result.get("skipped", "unknown")),
                result.get("confidence", "N/A"),
                total_tokens,
                latency_ms,
            )
            return result

    logging.warning("Agent reached max iterations for %s", symbol)
    return None
