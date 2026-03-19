"""Discovery phase — uses LLM + MCP tools to generate novel strategy candidates."""

import json

from absl import logging
from openai import OpenAI

from services.agent_orchestration import config
from services.shared.mcp_client import resolve_and_call
from services.shared.model_config import MODEL_PRIMARY, OPENROUTER_BASE_URL

SYSTEM_PROMPT = """You are a strategy discovery agent in an autonomous orchestration loop. Your job is to generate novel trading strategy specifications that can be backtested.

You have access to MCP tools from the strategy server. Follow this workflow:

1. Call list_strategy_types() to see existing strategies
2. Call get_top_strategies(symbol="BTC-USD", limit=10, min_score=0.0) to find what works
3. Analyze gaps in the strategy universe — what indicator combos are untried?
4. Generate a batch of strategy specs using /generate-spec format
5. For each spec, call create_spec() to register it

## Available Indicators
| Indicator | Parameters | Description |
|-----------|-----------|-------------|
| EMA | period: 5-200 | Exponential Moving Average |
| SMA | period: 5-200 | Simple Moving Average |
| RSI | period: 7-21 | Relative Strength Index (0-100) |
| MACD | fast: 8-15, slow: 20-30, signal: 7-11 | Moving Average Convergence Divergence |
| BollingerBands | period: 10-30, stdDev: 1.5-2.5 | Bollinger Bands |
| ATR | period: 7-21 | Average True Range |
| Stochastic | kPeriod: 5-21, dPeriod: 3-7 | Stochastic Oscillator |
| ADX | period: 7-21 | Average Directional Index |
| OBV | (none) | On-Balance Volume |
| VWAP | (none) | Volume-Weighted Average Price |
| CCI | period: 10-30 | Commodity Channel Index |
| Williams%R | period: 7-21 | Williams Percent Range |

## Strategy Spec Format
Each spec must be valid JSON:
{
  "name": "unique_snake_case_name",
  "indicators": {"indicator_name": {"param1": value}},
  "entry_conditions": {"long": "condition string", "short": "condition string"},
  "exit_conditions": {"stop_loss": "condition", "take_profit": "condition"},
  "parameters": {"param_name": value},
  "description": "Human-readable description"
}

Rules:
- Use 2-4 indicators per strategy
- Combine trend + momentum + volume indicators
- All parameters within valid ranges
- Focus on NOVEL combinations not in the existing universe
- Generate specs that are distinct from each other

IMPORTANT: Generate exactly {candidates_per_cycle} strategy specs in this run.
When done creating all specs, respond with a JSON summary:
{{"status": "complete", "created": ["name1", "name2", ...]}}
"""

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_strategy_types",
            "description": "List distinct strategy types with validated or deployed implementations",
            "parameters": {"type": "object", "properties": {}},
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
                    "symbol": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                    "min_score": {"type": "number", "default": 0.0},
                },
                "required": ["symbol"],
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
                    "name": {"type": "string"},
                    "indicators": {"type": "object"},
                    "entry_conditions": {"type": "object"},
                    "exit_conditions": {"type": "object"},
                    "parameters": {"type": "object"},
                    "description": {"type": "string"},
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
    "create_spec": "strategy",
}


def run_discovery(api_key, mcp_urls, candidates_per_cycle=None, existing_names=None):
    """Run the discovery phase to generate N new strategy candidates.

    Args:
        api_key: LLM API key.
        mcp_urls: Dict of MCP server URLs.
        candidates_per_cycle: Override for number of candidates.
        existing_names: Set of strategy names already in state (for dedup).

    Returns a list of created strategy names, or empty list on failure.
    """
    n = candidates_per_cycle or config.CANDIDATES_PER_CYCLE
    existing_names = existing_names or set()

    client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)

    system_content = SYSTEM_PROMPT.format(candidates_per_cycle=n)
    messages = [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": (
                f"Discover and create {n} novel trading strategies. "
                "Follow the workflow: list existing, analyze performers, "
                "identify gaps, then create specs for each new strategy."
            ),
        },
    ]

    created_names = []

    for iteration in range(config.MAX_LLM_ITERATIONS):
        logging.info("Discovery: LLM iteration %d", iteration + 1)

        try:
            response = client.chat.completions.create(
                model=MODEL_PRIMARY,
                messages=messages,
                tools=MCP_TOOLS,
                tool_choice="auto",
            )
        except Exception as e:
            logging.error("Discovery: LLM call failed: %s", e)
            break

        choice = response.choices[0]
        message = choice.message
        messages.append(message.model_dump(exclude_none=True))

        if choice.finish_reason == "stop" or not message.tool_calls:
            # Try to parse final summary
            if message.content:
                try:
                    summary = json.loads(message.content)
                    if isinstance(summary, dict) and "created" in summary:
                        created_names = summary["created"]
                except (json.JSONDecodeError, TypeError):
                    pass
            logging.info(
                "Discovery: finished after %d iterations, created=%s",
                iteration + 1,
                created_names,
            )
            return created_names

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            logging.info("Discovery: calling %s(%s)", fn_name, fn_args)

            # Track create_spec calls, skip duplicates
            if fn_name == "create_spec" and "name" in fn_args:
                spec_name = fn_args["name"]
                if spec_name in existing_names or spec_name in created_names:
                    logging.info(
                        "Discovery: skipping duplicate spec %s", spec_name
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(
                                {"error": f"Strategy '{spec_name}' already exists. Generate a different name."}
                            ),
                        }
                    )
                    continue
                created_names.append(spec_name)

            result = resolve_and_call(
                fn_name,
                fn_args,
                TOOL_TO_SERVER,
                mcp_urls,
                return_type="string",
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    logging.warning("Discovery: reached max iterations (%d)", config.MAX_LLM_ITERATIONS)
    return created_names
