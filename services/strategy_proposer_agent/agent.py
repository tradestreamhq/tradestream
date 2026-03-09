"""Strategy Proposer Agent - proposes novel trading strategies via LLM + MCP tools."""

import json

from absl import logging
from openai import OpenAI


SYSTEM_PROMPT = """You are a strategy proposer agent. You analyze the existing strategy universe to identify gaps and propose novel trading strategies.

You have access to MCP tools from a strategy server. Follow this exact workflow:

1. Call list_strategy_types() to see all existing strategy types
2. Call get_top_strategies(symbol="BTC/USD", limit=5) to see top 5 performers by Sharpe
3. Call get_top_strategies(symbol="BTC/USD", limit=100, min_score=-100) and pick the bottom 5 to understand what fails
4. Apply /indicator-catalog to review available indicators
5. Apply /gap-analysis to reason about untried combinations
6. Apply /generate-spec to produce a valid strategy spec JSON
7. Apply /novelty-check to confirm uniqueness
8. Call create_spec(name, indicators, entry_conditions, exit_conditions, parameters, description) to register the new strategy

## Skill: /indicator-catalog
Available TA4J indicators with valid parameter ranges:
- EMA(period: 5-200) — Exponential Moving Average. Reacts faster to recent prices than SMA.
- SMA(period: 5-200) — Simple Moving Average. Equal weight to all prices in the window.
- RSI(period: 7-21) — Relative Strength Index. Measures momentum; >70 overbought, <30 oversold.
- MACD(fast: 8-15, slow: 20-30, signal: 7-11) — Moving Average Convergence Divergence. Trend-following momentum indicator.
- BollingerBands(period: 10-30, stdDev: 1.5-2.5) — Volatility bands around a moving average. Price touching bands signals potential reversal.
- ATR(period: 7-21) — Average True Range. Measures volatility for position sizing and stop placement.
- Stochastic(kPeriod: 5-21, dPeriod: 3-7) — Stochastic Oscillator. Compares closing price to price range.
- ADX(period: 7-21) — Average Directional Index. Measures trend strength (not direction). >25 = trending.
- OBV — On-Balance Volume. Cumulative volume flow to confirm price trends.
- VWAP — Volume Weighted Average Price. Institutional benchmark; price above = bullish bias.
- CCI(period: 10-30) — Commodity Channel Index. Identifies cyclical turns; >100 overbought, <-100 oversold.
- Williams%R(period: 7-21) — Williams Percent Range. Similar to Stochastic but inverted scale.

## Skill: /gap-analysis
Reason about gaps in the strategy universe:
- What indicator combinations are NOT covered by existing strategies?
- Which market regimes (trending, ranging, volatile, calm) lack dedicated strategies?
- Are there cross-category combinations (e.g., momentum + volume, volatility + trend) not tried?
- What parameter ranges are underexplored?
- Consider: mean-reversion strategies for ranging markets, breakout strategies using volume confirmation,
  multi-timeframe approaches, volatility-adaptive strategies using ATR or BollingerBands.

## Skill: /generate-spec
Output MUST be valid JSON matching the strategy_specs schema:
{
  "name": "string — unique, descriptive, snake_case",
  "indicators": {"indicator_name": {"param": value, ...}, ...},
  "entry_conditions": {"condition_name": "condition expression string", ...},
  "exit_conditions": {"condition_name": "condition expression string", ...},
  "parameters": {"param_name": value, ...},
  "description": "string — human-readable description of the strategy logic"
}

Rules:
- name must be unique and descriptive (e.g., "ema_rsi_crossover_with_volume")
- indicators must only use indicators from /indicator-catalog with params in valid ranges
- entry_conditions and exit_conditions must reference the declared indicators
- parameters should include tunable values like thresholds, periods, etc.
- description should explain the strategy logic in plain English

## Skill: /novelty-check
Before submitting, verify novelty:
- Compare the proposed spec name against the list from list_strategy_types()
- Compare the indicator combination against existing strategies
- If >70% of indicators overlap with any single existing strategy, REJECT and try a different combination
- Only propose strategies that bring genuinely new indicator combinations or market regime coverage

IMPORTANT:
- Always call the tools in order
- Always produce exactly ONE new strategy spec per run
- Use structured reasoning before generating the spec
- If you cannot find a novel combination, explain why and do NOT call create_spec
"""

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_strategy_types",
            "description": "List distinct strategy types with validated or deployed implementations",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_strategies",
            "description": "Get top-performing strategies by Sharpe ratio for a symbol",
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
                        "description": "Minimum Sharpe ratio",
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
            "name": "create_spec",
            "description": "Create a new strategy specification",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique spec name"},
                    "indicators": {
                        "type": "object",
                        "description": "Indicator configurations",
                    },
                    "entry_conditions": {
                        "type": "object",
                        "description": "Entry rule definitions",
                    },
                    "exit_conditions": {
                        "type": "object",
                        "description": "Exit rule definitions",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Parameter definitions with ranges",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description",
                    },
                },
                "required": [
                    "name",
                    "indicators",
                    "entry_conditions",
                    "exit_conditions",
                    "parameters",
                    "description",
                ],
            },
        },
    },
]

TOOL_TO_SERVER = {
    "list_strategy_types": "strategy",
    "get_top_strategies": "strategy",
    "get_spec": "strategy",
    "get_performance": "strategy",
    "create_spec": "strategy",
    "get_walk_forward": "strategy",
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


def run_proposer(api_key, mcp_urls):
    """Run the strategy proposer agent.

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
            "content": (
                "Propose a novel trading strategy. Follow the workflow exactly: "
                "list existing strategies, analyze performance, identify gaps, "
                "generate a spec, check novelty, and create the spec."
            ),
        },
    ]

    max_iterations = 15
    for iteration in range(max_iterations):
        logging.info("Strategy proposer: LLM iteration %d", iteration + 1)

        response = client.chat.completions.create(
            model="anthropic/claude-3-5-sonnet",
            messages=messages,
            tools=MCP_TOOLS,
            tool_choice="auto",
            response_format={"type": "json_object"},
        )

        choice = response.choices[0]
        message = choice.message

        messages.append(message.model_dump(exclude_none=True))

        if choice.finish_reason == "stop" or not message.tool_calls:
            logging.info(
                "Strategy proposer: finished after %d iterations", iteration + 1
            )
            return message.content

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            logging.info("Strategy proposer: calling tool %s(%s)", fn_name, fn_args)

            result = _call_mcp_tool(fn_name, fn_args, mcp_urls)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    logging.warning("Strategy proposer: reached max iterations (%d)", max_iterations)
    return None
