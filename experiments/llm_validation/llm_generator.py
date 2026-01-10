"""
LLM-based Strategy Specification Generator.

This module uses Claude API to generate novel trading strategy specifications
based on few-shot examples from existing high-performing strategies.
"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

try:
    import anthropic
except ImportError:
    anthropic = None

from strategy_schema import (
    IndicatorType,
    ConditionType,
    ParameterType,
    load_existing_strategies,
    validate_strategy,
    ValidationResult,
)


# Available indicators and conditions for reference in prompts
AVAILABLE_INDICATORS = [e.value for e in IndicatorType]
AVAILABLE_CONDITIONS = [e.value for e in ConditionType]
AVAILABLE_PARAM_TYPES = [e.value for e in ParameterType]


SYSTEM_PROMPT = """You are an expert quantitative trading strategy designer. Your task is to generate novel trading strategy specifications in YAML format.

You have deep knowledge of technical analysis indicators and how to combine them effectively. You understand:
- Moving averages (SMA, EMA, DEMA, TEMA) for trend following
- Oscillators (RSI, Stochastic, MACD, CCI) for momentum and overbought/oversold
- Volume indicators (OBV, CMF, MFI, Klinger) for volume confirmation
- Trend indicators (ADX, DMI, Aroon) for trend strength
- Volatility indicators (ATR, Bollinger Bands) for range and breakout

When generating strategies:
1. Combine 2-4 indicators that complement each other
2. Use clear entry and exit conditions
3. Include meaningful parameter ranges for optimization
4. Avoid overly complex logic that may overfit
5. Consider both trend-following and mean-reversion approaches
"""


def get_strategy_schema_prompt() -> str:
    """Generate the schema documentation for the prompt."""
    return f"""
## Strategy YAML Schema

```yaml
name: STRATEGY_NAME  # Uppercase with underscores
description: Brief description of the strategy
complexity: SIMPLE|MEDIUM|COMPLEX

indicators:
  - id: unique_identifier
    type: INDICATOR_TYPE  # See available types below
    input: close|high|low|open|volume|<other_indicator_id>  # Optional, defaults to close
    params:
      period: "${{parameterName}}"  # Reference to parameter
      # Other params depend on indicator type

entryConditions:
  - type: CONDITION_TYPE
    indicator: indicator_id  # Reference to indicator
    params:
      crosses: other_indicator_id  # For crossover conditions
      threshold: 25  # For constant comparisons
      value: 70  # Alternative for constant comparisons

exitConditions:
  - type: CONDITION_TYPE
    indicator: indicator_id
    params:
      crosses: other_indicator_id

parameters:
  - name: parameterName  # camelCase
    type: INTEGER|DOUBLE
    min: 5
    max: 50
    defaultValue: 20
```

## Available Indicator Types
{', '.join(AVAILABLE_INDICATORS)}

## Available Condition Types
{', '.join(AVAILABLE_CONDITIONS)}

## Available Parameter Types
{', '.join(AVAILABLE_PARAM_TYPES)}
"""


def format_few_shot_examples(strategies: list[dict]) -> str:
    """Format existing strategies as few-shot examples."""
    examples = []
    for i, strategy in enumerate(strategies, 1):
        yaml_str = yaml.dump(strategy, default_flow_style=False, sort_keys=False)
        examples.append(
            f"### Example {i}: {strategy.get('name', 'Unknown')}\n```yaml\n{yaml_str}```"
        )
    return "\n\n".join(examples)


def create_generation_prompt(
    few_shot_examples: list[dict], creativity_hint: str | None = None
) -> str:
    """Create the full prompt for strategy generation."""
    schema = get_strategy_schema_prompt()
    examples = format_few_shot_examples(few_shot_examples)

    prompt = f"""Generate a NOVEL trading strategy specification in YAML format.

{schema}

## Few-Shot Examples
Here are proven trading strategies to learn from:

{examples}

## Requirements
1. Create a NOVEL strategy - do NOT copy any example directly
2. Combine indicators in a new way not seen in the examples
3. Use 2-4 indicators that complement each other
4. Include clear entry and exit conditions
5. Define meaningful parameter ranges (not too wide, not too narrow)
6. The strategy should have a clear trading logic that can be explained simply

"""
    if creativity_hint:
        prompt += f"\n## Creativity Hint\n{creativity_hint}\n"

    prompt += """
## Output Format
Output ONLY valid YAML - no explanations, no markdown code blocks, just the YAML content starting with 'name:'.
"""
    return prompt


CREATIVITY_HINTS = [
    "Focus on volume confirmation for trend signals",
    "Combine momentum and trend indicators",
    "Use multiple timeframe concepts with different periods",
    "Create a mean-reversion strategy with overbought/oversold filters",
    "Combine volatility breakout with trend confirmation",
    "Use divergence concepts between price and oscillators",
    "Create a trend-following strategy with volatility filters",
    "Combine Aroon indicators with volume confirmation",
    "Use CMO (Chande Momentum Oscillator) with trend filters",
    "Create a strategy using Williams %R with moving average confirmation",
]


@dataclass
class GenerationResult:
    """Result of a single strategy generation attempt."""

    raw_output: str
    parsed_strategy: dict | None
    validation: ValidationResult
    generation_time_ms: float
    creativity_hint: str | None


class StrategyGenerator:
    """Generates trading strategies using Claude API."""

    def __init__(
        self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"
    ):
        """
        Initialize the generator.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
            model: Model to use for generation.
        """
        if anthropic is None:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model

    def generate_single(
        self,
        few_shot_examples: list[dict],
        existing_strategies: list[dict] | None = None,
        creativity_hint: str | None = None,
        temperature: float = 0.8,
    ) -> GenerationResult:
        """
        Generate a single strategy.

        Args:
            few_shot_examples: List of example strategies for few-shot learning
            existing_strategies: All existing strategies to check novelty against
            creativity_hint: Optional hint to guide generation
            temperature: LLM temperature (higher = more creative)

        Returns:
            GenerationResult with raw output, parsed strategy, and validation
        """
        prompt = create_generation_prompt(few_shot_examples, creativity_hint)

        start_time = time.time()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        generation_time = (time.time() - start_time) * 1000

        raw_output = response.content[0].text.strip()

        # Try to parse as YAML
        parsed = None
        try:
            parsed = yaml.safe_load(raw_output)
        except yaml.YAMLError:
            # Try to extract YAML from markdown code block if present
            if "```yaml" in raw_output:
                yaml_content = raw_output.split("```yaml")[1].split("```")[0]
                try:
                    parsed = yaml.safe_load(yaml_content)
                    raw_output = yaml_content.strip()
                except yaml.YAMLError:
                    pass
            elif "```" in raw_output:
                yaml_content = raw_output.split("```")[1].split("```")[0]
                try:
                    parsed = yaml.safe_load(yaml_content)
                    raw_output = yaml_content.strip()
                except yaml.YAMLError:
                    pass

        # Validate
        validation = validate_strategy(raw_output, existing_strategies)

        return GenerationResult(
            raw_output=raw_output,
            parsed_strategy=parsed if isinstance(parsed, dict) else None,
            validation=validation,
            generation_time_ms=generation_time,
            creativity_hint=creativity_hint,
        )

    def generate_batch(
        self,
        few_shot_examples: list[dict],
        existing_strategies: list[dict] | None = None,
        count: int = 50,
        temperature: float = 0.8,
        use_creativity_hints: bool = True,
    ) -> list[GenerationResult]:
        """
        Generate a batch of strategies.

        Args:
            few_shot_examples: List of example strategies for few-shot learning
            existing_strategies: All existing strategies to check novelty against
            count: Number of strategies to generate
            temperature: LLM temperature
            use_creativity_hints: Whether to cycle through creativity hints

        Returns:
            List of GenerationResults
        """
        results = []

        for i in range(count):
            hint = None
            if use_creativity_hints:
                hint = CREATIVITY_HINTS[i % len(CREATIVITY_HINTS)]

            print(f"Generating strategy {i + 1}/{count}...")
            try:
                result = self.generate_single(
                    few_shot_examples=few_shot_examples,
                    existing_strategies=existing_strategies,
                    creativity_hint=hint,
                    temperature=temperature,
                )
                results.append(result)

                # Log progress
                status = "✓" if result.validation.is_valid else "✗"
                print(
                    f"  {status} Syntax: {result.validation.syntax_valid}, "
                    f"Logic: {result.validation.logic_valid}, "
                    f"Novel: {result.validation.is_novel}"
                )

                # Rate limiting
                time.sleep(0.5)

            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue

        return results


def select_few_shot_examples(
    strategies_dir: str,
    selection_method: str = "diverse",
    count: int = 7,
) -> list[dict]:
    """
    Select strategies to use as few-shot examples.

    Args:
        strategies_dir: Directory containing strategy YAML files
        selection_method: How to select examples:
            - "diverse": Select strategies using different indicator types
            - "random": Random selection
            - "all": Use all strategies (limited by count)
        count: Number of examples to select

    Returns:
        List of strategy dictionaries
    """
    all_strategies = load_existing_strategies(strategies_dir)

    if selection_method == "random":
        import random

        return random.sample(all_strategies, min(count, len(all_strategies)))

    elif selection_method == "diverse":
        # Select strategies that use different indicator types
        selected = []
        seen_indicator_combos = set()

        for strategy in all_strategies:
            indicator_types = tuple(
                sorted(ind.get("type") for ind in strategy.get("indicators", []))
            )

            if indicator_types not in seen_indicator_combos:
                selected.append(strategy)
                seen_indicator_combos.add(indicator_types)

            if len(selected) >= count:
                break

        return selected

    else:  # "all"
        return all_strategies[:count]


def run_experiment_1(
    strategies_dir: str,
    output_dir: str,
    num_generations: int = 50,
    few_shot_count: int = 7,
    temperature: float = 0.8,
) -> dict:
    """
    Run Experiment 1: LLM Spec Generation Quality.

    Success Criteria:
    - ≥80% syntactically valid
    - ≥60% logically coherent
    - ≥70% novel

    Args:
        strategies_dir: Directory with existing strategy YAML files
        output_dir: Where to save results
        num_generations: Number of strategies to generate
        few_shot_count: Number of few-shot examples to use
        temperature: LLM temperature

    Returns:
        Dictionary with experiment results
    """
    print("=" * 60)
    print("EXPERIMENT 1: LLM Spec Generation Quality")
    print("=" * 60)

    # Load existing strategies
    existing = load_existing_strategies(strategies_dir)
    print(f"Loaded {len(existing)} existing strategies")

    # Select few-shot examples
    few_shot = select_few_shot_examples(strategies_dir, "diverse", few_shot_count)
    print(f"Selected {len(few_shot)} few-shot examples:")
    for s in few_shot:
        print(f"  - {s.get('name')}")

    # Generate strategies
    generator = StrategyGenerator()
    results = generator.generate_batch(
        few_shot_examples=few_shot,
        existing_strategies=existing,
        count=num_generations,
        temperature=temperature,
    )

    # Calculate metrics
    total = len(results)
    syntax_valid = sum(1 for r in results if r.validation.syntax_valid)
    logic_valid = sum(1 for r in results if r.validation.logic_valid)
    novel = sum(1 for r in results if r.validation.is_novel)
    fully_valid = sum(1 for r in results if r.validation.is_valid)

    syntax_rate = syntax_valid / total if total > 0 else 0
    logic_rate = logic_valid / total if total > 0 else 0
    novel_rate = novel / total if total > 0 else 0
    valid_rate = fully_valid / total if total > 0 else 0

    # Prepare output
    output = {
        "experiment": "1_spec_generation_quality",
        "config": {
            "num_generations": num_generations,
            "few_shot_count": few_shot_count,
            "temperature": temperature,
        },
        "results": {
            "total_generated": total,
            "syntax_valid_count": syntax_valid,
            "syntax_valid_rate": syntax_rate,
            "logic_valid_count": logic_valid,
            "logic_valid_rate": logic_rate,
            "novel_count": novel,
            "novel_rate": novel_rate,
            "fully_valid_count": fully_valid,
            "fully_valid_rate": valid_rate,
        },
        "success_criteria": {
            "syntax_valid_target": 0.80,
            "syntax_valid_passed": syntax_rate >= 0.80,
            "logic_valid_target": 0.60,
            "logic_valid_passed": logic_rate >= 0.60,
            "novel_target": 0.70,
            "novel_passed": novel_rate >= 0.70,
        },
        "overall_passed": (
            syntax_rate >= 0.80 and logic_rate >= 0.60 and novel_rate >= 0.70
        ),
        "generated_strategies": [],
    }

    # Save valid strategies
    valid_strategies_dir = Path(output_dir) / "generated_strategies"
    valid_strategies_dir.mkdir(parents=True, exist_ok=True)

    for i, result in enumerate(results):
        strategy_data = {
            "index": i,
            "syntax_valid": result.validation.syntax_valid,
            "logic_valid": result.validation.logic_valid,
            "is_novel": result.validation.is_novel,
            "is_valid": result.validation.is_valid,
            "errors": result.validation.errors,
            "generation_time_ms": result.generation_time_ms,
            "creativity_hint": result.creativity_hint,
        }

        if result.parsed_strategy:
            strategy_data["strategy"] = result.parsed_strategy
            strategy_data["name"] = result.parsed_strategy.get("name", f"GENERATED_{i}")

            # Save valid strategies to files
            if result.validation.is_valid:
                name = result.parsed_strategy.get("name", f"generated_{i}")
                filename = f"{name.lower()}.yaml"
                with open(valid_strategies_dir / filename, "w") as f:
                    yaml.dump(
                        result.parsed_strategy,
                        f,
                        default_flow_style=False,
                        sort_keys=False,
                    )

        output["generated_strategies"].append(strategy_data)

    # Save results
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(output_dir) / "experiment_1_results.json", "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT 1 RESULTS")
    print("=" * 60)
    print(f"Total Generated: {total}")
    print(
        f"Syntax Valid: {syntax_valid}/{total} ({syntax_rate:.1%}) {'✓' if syntax_rate >= 0.80 else '✗'} (target: 80%)"
    )
    print(
        f"Logic Valid:  {logic_valid}/{total} ({logic_rate:.1%}) {'✓' if logic_rate >= 0.60 else '✗'} (target: 60%)"
    )
    print(
        f"Novel:        {novel}/{total} ({novel_rate:.1%}) {'✓' if novel_rate >= 0.70 else '✗'} (target: 70%)"
    )
    print(f"Fully Valid:  {fully_valid}/{total} ({valid_rate:.1%})")
    print("-" * 60)
    print(f"OVERALL: {'PASSED ✓' if output['overall_passed'] else 'FAILED ✗'}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run LLM Strategy Generation Experiments"
    )
    parser.add_argument(
        "--strategies-dir",
        default="../../src/main/resources/strategies",
        help="Directory containing existing strategy YAML files",
    )
    parser.add_argument(
        "--output-dir",
        default="./results",
        help="Directory to save experiment results",
    )
    parser.add_argument(
        "--num-generations",
        type=int,
        default=50,
        help="Number of strategies to generate",
    )
    parser.add_argument(
        "--few-shot-count",
        type=int,
        default=7,
        help="Number of few-shot examples",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.8,
        help="LLM temperature (0.0-1.0)",
    )

    args = parser.parse_args()

    run_experiment_1(
        strategies_dir=args.strategies_dir,
        output_dir=args.output_dir,
        num_generations=args.num_generations,
        few_shot_count=args.few_shot_count,
        temperature=args.temperature,
    )
