# Janitor Agent Specification

## Goal

OpenCode agent that evaluates strategies for retirement based on sustained poor performance, cleaning up the strategy library while preserving historical data and protecting canonical strategies.

## Why Not Hard Numbers?

A fixed "remove bottom N" approach doesn't work because:
- Market conditions change (a strategy may recover)
- New specs need time to prove themselves
- Some strategies only work in specific market conditions
- Strategy performance naturally degrades over time (alpha decay)

Instead, we use **nuanced criteria** that consider multiple factors.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  JANITOR AGENT (OpenCode)                                  │
│                                                             │
│  Schedule: Daily at 3:00 AM UTC                            │
│  Model: Gemini 3.0 Pro (evaluation requires judgment)      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ MCP Tools                                            │   │
│  │  • strategy-db-mcp:                                  │   │
│  │    - get_retirement_candidates()                     │   │
│  │    - get_implementation_history(impl_id)            │   │
│  │    - retire_implementation(impl_id, reason)         │   │
│  │    - get_better_alternatives(spec_id, symbol)       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Skills                                               │   │
│  │  • evaluate-performance                             │   │
│  │  • recommend-retirement                             │   │
│  │  • generate-retirement-report                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Output: Retirement decisions + daily report               │
└─────────────────────────────────────────────────────────────┘
```

## Retirement Criteria

### Implementation Retirement

**All criteria must be true for retirement:**

```python
def should_retire_implementation(impl: Implementation) -> tuple[bool, str]:
    """
    Evaluate if an implementation should be retired.

    Returns:
        (should_retire, reason)
    """
    # Criterion 1: Enough data to judge
    if impl.forward_trades < 100:
        return False, "Insufficient signals (< 100)"

    if impl.age_days < 180:
        return False, "Too young (< 6 months)"

    # Criterion 2: Consistently poor performance
    if impl.forward_sharpe >= 0.5:
        return False, f"Sharpe acceptable ({impl.forward_sharpe:.2f})"

    if impl.forward_accuracy >= 0.45:
        return False, f"Accuracy acceptable ({impl.forward_accuracy:.0%})"

    # Criterion 3: Not improving
    if impl.sharpe_trend != "DECLINING":
        return False, f"Performance not declining ({impl.sharpe_trend})"

    # Criterion 4: Better alternatives exist
    better_exists = check_better_alternatives(
        impl.spec_id,
        impl.symbol,
        min_sharpe=1.0
    )
    if not better_exists:
        return False, "No better alternatives available"

    # All criteria met
    reason = (
        f"Retired: Sharpe={impl.forward_sharpe:.2f}, "
        f"Accuracy={impl.forward_accuracy:.0%}, "
        f"Trend={impl.sharpe_trend}, "
        f"Age={impl.age_days}d, "
        f"Signals={impl.forward_trades}"
    )
    return True, reason
```

### Spec Retirement

**Only retire a spec if ALL implementations are retired AND spec is not CANONICAL:**

```python
def should_retire_spec(spec: Spec) -> tuple[bool, str]:
    """
    Evaluate if a spec should be retired.

    CANONICAL specs are NEVER retired.
    """
    # Protection: Never retire original 70 specs
    if spec.source == "CANONICAL":
        return False, "CANONICAL specs protected from retirement"

    # Get all implementations
    impls = get_implementations(spec.spec_id)

    if len(impls) == 0:
        return False, "No implementations to evaluate"

    # Check if all are retired
    active_impls = [i for i in impls if i.status != "RETIRED"]
    if active_impls:
        return False, f"{len(active_impls)} active implementations remain"

    # All implementations retired, safe to retire spec
    return True, "All implementations retired"
```

## Retirement Workflow

### 1. Identify Candidates

```sql
-- Get implementations that might need retirement
SELECT
    i.impl_id,
    s.name as spec_name,
    s.source,
    i.symbol,
    i.forward_sharpe,
    i.forward_accuracy,
    i.forward_trades,
    EXTRACT(DAY FROM NOW() - i.created_at) as age_days,
    calculate_sharpe_trend(i.impl_id) as sharpe_trend
FROM strategy_implementations i
JOIN strategy_specs s ON i.spec_id = s.spec_id
WHERE i.status = 'VALIDATED'
  AND i.forward_trades >= 100
  AND EXTRACT(DAY FROM NOW() - i.created_at) >= 180
  AND (i.forward_sharpe < 0.5 OR i.forward_accuracy < 0.45)
ORDER BY i.forward_sharpe ASC
LIMIT 100;
```

### 2. Evaluate Each Candidate

For each candidate, the Janitor Agent:
1. Checks all retirement criteria
2. Verifies better alternatives exist
3. Reviews performance trend
4. Makes retirement recommendation with reasoning

### 3. Execute Retirements

```python
async def execute_retirement(
    impl_id: str,
    reason: str,
    agent_reasoning: str
) -> bool:
    """
    Retire an implementation (soft delete).
    """
    # Update status
    await db.execute("""
        UPDATE strategy_implementations
        SET status = 'RETIRED',
            updated_at = NOW()
        WHERE impl_id = $1
    """, impl_id)

    # Log retirement decision
    await db.execute("""
        INSERT INTO retirement_log
        (impl_id, reason, agent_reasoning, retired_at)
        VALUES ($1, $2, $3, NOW())
    """, impl_id, reason, agent_reasoning)

    # Check if spec should also be retired
    spec_id = await get_spec_id(impl_id)
    spec = await get_spec(spec_id)

    should_retire, spec_reason = should_retire_spec(spec)
    if should_retire:
        await retire_spec(spec_id, spec_reason)

    return True
```

### 4. Generate Report

```markdown
# Janitor Agent Daily Report
Date: 2026-02-01

## Summary
- Implementations evaluated: 47
- Implementations retired: 12
- Specs retired: 2
- CANONICAL specs protected: 3 (evaluated but protected)

## Retirements

### Implementations Retired

| Spec | Symbol | Sharpe | Accuracy | Signals | Age | Reason |
|------|--------|--------|----------|---------|-----|--------|
| RSI_MOMENTUM_v2 | BTC/USD | 0.23 | 41% | 234 | 8mo | Declining performance |
| MACD_REVERSAL_v3 | ETH/USD | 0.31 | 43% | 189 | 7mo | Better alternatives exist |
...

### Specs Retired

| Spec | Source | Implementations | Reason |
|------|--------|-----------------|--------|
| RSI_MOMENTUM_v2 | LLM_GENERATED | 3 (all retired) | All implementations underperformed |
| TRIPLE_EMA_v1 | LLM_GENERATED | 2 (all retired) | Failed to validate |

### Protected (CANONICAL)

| Spec | Note |
|------|------|
| RSI_REVERSAL | Original spec, some implementations underperforming but protected |
| MACD_CROSSOVER | Original spec, protected |

## Recommendations
- Consider adjusting RSI_REVERSAL parameters for BTC/USD
- LLM-generated specs showing 60% retirement rate - may need prompt tuning
```

## Database Schema Additions

```sql
-- Retirement log for auditing
CREATE TABLE retirement_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    impl_id UUID REFERENCES strategy_implementations(impl_id),
    spec_id UUID REFERENCES strategy_specs(spec_id),
    retirement_type VARCHAR(20) NOT NULL,  -- implementation, spec
    reason TEXT NOT NULL,
    agent_reasoning TEXT,
    retired_at TIMESTAMP DEFAULT NOW(),
    can_reactivate BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_retirement_log_impl ON retirement_log(impl_id);
CREATE INDEX idx_retirement_log_spec ON retirement_log(spec_id);
CREATE INDEX idx_retirement_log_date ON retirement_log(retired_at DESC);

-- Sharpe trend calculation function
CREATE OR REPLACE FUNCTION calculate_sharpe_trend(p_impl_id UUID)
RETURNS VARCHAR(20) AS $$
DECLARE
    trend_slope DECIMAL;
BEGIN
    -- Calculate slope of monthly Sharpe ratios
    SELECT regr_slope(sharpe, month_num) INTO trend_slope
    FROM (
        SELECT
            EXTRACT(MONTH FROM signal_timestamp) +
            EXTRACT(YEAR FROM signal_timestamp) * 12 as month_num,
            -- Simplified Sharpe calculation per month
            AVG(return_pct) / NULLIF(STDDEV(return_pct), 0) as sharpe
        FROM implementation_signals
        WHERE impl_id = p_impl_id
          AND signal_type = 'forward_test'
        GROUP BY 1
        ORDER BY 1
    ) monthly_sharpe;

    IF trend_slope IS NULL THEN
        RETURN 'INSUFFICIENT_DATA';
    ELSIF trend_slope < -0.02 THEN
        RETURN 'DECLINING';
    ELSIF trend_slope > 0.02 THEN
        RETURN 'IMPROVING';
    ELSE
        RETURN 'STABLE';
    END IF;
END;
$$ LANGUAGE plpgsql;
```

## Configuration

```json
{
  "name": "janitor",
  "description": "Retires underperforming strategies",
  "model": "google/gemini-3.0-pro",
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
  "schedule": "0 3 * * *",
  "limits": {
    "timeout_seconds": 600,
    "max_retirements_per_run": 50
  },
  "criteria": {
    "min_signals": 100,
    "min_age_days": 180,
    "max_sharpe": 0.5,
    "max_accuracy": 0.45,
    "required_trend": "DECLINING",
    "require_better_alternative": true,
    "min_alternative_sharpe": 1.0
  },
  "protection": {
    "canonical_specs": true,
    "grace_period_days": 180
  }
}
```

## Skills

### evaluate-performance/SKILL.md

```markdown
# Skill: Evaluate Performance

## Purpose
Evaluate strategy implementation performance for potential retirement.

## Evaluation Factors
1. **Sharpe Ratio**: Risk-adjusted return (threshold: 0.5)
2. **Accuracy**: Win rate on signals (threshold: 45%)
3. **Signal Count**: Minimum 100 forward-test signals
4. **Age**: Minimum 6 months since creation
5. **Trend**: Performance trajectory (declining = retire)
6. **Alternatives**: Better options must exist

## Output
Retirement recommendation with reasoning for each candidate.
```

### recommend-retirement/SKILL.md

```markdown
# Skill: Recommend Retirement

## Purpose
Make nuanced retirement recommendations considering edge cases.

## Edge Cases to Consider
- Seasonal strategies (may underperform in certain periods)
- Market regime changes (strategy may recover)
- Recent parameter changes (need time to evaluate)
- Symbol-specific issues (may work better on other symbols)

## Output
Final retirement decision with detailed reasoning.
```

### generate-retirement-report/SKILL.md

```markdown
# Skill: Generate Retirement Report

## Purpose
Create daily summary of retirement activities for review.

## Report Sections
1. Summary statistics
2. Detailed retirement list with reasons
3. Protected specs (CANONICAL that would otherwise retire)
4. Recommendations for strategy improvements
5. Metrics trends over time

## Format
Markdown report suitable for Slack/email distribution.
```

## Protections

### CANONICAL Spec Protection

```python
def is_protected(spec: Spec) -> bool:
    """
    Check if spec is protected from retirement.
    """
    # Original 70 specs are always protected
    if spec.source == "CANONICAL":
        return True

    # Add other protection rules as needed
    return False
```

### Grace Period

- All strategies get 6-month minimum before evaluation
- Recently modified strategies get additional 30-day grace period
- User-favorited strategies get additional review before retirement

### Soft Delete

- Retired strategies are marked status='RETIRED', not deleted
- Historical data preserved for analysis
- Can be reactivated if market conditions change

## Acceptance Criteria

- [ ] Retirement criteria prevent premature removal
- [ ] CANONICAL specs protected from retirement
- [ ] Soft delete preserves history
- [ ] Retirement reasoning logged for each decision
- [ ] Summary report generated daily
- [ ] Better alternatives check works correctly
- [ ] Sharpe trend calculation accurate
- [ ] Schedule runs daily at 3:00 AM UTC
- [ ] Max 50 retirements per run (prevent runaway)

## Metrics

- `janitor_candidates_evaluated` - Implementations checked
- `janitor_implementations_retired` - Implementations retired
- `janitor_specs_retired` - Specs retired
- `janitor_canonical_protected` - CANONICAL specs that would have retired
- `janitor_run_duration_seconds` - Time per run

## File Structure

```
agents/janitor/
├── .opencode/
│   └── config.json
├── skills/
│   ├── evaluate-performance/
│   │   └── SKILL.md
│   ├── recommend-retirement/
│   │   └── SKILL.md
│   └── generate-retirement-report/
│       └── SKILL.md
├── prompts/
│   └── system.md
└── tests/
    ├── test_retirement_criteria.py
    └── test_canonical_protection.py
```
