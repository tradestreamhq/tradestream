# Learning Agent Specification

## Goal

OpenCode agent that generates new strategy specs based on patterns observed in top performers, using few-shot learning from existing successful strategies.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  LEARNING AGENT (OpenCode)                                 │
│                                                             │
│  Schedule: Every 6 hours                                   │
│  Model: Claude Sonnet 4.5 (creative generation)            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MCP Tools                                            │   │
│  │  • strategy-db-mcp:                                  │   │
│  │    - get_top_specs(limit=10)                        │   │
│  │    - get_implementations(spec_id)                   │   │
│  │    - submit_new_spec(spec)                          │   │
│  │    - check_spec_similarity(spec)                    │   │
│  │    - get_generation_stats(source)                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Skills                                               │   │
│  │  • few-shot-spec-generation                         │   │
│  │  • analyze-performance-patterns                     │   │
│  │  • validate-spec-structure                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Output: New specs → strategy_specs table                  │
│  Feedback: GA results → learning adjustments               │
└─────────────────────────────────────────────────────────────┘
```

## Workflow

### 1. Gather Context

```python
# Query top-performing specs with their best implementations
top_specs = await strategy_db_mcp.get_top_specs(limit=10)

for spec in top_specs:
    spec.top_implementations = await strategy_db_mcp.get_implementations(
        spec_id=spec.spec_id,
        status="VALIDATED",
        limit=5
    )

# Also fetch feedback on previously generated specs
generation_stats = await strategy_db_mcp.get_generation_stats(source="LLM_GENERATED")
```

### 2. Analyze Patterns

The agent identifies common patterns across top performers:
- Indicator combinations that work together
- Entry/exit condition types that correlate with success
- Parameter ranges that tend to perform well
- Market regimes where certain patterns excel
- **Feedback from GA optimization on previously generated specs**

### 3. Generate New Specs

Using few-shot prompting with top performers as examples, generate novel specs that:
- Combine successful elements in new ways
- Explore variations on proven patterns
- Fill gaps in the strategy library
- **Avoid patterns that have historically underperformed**

### 4. Validate and Submit

- Check spec structure is valid
- Validate spec quality criteria
- Check for duplicates/high similarity
- Submit to database for GA optimization

## Few-Shot Spec Generation

### System Prompt

```markdown
You are a quantitative strategy researcher for TradeStream. Your job is to generate
new trading strategy specifications based on patterns observed in our top performers.

## Your Context
You have access to our top 10 performing strategy specs, each with their best
implementations and performance metrics. Use these as examples and inspiration.

You also have feedback on previously generated specs - which ones succeeded in
GA optimization and which ones failed. Use this to guide your generation.

## Your Goal
Generate 1-5 NEW strategy specs that:
1. Follow the same structural format as the examples
2. Are genuinely novel (not duplicates or minor variations)
3. Build on patterns that work in the top performers
4. Have clear reasoning for why they should work
5. Avoid patterns similar to those that have historically failed

## Output Format
For each new spec, provide:
- Name (unique, descriptive)
- Description (1-2 sentences)
- Indicators (list with parameters)
- Entry conditions
- Exit conditions
- Parameter definitions with ranges
- Reasoning (why this should work, based on what you learned)

## Constraints
- Only use indicators we support: RSI, MACD, EMA, SMA, Bollinger Bands, ATR, ADX, Stochastic, Volume
- Keep parameter ranges reasonable (not too wide)
- Entry/exit conditions must be unambiguous
```

### Few-Shot Examples (from top specs)

```markdown
## Example 1: RSI_REVERSAL (Sharpe: 1.8, Accuracy: 62%)

**Why it works:** Captures mean reversion when assets become oversold. Works best in
ranging markets where extreme readings tend to correct.

**Indicators:**
- RSI(period=${rsiPeriod})

**Entry:** RSI < ${oversold}
**Exit:** RSI > ${overbought}

**Parameters:**
- rsiPeriod: INTEGER, 5-50, default 14
- oversold: INTEGER, 20-35, default 30
- overbought: INTEGER, 65-80, default 70

---

## Example 2: MACD_MOMENTUM (Sharpe: 1.6, Accuracy: 58%)

**Why it works:** MACD crossovers identify momentum shifts. Combined with histogram
expansion, filters out weak signals.

**Indicators:**
- MACD(fast=${fastPeriod}, slow=${slowPeriod}, signal=${signalPeriod})

**Entry:** MACD crosses above signal line AND histogram > 0
**Exit:** MACD crosses below signal line

**Parameters:**
- fastPeriod: INTEGER, 8-15, default 12
- slowPeriod: INTEGER, 20-30, default 26
- signalPeriod: INTEGER, 7-12, default 9
```

### Generation Prompt

```markdown
Based on the top-performing specs above, generate 3 new strategy specs.

Consider:
1. What indicator combinations haven't been tried?
2. Can you combine elements from multiple successful strategies?
3. Are there variations on the successful patterns worth exploring?

For each new spec, explain your reasoning - what pattern from the top performers
inspired it, and why you think this variation will work.
```

## Duplicate Detection

### Similarity Check

Uses a multi-dimensional similarity calculation combining structural analysis with
embedding-based semantic similarity for robust duplicate detection.

```python
import numpy as np
from sentence_transformers import SentenceTransformer

# Load embedding model once at startup
_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

async def check_spec_similarity(
    new_spec: dict,
    existing_specs: list[dict],
    threshold: float = 0.85
) -> tuple[bool, str]:
    """
    Check if new spec is too similar to existing specs.

    Uses hybrid similarity combining:
    - Structural similarity (indicators, conditions, parameters)
    - Embedding similarity (semantic meaning)

    Returns:
        (is_duplicate, reason)
    """
    for existing in existing_specs:
        structural_sim = calculate_structural_similarity(new_spec, existing)
        embedding_sim = calculate_embedding_similarity(new_spec, existing)

        # Weighted combination: structural (60%) + embedding (40%)
        combined_similarity = 0.6 * structural_sim + 0.4 * embedding_sim

        if combined_similarity > threshold:
            return True, f"Too similar to {existing['name']} ({combined_similarity:.0%})"

    return False, None

def calculate_structural_similarity(spec1: dict, spec2: dict) -> float:
    """
    Calculate structural similarity between two specs based on:
    - Indicator overlap (type and parameters)
    - Entry condition similarity (type, operator, thresholds)
    - Exit condition similarity (type, operator, thresholds)
    - Parameter range overlap
    """
    # Indicator similarity (type + parameter structure)
    indicator_sim = _calculate_indicator_similarity(spec1, spec2)

    # Entry condition similarity (including thresholds)
    entry_sim = _calculate_condition_similarity(
        spec1.get("entry_conditions", []),
        spec2.get("entry_conditions", [])
    )

    # Exit condition similarity (including thresholds)
    exit_sim = _calculate_condition_similarity(
        spec1.get("exit_conditions", []),
        spec2.get("exit_conditions", [])
    )

    # Parameter range overlap
    param_sim = _calculate_parameter_similarity(spec1, spec2)

    # Weighted average across all dimensions
    return (
        0.30 * indicator_sim +
        0.25 * entry_sim +
        0.25 * exit_sim +
        0.20 * param_sim
    )

def _calculate_indicator_similarity(spec1: dict, spec2: dict) -> float:
    """Calculate indicator similarity including parameter structure."""
    ind1 = spec1.get("indicators", [])
    ind2 = spec2.get("indicators", [])

    if not ind1 or not ind2:
        return 0.0

    # Type overlap (Jaccard)
    types1 = {i["type"] for i in ind1}
    types2 = {i["type"] for i in ind2}
    type_sim = len(types1 & types2) / max(len(types1 | types2), 1)

    # Parameter structure similarity for matching types
    param_sims = []
    for i1 in ind1:
        for i2 in ind2:
            if i1["type"] == i2["type"]:
                p1 = set(i1.get("params", {}).keys())
                p2 = set(i2.get("params", {}).keys())
                if p1 or p2:
                    param_sims.append(len(p1 & p2) / max(len(p1 | p2), 1))

    param_structure_sim = sum(param_sims) / max(len(param_sims), 1) if param_sims else 0.0

    return 0.6 * type_sim + 0.4 * param_structure_sim

def _calculate_condition_similarity(conds1: list, conds2: list) -> float:
    """Calculate condition similarity including operators and thresholds."""
    if not conds1 or not conds2:
        return 0.0

    # Type overlap
    types1 = {c.get("type") for c in conds1}
    types2 = {c.get("type") for c in conds2}
    type_sim = len(types1 & types2) / max(len(types1 | types2), 1)

    # Operator overlap
    ops1 = {c.get("operator") for c in conds1 if c.get("operator")}
    ops2 = {c.get("operator") for c in conds2 if c.get("operator")}
    op_sim = len(ops1 & ops2) / max(len(ops1 | ops2), 1) if (ops1 or ops2) else 0.5

    # Threshold similarity (for conditions with numeric thresholds)
    threshold_sims = []
    for c1 in conds1:
        for c2 in conds2:
            if c1.get("type") == c2.get("type"):
                t1 = c1.get("threshold")
                t2 = c2.get("threshold")
                if t1 is not None and t2 is not None:
                    # Similarity based on relative difference
                    max_val = max(abs(t1), abs(t2), 1)
                    threshold_sims.append(1 - abs(t1 - t2) / max_val)

    threshold_sim = sum(threshold_sims) / len(threshold_sims) if threshold_sims else 0.5

    return 0.4 * type_sim + 0.3 * op_sim + 0.3 * threshold_sim

def _calculate_parameter_similarity(spec1: dict, spec2: dict) -> float:
    """Calculate parameter range overlap."""
    params1 = {p["name"]: p for p in spec1.get("parameters", [])}
    params2 = {p["name"]: p for p in spec2.get("parameters", [])}

    if not params1 or not params2:
        return 0.0

    # Name overlap
    names1 = set(params1.keys())
    names2 = set(params2.keys())
    name_sim = len(names1 & names2) / max(len(names1 | names2), 1)

    # Range overlap for matching parameters
    range_sims = []
    for name in names1 & names2:
        p1, p2 = params1[name], params2[name]
        if p1.get("type") == p2.get("type"):
            # Calculate range overlap ratio
            min1, max1 = p1.get("min", 0), p1.get("max", 100)
            min2, max2 = p2.get("min", 0), p2.get("max", 100)

            overlap_start = max(min1, min2)
            overlap_end = min(max1, max2)
            overlap = max(0, overlap_end - overlap_start)

            union = max(max1, max2) - min(min1, min2)
            range_sims.append(overlap / max(union, 1))

    range_sim = sum(range_sims) / len(range_sims) if range_sims else 0.0

    return 0.4 * name_sim + 0.6 * range_sim

def calculate_embedding_similarity(spec1: dict, spec2: dict) -> float:
    """
    Calculate semantic similarity using text embeddings.

    Converts spec structure to natural language description and computes
    cosine similarity of embeddings.
    """
    desc1 = _spec_to_description(spec1)
    desc2 = _spec_to_description(spec2)

    embeddings = _embedding_model.encode([desc1, desc2])
    cosine_sim = float(embeddings[0] @ embeddings[1]) / (
        np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
    )

    return cosine_sim

def _spec_to_description(spec: dict) -> str:
    """Convert spec to natural language description for embedding."""
    parts = [f"Strategy {spec.get('name', 'unknown')}"]

    # Indicators
    indicators = [i["type"] for i in spec.get("indicators", [])]
    if indicators:
        parts.append(f"uses indicators: {', '.join(indicators)}")

    # Entry conditions
    entries = spec.get("entry_conditions", [])
    if entries:
        entry_desc = ", ".join(
            f"{c.get('type')} {c.get('operator', '')} {c.get('threshold', '')}"
            for c in entries
        )
        parts.append(f"enters when: {entry_desc}")

    # Exit conditions
    exits = spec.get("exit_conditions", [])
    if exits:
        exit_desc = ", ".join(
            f"{c.get('type')} {c.get('operator', '')} {c.get('threshold', '')}"
            for c in exits
        )
        parts.append(f"exits when: {exit_desc}")

    return ". ".join(parts)
```

## LLM Output Parsing and Retry

### Structured Output Parsing

The Learning Agent uses structured output parsing with retry logic to handle
malformed LLM responses gracefully.

```python
import json
import re
import asyncio
from typing import Optional

MAX_PARSE_RETRIES = 3
PARSE_RETRY_DELAY_SECONDS = 1

async def parse_llm_spec_output(
    raw_output: str,
    llm_client,
    original_prompt: str
) -> tuple[list[dict], list[str]]:
    """
    Parse LLM output into validated specs with retry logic.

    Returns:
        (parsed_specs, parse_errors)
    """
    specs = []
    errors = []

    for attempt in range(MAX_PARSE_RETRIES):
        try:
            # Try multiple extraction strategies
            parsed = _extract_specs_from_output(raw_output)

            if parsed:
                specs = parsed
                break

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            errors.append(f"Attempt {attempt + 1}: {str(e)}")

            if attempt < MAX_PARSE_RETRIES - 1:
                # Request reformatted output from LLM
                raw_output = await _request_reformat(
                    llm_client,
                    raw_output,
                    str(e),
                    original_prompt
                )
                await asyncio.sleep(PARSE_RETRY_DELAY_SECONDS)

    return specs, errors

def _extract_specs_from_output(raw_output: str) -> list[dict]:
    """
    Try multiple strategies to extract specs from LLM output.

    Strategies (in order):
    1. Direct JSON array parsing
    2. JSON code block extraction
    3. YAML code block extraction
    4. Markdown structured extraction
    """
    # Strategy 1: Direct JSON array
    try:
        parsed = json.loads(raw_output)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "specs" in parsed:
            return parsed["specs"]
    except json.JSONDecodeError:
        pass

    # Strategy 2: JSON code blocks
    json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', raw_output)
    for block in json_blocks:
        try:
            parsed = json.loads(block)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            continue

    # Strategy 3: YAML code blocks
    yaml_blocks = re.findall(r'```ya?ml\s*([\s\S]*?)\s*```', raw_output)
    for block in yaml_blocks:
        try:
            import yaml
            parsed = yaml.safe_load(block)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except yaml.YAMLError:
            continue

    # Strategy 4: Markdown structured extraction
    return _extract_from_markdown(raw_output)

def _extract_from_markdown(raw_output: str) -> list[dict]:
    """Extract specs from markdown-formatted output."""
    specs = []

    # Split by spec headers (## Spec N: or ## NEW_STRATEGY_NAME)
    spec_sections = re.split(r'\n##\s+(?:Spec\s+\d+:|[A-Z][A-Z0-9_]+)\s*\n', raw_output)

    for section in spec_sections[1:]:  # Skip intro text
        spec = {}

        # Extract name
        name_match = re.search(r'\*\*Name\*\*:\s*([A-Z][A-Z0-9_]+)', section)
        if name_match:
            spec["name"] = name_match.group(1)

        # Extract indicators
        ind_match = re.search(r'\*\*Indicators\*\*:\s*([\s\S]*?)(?:\*\*|$)', section)
        if ind_match:
            spec["indicators"] = _parse_indicator_list(ind_match.group(1))

        # Extract entry conditions
        entry_match = re.search(r'\*\*Entry\*\*:\s*(.+)', section)
        if entry_match:
            spec["entry_conditions"] = _parse_condition(entry_match.group(1))

        # Extract exit conditions
        exit_match = re.search(r'\*\*Exit\*\*:\s*(.+)', section)
        if exit_match:
            spec["exit_conditions"] = _parse_condition(exit_match.group(1))

        # Extract parameters
        param_match = re.search(r'\*\*Parameters\*\*:\s*([\s\S]*?)(?:\*\*|---|\n\n|$)', section)
        if param_match:
            spec["parameters"] = _parse_parameters(param_match.group(1))

        if spec.get("name") and spec.get("indicators"):
            specs.append(spec)

    return specs

async def _request_reformat(
    llm_client,
    malformed_output: str,
    error_message: str,
    original_prompt: str
) -> str:
    """Request LLM to reformat malformed output."""
    reformat_prompt = f"""
Your previous output could not be parsed. Error: {error_message}

Please reformat your response as a valid JSON array of spec objects.
Each spec must have: name, indicators, entry_conditions, exit_conditions, parameters.

Original request: {original_prompt[:500]}...

Your previous (malformed) output:
{malformed_output[:1000]}...

Provide ONLY the corrected JSON array, no explanation:
"""

    response = await llm_client.complete(
        prompt=reformat_prompt,
        max_tokens=2000,
        temperature=0.1  # Low temperature for structured output
    )

    return response.text
```

## Spec Validation

### Schema Validation

```python
SPEC_SCHEMA = {
    "type": "object",
    "required": ["name", "indicators", "entry_conditions", "exit_conditions", "parameters"],
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[A-Z][A-Z0-9_]{2,49}$"
        },
        "description": {"type": "string", "maxLength": 500},
        "indicators": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "output_name"],
                "properties": {
                    "type": {"enum": SUPPORTED_INDICATORS},
                    "output_name": {"type": "string"},
                    "params": {"type": "object"}
                }
            }
        },
        "entry_conditions": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/definitions/condition"}
        },
        "exit_conditions": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/definitions/condition"}
        },
        "parameters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type", "min", "max"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"enum": ["INTEGER", "DECIMAL"]},
                    "min": {"type": "number"},
                    "max": {"type": "number"},
                    "default": {"type": "number"}
                }
            }
        }
    }
}

SUPPORTED_INDICATORS = [
    "RSI", "MACD", "EMA", "SMA", "BOLLINGER",
    "ATR", "ADX", "STOCHASTIC", "VOLUME", "OBV"
]

def validate_spec(spec: dict) -> tuple[bool, list[str]]:
    """Validate spec against schema."""
    errors = []

    try:
        jsonschema.validate(spec, SPEC_SCHEMA)
    except jsonschema.ValidationError as e:
        errors.append(str(e.message))

    # Additional semantic validation
    param_names = {p["name"] for p in spec.get("parameters", [])}

    # Check all parameter references exist
    for indicator in spec.get("indicators", []):
        for param_name, param_value in indicator.get("params", {}).items():
            if isinstance(param_value, str) and param_value.startswith("${"):
                ref_name = param_value[2:-1]
                if ref_name not in param_names:
                    errors.append(f"Parameter reference '{ref_name}' not defined")

    return len(errors) == 0, errors
```

### Spec Quality Validation

Beyond schema validation, specs are validated for quality criteria:

```python
QUALITY_THRESHOLDS = {
    "min_indicators": 1,
    "max_indicators": 5,
    "min_conditions": 1,
    "max_conditions": 10,
    "min_parameters": 1,
    "max_parameters": 15,
    "min_param_range_ratio": 1.5,  # max/min must be at least 1.5x
    "max_param_range_ratio": 100,  # max/min must be at most 100x
}

def validate_spec_quality(spec: dict) -> tuple[bool, list[str]]:
    """
    Validate spec meets quality criteria beyond schema compliance.

    Checks:
    - Reasonable number of indicators/conditions/parameters
    - Parameter ranges are neither too narrow nor too wide
    - No redundant conditions
    - Indicators are actually used in conditions
    """
    errors = []

    # Indicator count check
    ind_count = len(spec.get("indicators", []))
    if ind_count < QUALITY_THRESHOLDS["min_indicators"]:
        errors.append(f"Too few indicators: {ind_count}")
    if ind_count > QUALITY_THRESHOLDS["max_indicators"]:
        errors.append(f"Too many indicators: {ind_count}")

    # Condition count check
    entry_count = len(spec.get("entry_conditions", []))
    exit_count = len(spec.get("exit_conditions", []))
    total_conditions = entry_count + exit_count

    if total_conditions < QUALITY_THRESHOLDS["min_conditions"]:
        errors.append(f"Too few conditions: {total_conditions}")
    if total_conditions > QUALITY_THRESHOLDS["max_conditions"]:
        errors.append(f"Too many conditions: {total_conditions}")

    # Parameter range check
    for param in spec.get("parameters", []):
        min_val = param.get("min", 0)
        max_val = param.get("max", 100)

        if min_val <= 0:
            range_ratio = max_val  # Avoid division by zero
        else:
            range_ratio = max_val / min_val

        if range_ratio < QUALITY_THRESHOLDS["min_param_range_ratio"]:
            errors.append(f"Parameter '{param['name']}' range too narrow: {min_val}-{max_val}")
        if range_ratio > QUALITY_THRESHOLDS["max_param_range_ratio"]:
            errors.append(f"Parameter '{param['name']}' range too wide: {min_val}-{max_val}")

    # Check indicators are used in conditions
    indicator_outputs = {i.get("output_name") for i in spec.get("indicators", [])}
    condition_refs = set()

    for cond in spec.get("entry_conditions", []) + spec.get("exit_conditions", []):
        if "indicator" in cond:
            condition_refs.add(cond["indicator"])

    unused_indicators = indicator_outputs - condition_refs
    if unused_indicators:
        errors.append(f"Unused indicators: {unused_indicators}")

    return len(errors) == 0, errors
```

## GA Feedback Loop

### Tracking Generation Source Performance

The Learning Agent tracks which generated specs succeed in GA optimization and
uses this feedback to improve future generation.

```python
async def get_generation_feedback(db) -> dict:
    """
    Analyze performance of previously generated specs.

    Returns stats on LLM-generated specs vs other sources to guide
    future generation decisions.
    """
    stats = await db.fetch("""
        SELECT
            source,
            COUNT(*) as total_specs,
            COUNT(*) FILTER (WHERE status = 'VALIDATED') as validated_count,
            COUNT(*) FILTER (WHERE status = 'DEPLOYED') as deployed_count,
            AVG(best_sharpe) FILTER (WHERE best_sharpe IS NOT NULL) as avg_sharpe,
            AVG(best_accuracy) FILTER (WHERE best_accuracy IS NOT NULL) as avg_accuracy
        FROM strategy_specs
        WHERE created_at >= NOW() - INTERVAL '30 days'
        GROUP BY source
    """)

    # Calculate success rates by source
    feedback = {}
    for row in stats:
        feedback[row["source"]] = {
            "total": row["total_specs"],
            "validated": row["validated_count"],
            "deployed": row["deployed_count"],
            "validation_rate": row["validated_count"] / max(row["total_specs"], 1),
            "deployment_rate": row["deployed_count"] / max(row["total_specs"], 1),
            "avg_sharpe": row["avg_sharpe"],
            "avg_accuracy": row["avg_accuracy"]
        }

    return feedback

async def get_successful_patterns(db) -> list[dict]:
    """
    Identify patterns from LLM-generated specs that succeeded.

    Returns common indicator combinations, condition types, and parameter
    ranges from specs that achieved VALIDATED or DEPLOYED status.
    """
    successful_specs = await db.fetch("""
        SELECT spec_definition
        FROM strategy_specs
        WHERE source = 'LLM_GENERATED'
          AND status IN ('VALIDATED', 'DEPLOYED')
          AND best_sharpe >= 1.5
        ORDER BY best_sharpe DESC
        LIMIT 20
    """)

    patterns = {
        "indicator_combos": {},
        "condition_types": {},
        "param_ranges": {}
    }

    for row in successful_specs:
        spec = row["spec_definition"]

        # Track indicator combinations
        indicators = tuple(sorted(i["type"] for i in spec.get("indicators", [])))
        patterns["indicator_combos"][indicators] = \
            patterns["indicator_combos"].get(indicators, 0) + 1

        # Track condition types
        for cond in spec.get("entry_conditions", []) + spec.get("exit_conditions", []):
            ctype = cond.get("type")
            if ctype:
                patterns["condition_types"][ctype] = \
                    patterns["condition_types"].get(ctype, 0) + 1

    return patterns

async def get_failed_patterns(db) -> list[dict]:
    """
    Identify patterns from LLM-generated specs that failed.

    Returns common patterns to AVOID in future generation.
    """
    failed_specs = await db.fetch("""
        SELECT spec_definition
        FROM strategy_specs
        WHERE source = 'LLM_GENERATED'
          AND (status = 'REJECTED' OR (status = 'CANDIDATE' AND
               created_at < NOW() - INTERVAL '7 days'))
        ORDER BY created_at DESC
        LIMIT 50
    """)

    # Track patterns that correlate with failure
    failed_patterns = {
        "indicator_combos": {},
        "condition_types": {}
    }

    for row in failed_specs:
        spec = row["spec_definition"]
        indicators = tuple(sorted(i["type"] for i in spec.get("indicators", [])))
        failed_patterns["indicator_combos"][indicators] = \
            failed_patterns["indicator_combos"].get(indicators, 0) + 1

    return failed_patterns
```

### Adaptive Generation

```python
async def build_generation_context(db) -> dict:
    """
    Build context for LLM generation that includes feedback from GA results.
    """
    feedback = await get_generation_feedback(db)
    successful = await get_successful_patterns(db)
    failed = await get_failed_patterns(db)

    llm_stats = feedback.get("LLM_GENERATED", {})

    context = {
        "generation_stats": {
            "total_generated": llm_stats.get("total", 0),
            "validation_rate": llm_stats.get("validation_rate", 0),
            "deployment_rate": llm_stats.get("deployment_rate", 0),
            "avg_sharpe": llm_stats.get("avg_sharpe", 0)
        },
        "successful_patterns": {
            "top_indicator_combos": sorted(
                successful["indicator_combos"].items(),
                key=lambda x: -x[1]
            )[:5],
            "top_condition_types": sorted(
                successful["condition_types"].items(),
                key=lambda x: -x[1]
            )[:5]
        },
        "patterns_to_avoid": {
            "failed_indicator_combos": [
                combo for combo, count in failed["indicator_combos"].items()
                if count >= 3  # Failed 3+ times
            ]
        }
    }

    return context

FEEDBACK_PROMPT_SECTION = """
## Learning from Previous Generations

Your previously generated specs have the following track record:
- Total generated: {total_generated}
- Validation rate: {validation_rate:.0%}
- Deployment rate: {deployment_rate:.0%}
- Average Sharpe: {avg_sharpe:.2f}

### Patterns that have worked well:
{successful_patterns}

### Patterns to AVOID (have failed multiple times):
{failed_patterns}

Use this feedback to guide your generation. Favor patterns similar to successful
ones and avoid patterns similar to failed ones.
"""
```

## Rate Limiting

```python
LEARNING_AGENT_LIMITS = {
    "max_specs_per_run": 5,
    "min_top_performer_sharpe": 1.5,  # Only learn from high performers
    "cooldown_hours_per_spec_type": 24,  # Don't spam similar specs
    "max_specs_per_day": 10
}

async def check_generation_limits(db) -> tuple[bool, str]:
    """Check if we can generate more specs."""
    # Check daily limit
    today_count = await db.fetchval("""
        SELECT COUNT(*) FROM strategy_specs
        WHERE source = 'LLM_GENERATED'
          AND created_at >= CURRENT_DATE
    """)

    if today_count >= LEARNING_AGENT_LIMITS["max_specs_per_day"]:
        return False, f"Daily limit reached ({today_count} specs today)"

    return True, None
```

## Configuration

```json
{
  "name": "learning",
  "description": "Generates new strategy specs from top performers",
  "model": "anthropic/claude-sonnet-4.5",
  "mcp_servers": {
    "strategy-db-mcp": {
      "command": "python",
      "args": ["-m", "mcp_servers.strategy_db_mcp"],
      "env": {
        "DATABASE_URL": "${POSTGRES_URL}"
      }
    }
  },
  "skills_dir": "./skills",
  "schedule": "0 */6 * * *",
  "limits": {
    "timeout_seconds": 300,
    "max_specs_per_run": 5,
    "min_top_performer_sharpe": 1.5
  },
  "feedback": {
    "enabled": true,
    "lookback_days": 30,
    "min_failed_count_to_avoid": 3
  }
}
```

## Skills

### few-shot-spec-generation/SKILL.md

```markdown
# Skill: Few-Shot Spec Generation

## Purpose
Generate new strategy specifications using top performers as examples.

## When to Use
- During scheduled Learning Agent runs (every 6 hours)
- When strategy library needs expansion
- When GA has exhausted current spec parameter space

## Workflow
1. Fetch top 10 specs with get_top_specs()
2. For each spec, get top 5 implementations
3. Fetch feedback on previously generated specs
4. Analyze patterns across successful strategies
5. Generate 1-5 new specs that build on successful patterns
6. Validate each spec structure and quality
7. Check for duplicates
8. Submit valid, unique specs

## Output
New strategy specs in JSON format, ready for database insertion.

## Constraints
- Only use supported indicators
- Must include reasoning for each spec
- Must pass validation before submission
- Should avoid patterns that have historically failed
```

### analyze-performance-patterns/SKILL.md

```markdown
# Skill: Analyze Performance Patterns

## Purpose
Identify patterns that correlate with strategy success.

## Analysis Dimensions
1. **Indicator Combinations**: Which indicators appear together in top specs?
2. **Condition Types**: What entry/exit conditions work best?
3. **Parameter Ranges**: What ranges tend to produce best results?
4. **Market Regimes**: Which strategies work in which conditions?
5. **Generation Source**: How do LLM-generated specs compare to others?

## Output
Pattern analysis summary to inform spec generation.
```

## Acceptance Criteria

- [ ] Agent retrieves top performers via strategy-db-mcp
- [ ] LLM generates valid spec YAML/JSON
- [ ] LLM output parsing handles malformed responses with retry
- [ ] Spec validation catches structural errors
- [ ] Spec quality validation catches poor-quality specs
- [ ] Duplicate detection uses embedding-based similarity
- [ ] Duplicate detection considers parameter ranges and thresholds
- [ ] New specs saved with source='LLM_GENERATED'
- [ ] Reasoning stored with each spec
- [ ] Rate limiting prevents spec spam
- [ ] Schedule runs every 6 hours
- [ ] Metrics track specs generated, validated, submitted
- [ ] GA feedback loop tracks generation_source correlation
- [ ] Successful/failed patterns inform future generation

## Metrics

- `learning_agent_specs_generated` - Total specs generated
- `learning_agent_specs_validated` - Specs that passed validation
- `learning_agent_specs_submitted` - Specs saved to database
- `learning_agent_specs_duplicate` - Specs rejected as duplicates
- `learning_agent_parse_retries` - LLM output parsing retries needed
- `learning_agent_run_duration_seconds` - Time per run
- `learning_agent_feedback_validation_rate` - Validation rate of LLM specs
- `learning_agent_feedback_deployment_rate` - Deployment rate of LLM specs

## File Structure

```
agents/learning/
├── .opencode/
│   └── config.json
├── skills/
│   ├── few-shot-spec-generation/
│   │   └── SKILL.md
│   ├── analyze-performance-patterns/
│   │   └── SKILL.md
│   └── validate-spec-structure/
│       └── SKILL.md
├── prompts/
│   ├── system.md
│   └── few_shot_examples.md
└── tests/
    ├── test_spec_validation.py
    ├── test_duplicate_detection.py
    ├── test_llm_parsing.py
    └── test_feedback_loop.py
```
