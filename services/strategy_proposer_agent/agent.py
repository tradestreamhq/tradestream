"""Strategy Proposer Agent - proposes novel trading strategies via LLM + MCP tools."""

import json

from absl import logging
from openai import OpenAI

INDICATOR_CATALOG = """Available TA4J indicators with valid parameter ranges:

- EMA(period: 5-200) -- Exponential Moving Average. Gives more weight to recent prices.
- SMA(period: 5-200) -- Simple Moving Average. Equal weight to all prices in window.
- RSI(period: 7-21) -- Relative Strength Index. Momentum oscillator measuring speed of price changes (0-100).
- MACD(fast: 8-15, slow: 20-30, signal: 7-11) -- Moving Average Convergence Divergence. Trend-following momentum indicator.
- BollingerBands(period: 10-30, stdDev: 1.5-2.5) -- Volatility bands around a moving average.
- ATR(period: 7-21) -- Average True Range. Measures market volatility.
- Stochastic(kPeriod: 5-21, dPeriod: 3-7) -- Stochastic Oscillator. Compares closing price to price range over period.
- ADX(period: 7-21) -- Average Directional Index. Measures trend strength (0-100).
- OBV -- On-Balance Volume. Cumulative volume indicator for confirming trends.
- VWAP -- Volume Weighted Average Price. Intraday benchmark combining price and volume.
- CCI(period: 10-30) -- Commodity Channel Index. Identifies cyclical turns in price.
- Williams%R(period: 7-21) -- Williams Percent Range. Overbought/oversold oscillator (-100 to 0).
"""

SYSTEM_PROMPT = f"""You are a quantitative strategy designer for cryptocurrency trading.
Your task is to propose novel trading strategies that differ meaningfully from existing ones.

You have access to MCP tools. Follow this exact workflow:

1. Call list_strategy_types() to see what strategy types already exist
2. Call get_top_strategies(symbol="BTC-USD", limit=5) for top performers and get_top_strategies(symbol="BTC-USD", limit=5, min_score=-100.0) for bottom performers to understand what works
3. REASON about gaps using the indicator catalog below:
   - What indicator combinations are NOT yet represented?
   - Which market regimes (trending, ranging, volatile) are underserved?
   - What lessons can be drawn from top vs bottom performers?
4. Generate a valid strategy spec JSON (see format below)
5. Compare your proposed spec against existing types. If >70% similar to any existing strategy, discard and try again.
6. Call create_spec(name, indicators, entry_conditions, exit_conditions, parameters, description) to register the novel strategy

## Skill: /indicator-catalog
{INDICATOR_CATALOG}

## Skill: /generate-spec
Output MUST be valid JSON matching the strategy_specs schema:
{{
  "name": "string -- unique snake_case name",
  "indicators": {{"indicator_name": {{"param": value}}}},
  "entry_conditions": {{"condition_name": "description of condition as string"}},
  "exit_conditions": {{"condition_name": "description of condition as string"}},
  "parameters": {{"key": value}},
  "description": "string -- human-readable description of the strategy logic"
}}

RULES:
1. All indicator parameters MUST be within the valid ranges listed above.
2. Use at least 2 indicators in combination.
3. Entry and exit conditions must reference the indicators you specified.
4. The strategy name must be unique and descriptive in snake_case.
5. Think about what market regime (trending, ranging, volatile) the strategy targets.

## Skill: /novelty-check
Compare proposed spec name and indicator combination against list_strategy_types() results.
Reject if >70% similar to any existing strategy. Similarity is based on:
- Same indicator combination (even with different params) = high similarity
- Same entry/exit logic pattern = high similarity
- Only parameter differences = too similar, reject

IMPORTANT: Always call the tools in order. Always produce a final create_spec call or explain why you could not.
"""

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_strategy_types",
            "description": "List distinct strategy types with validated/deployed implementations",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
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
            "name": "get_spec",
            "description": "Get a strategy specification by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec_name": {
                        "type": "string",
                        "description": "Name of the strategy spec",
                    },
                },
                "required": ["spec_name"],
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
                        "enum": ["backtest", "paper", "live"],
                        "description": "Performance environment",
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
                    "name": {
                        "type": "string",
                        "description": "Unique strategy name in snake_case",
                    },
                    "indicators": {
                        "type": "object",
                        "description": "Map of indicator names to their parameter configs",
                    },
                    "entry_conditions": {
                        "type": "object",
                        "description": "Map of condition names to condition descriptions",
                    },
                    "exit_conditions": {
                        "type": "object",
                        "description": "Map of condition names to condition descriptions",
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Strategy parameters as key-value pairs",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of strategy logic",
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
            "content": "Propose a novel trading strategy. Follow the workflow exactly.",
        },
    ]

    max_iterations = 15
    for iteration in range(max_iterations):
        logging.info("LLM iteration %d", iteration + 1)

        response = client.chat.completions.create(
            model="anthropic/claude-3-5-sonnet",
            messages=messages,
            tools=MCP_TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message

        messages.append(message.model_dump(exclude_none=True))

        if choice.finish_reason == "stop" or not message.tool_calls:
            logging.info("Agent finished after %d iterations", iteration + 1)
            return message.content

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            logging.info("Calling tool %s(%s)", fn_name, fn_args)

            result = _call_mcp_tool(fn_name, fn_args, mcp_urls)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    logging.warning("Reached max iterations (%d)", max_iterations)
    return None
