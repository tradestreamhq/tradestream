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
```

### 2. Analyze Patterns

The agent identifies common patterns across top performers:
- Indicator combinations that work together
- Entry/exit condition types that correlate with success
- Parameter ranges that tend to perform well
- Market regimes where certain patterns excel

### 3. Generate New Specs

Using few-shot prompting with top performers as examples, generate novel specs that:
- Combine successful elements in new ways
- Explore variations on proven patterns
- Fill gaps in the strategy library

### 4. Validate and Submit

- Check spec structure is valid
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

## Your Goal
Generate 1-5 NEW strategy specs that:
1. Follow the same structural format as the examples
2. Are genuinely novel (not duplicates or minor variations)
3. Build on patterns that work in the top performers
4. Have clear reasoning for why they should work

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

```python
async def check_spec_similarity(
    new_spec: dict,
    existing_specs: list[dict],
    threshold: float = 0.85
) -> tuple[bool, str]:
    """
    Check if new spec is too similar to existing specs.

    Returns:
        (is_duplicate, reason)
    """
    for existing in existing_specs:
        similarity = calculate_spec_similarity(new_spec, existing)
        if similarity > threshold:
            return True, f"Too similar to {existing['name']} ({similarity:.0%})"

    return False, None

def calculate_spec_similarity(spec1: dict, spec2: dict) -> float:
    """
    Calculate similarity between two specs based on:
    - Indicator overlap
    - Condition structure similarity
    - Parameter range overlap
    """
    # Indicator similarity
    ind1 = {i["type"] for i in spec1["indicators"]}
    ind2 = {i["type"] for i in spec2["indicators"]}
    indicator_sim = len(ind1 & ind2) / max(len(ind1 | ind2), 1)

    # Entry condition similarity (simplified)
    entry1 = {c["type"] for c in spec1["entry_conditions"]}
    entry2 = {c["type"] for c in spec2["entry_conditions"]}
    entry_sim = len(entry1 & entry2) / max(len(entry1 | entry2), 1)

    # Weighted average
    return 0.5 * indicator_sim + 0.5 * entry_sim
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
3. Analyze patterns across successful strategies
4. Generate 1-5 new specs that build on successful patterns
5. Validate each spec structure
6. Check for duplicates
7. Submit valid, unique specs

## Output
New strategy specs in JSON format, ready for database insertion.

## Constraints
- Only use supported indicators
- Must include reasoning for each spec
- Must pass validation before submission
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

## Output
Pattern analysis summary to inform spec generation.
```

## Acceptance Criteria

- [ ] Agent retrieves top performers via strategy-db-mcp
- [ ] LLM generates valid spec YAML/JSON
- [ ] Spec validation catches structural errors
- [ ] Duplicate detection prevents near-identical specs
- [ ] New specs saved with source='LLM_GENERATED'
- [ ] Reasoning stored with each spec
- [ ] Rate limiting prevents spec spam
- [ ] Schedule runs every 6 hours
- [ ] Metrics track specs generated, validated, submitted

## Metrics

- `learning_agent_specs_generated` - Total specs generated
- `learning_agent_specs_validated` - Specs that passed validation
- `learning_agent_specs_submitted` - Specs saved to database
- `learning_agent_specs_duplicate` - Specs rejected as duplicates
- `learning_agent_run_duration_seconds` - Time per run

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
    └── test_duplicate_detection.py
```
