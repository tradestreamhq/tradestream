"""
Strategy Proposer Agent.

Proposes novel trading strategies by reasoning about gaps in the existing
strategy universe and generating valid strategy specs via the strategy MCP.
"""

import json
import logging
from typing import Any, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

INDICATOR_CATALOG = """Available TA4J indicators with valid parameter ranges:

- EMA(period: 5-200) — Exponential Moving Average. Gives more weight to recent prices.
- SMA(period: 5-200) — Simple Moving Average. Equal weight to all prices in window.
- RSI(period: 7-21) — Relative Strength Index. Momentum oscillator measuring speed of price changes (0-100).
- MACD(fast: 8-15, slow: 20-30, signal: 7-11) — Moving Average Convergence Divergence. Trend-following momentum indicator.
- BollingerBands(period: 10-30, stdDev: 1.5-2.5) — Volatility bands around a moving average.
- ATR(period: 7-21) — Average True Range. Measures market volatility.
- Stochastic(kPeriod: 5-21, dPeriod: 3-7) — Stochastic Oscillator. Compares closing price to price range over period.
- ADX(period: 7-21) — Average Directional Index. Measures trend strength (0-100).
- OBV — On-Balance Volume. Cumulative volume indicator for confirming trends.
- VWAP — Volume Weighted Average Price. Intraday benchmark combining price and volume.
- CCI(period: 10-30) — Commodity Channel Index. Identifies cyclical turns in price.
- Williams%R(period: 7-21) — Williams Percent Range. Overbought/oversold oscillator (-100 to 0).
"""

SYSTEM_PROMPT = f"""You are a quantitative strategy designer for cryptocurrency trading.
Your task is to propose novel trading strategies that differ meaningfully from existing ones.

{INDICATOR_CATALOG}

STRATEGY SPEC FORMAT (must be valid JSON matching the strategy_specs schema):
{{
  "name": "string — unique snake_case name",
  "indicators": {{"indicator_name": {{"param": value}}}},
  "entry_conditions": {{"condition_name": "description of condition as string"}},
  "exit_conditions": {{"condition_name": "description of condition as string"}},
  "parameters": {{"key": value}},
  "description": "string — human-readable description of the strategy logic"
}}

RULES:
1. All indicator parameters MUST be within the valid ranges listed above.
2. Use at least 2 indicators in combination.
3. Entry and exit conditions must reference the indicators you specified.
4. The strategy name must be unique and descriptive in snake_case.
5. Think about what market regime (trending, ranging, volatile) the strategy targets.
6. Consider both momentum and mean-reversion approaches.
"""

NOVELTY_CHECK_PROMPT = """Compare the proposed strategy against the existing strategies.

Existing strategy types: {existing_types}

Proposed strategy:
{proposed_spec}

Evaluate similarity:
1. Does a strategy with the same indicator combination already exist?
2. Is the entry/exit logic substantially different from existing strategies?
3. Rate overall similarity from 0-100 (0=completely novel, 100=identical).

Respond with JSON: {{"similarity_score": <int>, "reason": "explanation", "is_novel": <bool>}}
A strategy is novel if similarity_score <= 70.
"""


class StrategyProposerAgent:
    """Agent that proposes novel trading strategies via LLM reasoning."""

    def __init__(
        self,
        openrouter_api_key: str,
        mcp_strategy_url: str,
        model: str = "anthropic/claude-3-5-sonnet",
    ):
        self.client = OpenAI(
            api_key=openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.mcp_strategy_url = mcp_strategy_url
        self.model = model

    async def _call_mcp_tool(
        self, session: Any, tool_name: str, arguments: dict
    ) -> Any:
        """Call an MCP tool and return parsed JSON result."""
        result = await session.call_tool(tool_name, arguments)
        if result.content and len(result.content) > 0:
            return json.loads(result.content[0].text)
        return None

    async def _get_existing_strategies(self, session: Any) -> list[str]:
        """Get list of existing strategy types from MCP."""
        return await self._call_mcp_tool(session, "list_strategy_types", {})

    async def _get_performance_context(
        self, session: Any
    ) -> dict[str, list[dict]]:
        """Get top and bottom performing strategies for context."""
        top = await self._call_mcp_tool(
            session,
            "get_top_strategies",
            {"symbol": "BTC/USD", "limit": 5, "min_score": 0.0},
        )
        bottom = await self._call_mcp_tool(
            session,
            "get_top_strategies",
            {"symbol": "BTC/USD", "limit": 5, "min_score": -100.0},
        )
        return {"top": top or [], "bottom": bottom or []}

    def _generate_strategy_spec(
        self,
        existing_types: list[str],
        performance: dict[str, list[dict]],
    ) -> Optional[dict]:
        """Use LLM to generate a novel strategy spec."""
        user_prompt = f"""Current existing strategy types: {json.dumps(existing_types)}

Top 5 strategies by Sharpe ratio: {json.dumps(performance.get('top', []), default=str)}

Bottom 5 strategies by Sharpe ratio: {json.dumps(performance.get('bottom', []), default=str)}

Analyze the gaps in the existing strategy universe:
1. What indicator combinations are NOT yet represented?
2. Which market regimes (trending, ranging, volatile) are underserved?
3. What lessons can be drawn from top vs bottom performers?

Propose ONE novel strategy spec that fills an identified gap.
Respond with ONLY the JSON strategy spec object, no other text."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
        )

        content = response.choices[0].message.content
        if content:
            return json.loads(content)
        return None

    def _check_novelty(
        self, proposed_spec: dict, existing_types: list[str]
    ) -> dict:
        """Use LLM to check if the proposed strategy is novel enough."""
        prompt = NOVELTY_CHECK_PROMPT.format(
            existing_types=json.dumps(existing_types),
            proposed_spec=json.dumps(proposed_spec, indent=2),
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a strategy similarity analyst. Respond with JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if content:
            return json.loads(content)
        return {"similarity_score": 100, "reason": "Failed to check", "is_novel": False}

    def _validate_spec(self, spec: dict) -> bool:
        """Validate that the spec has all required fields."""
        required = ["name", "indicators", "entry_conditions", "exit_conditions", "parameters", "description"]
        for field in required:
            if field not in spec:
                logger.warning("Spec missing required field: %s", field)
                return False

        if not isinstance(spec["indicators"], dict) or len(spec["indicators"]) < 1:
            logger.warning("Spec must have at least one indicator")
            return False

        if not isinstance(spec["entry_conditions"], dict):
            logger.warning("entry_conditions must be a dict")
            return False

        if not isinstance(spec["exit_conditions"], dict):
            logger.warning("exit_conditions must be a dict")
            return False

        if not isinstance(spec["name"], str) or not spec["name"].strip():
            logger.warning("name must be a non-empty string")
            return False

        return True

    async def run(self, session: Any) -> Optional[dict]:
        """Execute the full strategy proposal workflow.

        Args:
            session: An MCP ClientSession connected to the strategy MCP server.

        Returns:
            The created spec result dict, or None if no novel spec was proposed.
        """
        # Step 1: Get existing strategy types
        logger.info("Fetching existing strategy types...")
        existing_types = await self._get_existing_strategies(session)
        logger.info("Found %d existing strategy types", len(existing_types))

        # Step 2: Get performance context
        logger.info("Fetching performance context...")
        performance = await self._get_performance_context(session)
        logger.info(
            "Got %d top and %d bottom strategies",
            len(performance["top"]),
            len(performance["bottom"]),
        )

        # Step 3 & 4: Generate a novel strategy spec (LLM reasons about gaps)
        logger.info("Generating novel strategy spec...")
        spec = self._generate_strategy_spec(existing_types, performance)
        if spec is None:
            logger.warning("LLM failed to generate a strategy spec")
            return None

        # Validate spec structure
        if not self._validate_spec(spec):
            logger.warning("Generated spec failed validation: %s", spec)
            return None

        logger.info("Generated spec: %s", spec["name"])

        # Step 5: Novelty check
        logger.info("Running novelty check...")
        novelty = self._check_novelty(spec, existing_types)
        if not novelty.get("is_novel", False):
            logger.info(
                "Spec rejected — too similar (score=%s): %s",
                novelty.get("similarity_score"),
                novelty.get("reason"),
            )
            return None
        logger.info(
            "Novelty check passed (score=%s): %s",
            novelty.get("similarity_score"),
            novelty.get("reason"),
        )

        # Step 6: Create the spec via MCP
        logger.info("Creating spec via strategy MCP...")
        result = await self._call_mcp_tool(
            session,
            "create_spec",
            {
                "name": spec["name"],
                "indicators": spec["indicators"],
                "entry_conditions": spec["entry_conditions"],
                "exit_conditions": spec["exit_conditions"],
                "parameters": spec["parameters"],
                "description": spec["description"],
            },
        )

        if result and "spec_id" in result:
            logger.info("Successfully created spec: %s (id=%s)", spec["name"], result["spec_id"])
        else:
            logger.warning("Failed to create spec: %s", result)

        return result
