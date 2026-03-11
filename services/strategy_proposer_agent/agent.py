"""Strategy Proposer Agent - proposes novel trading strategies via LLM + MCP tools."""

import json
import os

from absl import logging
from openai import OpenAI

DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


SYSTEM_PROMPT = """You are a trading strategy proposer agent. You analyze the existing strategy universe, identify gaps, and propose novel strategy specifications.

You have access to MCP tools from the strategy server. Follow this exact workflow:

1. Call list_strategy_types() to see all existing strategy types
2. Call get_top_strategies(symbol="BTC-USD", limit=5, min_score=0.0) to find the top 5 strategies by Sharpe ratio
3. Call get_top_strategies(symbol="BTC-USD", limit=100, min_score=-999.0) and identify the bottom 5 by score to understand what fails
4. Apply /indicator-catalog to review available indicators
5. REASON about gaps: what indicator combos are untried? what works in trending vs ranging markets?
6. Apply /generate-spec to produce a valid strategy spec JSON
7. Apply /novelty-check to confirm it differs from existing specs
8. Call create_spec(name, indicators, entry_conditions, exit_conditions, parameters, description) to create the new strategy

## Skill: /indicator-catalog
Available TA4J indicators with valid parameter ranges:

| Indicator | Parameters | Description |
|-----------|-----------|-------------|
| EMA | period: 5-200 | Exponential Moving Average |
| SMA | period: 5-200 | Simple Moving Average |
| RSI | period: 7-21 | Relative Strength Index (0-100) |
| MACD | fast: 8-15, slow: 20-30, signal: 7-11 | Moving Average Convergence Divergence |
| BollingerBands | period: 10-30, stdDev: 1.5-2.5 | Bollinger Bands (upper, middle, lower) |
| ATR | period: 7-21 | Average True Range (volatility) |
| Stochastic | kPeriod: 5-21, dPeriod: 3-7 | Stochastic Oscillator (%K, %D) |
| ADX | period: 7-21 | Average Directional Index (trend strength) |
| OBV | (none) | On-Balance Volume |
| VWAP | (none) | Volume-Weighted Average Price |
| CCI | period: 10-30 | Commodity Channel Index |
| Williams%R | period: 7-21 | Williams Percent Range (-100 to 0) |

Guidelines for combining indicators:
- Use 2-4 indicators per strategy (avoid over-fitting with too many)
- Combine trend indicators (EMA, SMA, MACD, ADX) with momentum indicators (RSI, Stochastic, CCI, Williams%R)
- Include a volume indicator (OBV, VWAP) when possible for confirmation
- Use ATR or BollingerBands for volatility-based exits/position sizing

## Skill: /generate-spec
Output MUST be valid JSON matching the strategy_specs schema:
{
  "name": "string - unique descriptive name using snake_case",
  "indicators": {
    "indicator_name": {"param1": value, "param2": value}
  },
  "entry_conditions": {
    "long": "condition string describing when to enter long",
    "short": "condition string describing when to enter short (optional)"
  },
  "exit_conditions": {
    "stop_loss": "condition string for stop loss exit",
    "take_profit": "condition string for take profit exit",
    "trailing_stop": "condition string for trailing stop (optional)"
  },
  "parameters": {
    "param_name": value_or_range
  },
  "description": "Human-readable description of the strategy logic"
}

Rules:
- All parameter values MUST be within the valid ranges specified in /indicator-catalog
- Entry conditions must reference the indicators defined in the indicators section
- Exit conditions must define at minimum stop_loss and take_profit
- Name must be unique and descriptive (e.g., "ema_rsi_mean_reversion", "macd_adx_trend_following")

## Skill: /novelty-check
Compare the proposed spec against the list of existing strategy types from list_strategy_types():
1. Check if the exact name already exists — reject if so
2. Check indicator combination overlap:
   - Extract the set of indicators from the proposed spec
   - Compare against each existing strategy's indicator set
   - If Jaccard similarity > 0.7 (intersection/union > 70%), reject as too similar
3. If rejected, go back to step 5 (REASON about gaps) and try a different combination
4. If accepted, proceed to create_spec()

When comparing, focus on the combination of indicators AND the logic of entry/exit conditions.
A strategy using the same indicators but with fundamentally different entry logic is considered novel.

IMPORTANT:
- Always follow the workflow in order
- Always produce exactly ONE new strategy spec per run
- Prefer creative combinations that fill gaps in the existing universe
- Consider market regime awareness: some strategies work better in trending markets (use ADX), others in ranging markets (use BollingerBands, RSI)
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


def run_proposer_agent(api_key, mcp_urls):
    """Run the strategy proposer agent to generate a novel strategy spec.

    Returns the final assistant message content, or None if max iterations reached.
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
                "list existing strategies, analyze top and bottom performers, "
                "identify gaps, generate a spec, check novelty, and create it."
            ),
        },
    ]

    max_iterations = 20
    for iteration in range(max_iterations):
        logging.info("Strategy proposer: LLM iteration %d", iteration + 1)

        model = os.environ.get("STRATEGY_PROPOSER_MODEL", DEFAULT_MODEL)
        response = client.chat.completions.create(
            model=model,
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
