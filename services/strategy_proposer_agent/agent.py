"""Strategy Proposer Agent - proposes novel trading strategies via LLM + MCP tools."""

import json

from absl import logging
from openai import OpenAI


SYSTEM_PROMPT = """You are a strategy proposer agent. You analyze the existing strategy universe, identify gaps, and propose novel trading strategies.

You have access to MCP tools from the strategy server. Follow this exact workflow:

1. Call list_strategy_types() to see all existing strategy types
2. Call get_performance() for top 5 and bottom 5 strategies by sharpe ratio to understand what works and what doesn't
3. Apply /indicator-catalog to review available indicators
4. REASON about gaps: what indicator combos are untried? what works in trending vs ranging markets?
5. Apply /generate-spec to produce a valid strategy spec JSON
6. Apply /novelty-check to confirm it differs from existing specs
7. Call create_spec(name, indicators, entry_conditions, exit_conditions, parameters, description) to save the new strategy

## Skill: /indicator-catalog
Available TA4J indicators with valid parameter ranges:
- EMA(period: 5-200) — Exponential Moving Average. Reacts faster to recent price changes than SMA.
- SMA(period: 5-200) — Simple Moving Average. Equal weight across the lookback window.
- RSI(period: 7-21) — Relative Strength Index. Measures overbought/oversold conditions (0-100).
- MACD(fast: 8-15, slow: 20-30, signal: 7-11) — Moving Average Convergence Divergence. Trend and momentum.
- BollingerBands(period: 10-30, stdDev: 1.5-2.5) — Volatility bands around a moving average.
- ATR(period: 7-21) — Average True Range. Measures volatility in absolute terms.
- Stochastic(kPeriod: 5-21, dPeriod: 3-7) — Stochastic Oscillator. Momentum indicator comparing close to range.
- ADX(period: 7-21) — Average Directional Index. Measures trend strength (0-100).
- OBV — On-Balance Volume. Cumulative volume flow indicator, no parameters.
- VWAP — Volume-Weighted Average Price. Intraday fair value benchmark, no parameters.
- CCI(period: 10-30) — Commodity Channel Index. Identifies cyclical trends.
- Williams%R(period: 7-21) — Williams Percent Range. Similar to Stochastic, measures overbought/oversold.

When combining indicators, prefer complementary types:
- Trend (EMA, SMA, MACD, ADX) + Momentum (RSI, Stochastic, CCI, Williams%R)
- Trend + Volatility (BollingerBands, ATR)
- Volume (OBV, VWAP) + any of the above

## Skill: /generate-spec
Output MUST be valid JSON matching the strategy_specs schema:
{
  "name": "string — unique snake_case name for the strategy",
  "indicators": {"indicator_name": {"param1": value, ...}},
  "entry_conditions": {"condition_name": "human-readable condition string"},
  "exit_conditions": {"condition_name": "human-readable condition string"},
  "parameters": {"key": value},
  "description": "string — what the strategy does and why it should work"
}

Rules:
- name must be unique, descriptive, snake_case
- All indicator parameters must be within the valid ranges from /indicator-catalog
- Use at least 2 indicators from different categories (trend, momentum, volatility, volume)
- entry_conditions and exit_conditions must reference the indicators defined
- parameters should include position sizing and risk management values
- description should explain the market hypothesis

## Skill: /novelty-check
Compare the proposed spec against the list of existing strategy types from step 1:
- Compare indicator combinations: if >70% of indicators overlap with an existing strategy, REJECT
- Compare name: if name is too similar to existing, REJECT
- If rejected, go back to step 4 and reason about a different gap
- Only proceed to create_spec if the novelty check passes

IMPORTANT: Always call the tools in order. Always produce a final strategy spec or explain why you couldn't.
"""

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_strategy_types",
            "description": "List all existing strategy type names",
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
            "name": "get_performance",
            "description": "Get performance metrics for a strategy implementation",
            "parameters": {
                "type": "object",
                "properties": {
                    "impl_id": {
                        "type": "string",
                        "description": "Strategy implementation ID",
                    },
                    "environment": {
                        "type": "string",
                        "enum": ["backtest", "paper", "live"],
                        "description": "Environment to get metrics for",
                    },
                },
                "required": ["impl_id"],
            },
        },
    },
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
            "name": "get_spec",
            "description": "Get a strategy spec by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec_name": {
                        "type": "string",
                        "description": "Strategy spec name",
                    },
                },
                "required": ["spec_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_spec",
            "description": "Create a new strategy spec",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Unique strategy name",
                    },
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
                        "description": "Strategy parameters",
                    },
                    "description": {
                        "type": "string",
                        "description": "Strategy description",
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
    "get_performance": "strategy",
    "get_top_strategies": "strategy",
    "get_spec": "strategy",
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


def run_agent(api_key, mcp_urls):
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
                "list existing strategies, analyze performance, identify gaps in "
                "indicator coverage, generate a valid spec, check novelty, and "
                "create the spec."
            ),
        },
    ]

    max_iterations = 20
    for iteration in range(max_iterations):
        logging.info("Strategy proposer: LLM iteration %d", iteration + 1)

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
            logging.info(
                "Strategy proposer: agent finished after %d iterations",
                iteration + 1,
            )
            return message.content

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            logging.info(
                "Strategy proposer: calling tool %s(%s)", fn_name, fn_args
            )

            result = _call_mcp_tool(fn_name, fn_args, mcp_urls)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    logging.warning(
        "Strategy proposer: reached max iterations (%d)", max_iterations
    )
    return None
