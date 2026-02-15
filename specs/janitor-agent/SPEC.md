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

| Spec             | Symbol  | Sharpe | Accuracy | Signals | Age | Reason                    |
| ---------------- | ------- | ------ | -------- | ------- | --- | ------------------------- |
| RSI_MOMENTUM_v2  | BTC/USD | 0.23   | 41%      | 234     | 8mo | Declining performance     |
| MACD_REVERSAL_v3 | ETH/USD | 0.31   | 43%      | 189     | 7mo | Better alternatives exist |

...

### Specs Retired

| Spec            | Source        | Implementations | Reason                             |
| --------------- | ------------- | --------------- | ---------------------------------- |
| RSI_MOMENTUM_v2 | LLM_GENERATED | 3 (all retired) | All implementations underperformed |
| TRIPLE_EMA_v1   | LLM_GENERATED | 2 (all retired) | Failed to validate                 |

### Protected (CANONICAL)

| Spec           | Note                                                              |
| -------------- | ----------------------------------------------------------------- |
| RSI_REVERSAL   | Original spec, some implementations underperforming but protected |
| MACD_CROSSOVER | Original spec, protected                                          |

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

## Reactivation Workflow

### When to Reactivate

Retired strategies may be reactivated when:

1. **Market regime change**: Conditions become favorable for the strategy again
2. **Strategy update**: Parameters or logic have been improved
3. **False positive**: Retirement was premature due to data issues
4. **Manual request**: Human operator requests reactivation for testing

### Reactivation Process

```python
async def reactivate_implementation(
    impl_id: str,
    reason: str,
    requester: str
) -> bool:
    """
    Reactivate a retired implementation.
    """
    # Verify implementation is retired and can be reactivated
    impl = await get_implementation(impl_id)
    if impl.status != 'RETIRED':
        raise ValueError(f"Implementation {impl_id} is not retired")

    retirement_log = await get_retirement_log(impl_id)
    if not retirement_log.can_reactivate:
        raise ValueError(f"Implementation {impl_id} is not eligible for reactivation")

    # Update status to VALIDATING (requires fresh validation)
    await db.execute("""
        UPDATE strategy_implementations
        SET status = 'VALIDATING',
            updated_at = NOW()
        WHERE impl_id = $1
    """, impl_id)

    # Log reactivation
    await db.execute("""
        INSERT INTO reactivation_log
        (impl_id, reason, requester, reactivated_at)
        VALUES ($1, $2, $3, NOW())
    """, impl_id, reason, requester)

    return True
```

### Reactivation Criteria

```python
def can_reactivate(impl_id: str) -> tuple[bool, str]:
    """
    Check if an implementation can be reactivated.
    """
    impl = get_implementation(impl_id)
    retirement = get_retirement_log(impl_id)

    # Check reactivation flag
    if not retirement.can_reactivate:
        return False, "Implementation marked as non-reactivatable"

    # Limit reactivation attempts
    reactivation_count = get_reactivation_count(impl_id)
    if reactivation_count >= 2:
        return False, "Maximum reactivation attempts (2) exceeded"

    # Cooling off period after retirement
    days_since_retirement = (now() - retirement.retired_at).days
    if days_since_retirement < 30:
        return False, f"Cooling off period: {30 - days_since_retirement} days remaining"

    return True, "Eligible for reactivation"
```

### Reactivation Database Schema

```sql
-- Reactivation log for tracking
CREATE TABLE reactivation_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    impl_id UUID REFERENCES strategy_implementations(impl_id),
    reason TEXT NOT NULL,
    requester VARCHAR(100) NOT NULL,
    reactivated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_reactivation_log_impl ON reactivation_log(impl_id);
```

## Market Regime Detection

### Regime Types

```python
class MarketRegime(Enum):
    TRENDING_UP = "trending_up"      # Clear uptrend, momentum strategies work
    TRENDING_DOWN = "trending_down"  # Clear downtrend, reversal strategies work
    RANGING = "ranging"              # Sideways, mean-reversion works
    HIGH_VOLATILITY = "high_vol"     # Spikes, volatility strategies work
    LOW_VOLATILITY = "low_vol"       # Calm, carry/yield strategies work
```

### Regime Detection Function

```sql
CREATE OR REPLACE FUNCTION detect_market_regime(
    p_symbol VARCHAR(20),
    p_lookback_days INTEGER DEFAULT 30
)
RETURNS VARCHAR(20) AS $$
DECLARE
    volatility_ratio DECIMAL;
    trend_strength DECIMAL;
BEGIN
    -- Calculate ATR ratio (current vs average) and trend strength
    SELECT
        AVG(CASE WHEN rn <= 5 THEN atr END) / NULLIF(AVG(atr), 0),
        REGR_SLOPE(close_price, row_num)
    INTO volatility_ratio, trend_strength
    FROM (
        SELECT
            atr,
            close_price,
            ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn,
            ROW_NUMBER() OVER (ORDER BY timestamp ASC) as row_num
        FROM market_data
        WHERE symbol = p_symbol
          AND timestamp > NOW() - INTERVAL '1 day' * p_lookback_days
    ) data;

    -- Classify regime
    IF volatility_ratio > 1.5 THEN
        RETURN 'high_vol';
    ELSIF volatility_ratio < 0.5 THEN
        RETURN 'low_vol';
    ELSIF ABS(trend_strength) > 0.02 THEN
        IF trend_strength > 0 THEN
            RETURN 'trending_up';
        ELSE
            RETURN 'trending_down';
        END IF;
    ELSE
        RETURN 'ranging';
    END IF;
END;
$$ LANGUAGE plpgsql;
```

### Regime-Aware Retirement

```python
def should_retire_with_regime(impl: Implementation) -> tuple[bool, str]:
    """
    Consider market regime when evaluating retirement.
    """
    # Get strategy's preferred regime
    strategy_regime = impl.spec.preferred_regime

    # Get current regime for this symbol
    current_regime = detect_market_regime(impl.symbol)

    # If strategy is regime-specific and regime doesn't match,
    # defer retirement decision
    if strategy_regime and strategy_regime != current_regime:
        return False, f"Deferring: Strategy prefers {strategy_regime}, current is {current_regime}"

    # Otherwise, proceed with normal retirement evaluation
    return should_retire_implementation(impl)
```

## Performance Trend Analysis

### Trend Analysis Window Configuration

```python
class TrendAnalysisConfig:
    """Configuration for performance trend analysis."""

    # Minimum months of data required for trend analysis
    MIN_MONTHS_REQUIRED = 3

    # Lookback window for trend calculation (configurable)
    TREND_LOOKBACK_MONTHS = 6

    # Slope thresholds for classification
    DECLINING_THRESHOLD = -0.02  # Monthly Sharpe dropping
    IMPROVING_THRESHOLD = 0.02   # Monthly Sharpe increasing
```

### Updated Trend Calculation with Configurable Window

```sql
-- Updated trend calculation with configurable lookback window
CREATE OR REPLACE FUNCTION calculate_sharpe_trend(
    p_impl_id UUID,
    p_lookback_months INTEGER DEFAULT 6
)
RETURNS VARCHAR(20) AS $$
DECLARE
    trend_slope DECIMAL;
    month_count INTEGER;
BEGIN
    -- Calculate slope of monthly Sharpe ratios over lookback window
    SELECT
        regr_slope(sharpe, month_num),
        COUNT(DISTINCT month_num)
    INTO trend_slope, month_count
    FROM (
        SELECT
            EXTRACT(MONTH FROM signal_timestamp) +
            EXTRACT(YEAR FROM signal_timestamp) * 12 as month_num,
            AVG(return_pct) / NULLIF(STDDEV(return_pct), 0) as sharpe
        FROM implementation_signals
        WHERE impl_id = p_impl_id
          AND signal_type = 'forward_test'
          AND signal_timestamp > NOW() - INTERVAL '1 month' * p_lookback_months
        GROUP BY 1
        ORDER BY 1
    ) monthly_sharpe;

    -- Require minimum 3 months of data
    IF month_count < 3 THEN
        RETURN 'INSUFFICIENT_DATA';
    END IF;

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

## Batch Size Limits

### Safety Limits Configuration

```python
class RetirementLimits:
    """Safety limits for retirement operations."""

    # Maximum implementations to retire per run
    MAX_IMPLEMENTATIONS_PER_RUN = 50

    # Maximum specs to retire per run
    MAX_SPECS_PER_RUN = 10

    # Maximum percentage of active strategies to retire at once
    MAX_RETIREMENT_PERCENTAGE = 10  # Never retire more than 10%

    # Cooldown between batch retirements (hours)
    BATCH_COOLDOWN_HOURS = 24
```

### Batch Enforcement

```python
async def execute_batch_retirement(candidates: list[Implementation]) -> dict:
    """
    Execute retirement with batch limits enforced.
    """
    # Get total active implementations
    total_active = await get_active_implementation_count()
    max_by_percentage = int(total_active * 0.10)  # 10% limit

    # Apply stricter of absolute or percentage limit
    effective_limit = min(
        RetirementLimits.MAX_IMPLEMENTATIONS_PER_RUN,
        max_by_percentage
    )

    retired = []
    skipped = []

    for i, candidate in enumerate(candidates):
        if i >= effective_limit:
            skipped.append({
                'impl_id': candidate.impl_id,
                'reason': f'Batch limit reached ({effective_limit})'
            })
            continue

        success = await execute_retirement(
            candidate.impl_id,
            candidate.retirement_reason,
            candidate.agent_reasoning
        )
        if success:
            retired.append(candidate.impl_id)

    return {
        'retired': retired,
        'skipped': skipped,
        'limit_applied': effective_limit
    }
```

## Report Distribution

### Distribution Channels Configuration

```python
class ReportDistribution:
    """Configuration for report distribution."""

    # Primary storage location
    STORAGE_BUCKET = "gs://tradestream-reports/janitor/"

    # Slack notification settings
    SLACK_CHANNEL = "#strategy-ops"
    SLACK_WEBHOOK_SECRET = "SLACK_JANITOR_WEBHOOK"

    # Email distribution list
    EMAIL_RECIPIENTS = ["strategy-ops@tradestream.io"]

    # Report retention period
    REPORT_RETENTION_DAYS = 90
```

### Distribution Workflow

```python
async def distribute_report(report: JanitorReport) -> dict:
    """
    Distribute daily janitor report to all channels.
    """
    results = {}

    # 1. Store report in GCS (primary storage)
    report_path = f"{ReportDistribution.STORAGE_BUCKET}{report.date}/report.md"
    await storage.upload(report_path, report.to_markdown())
    results['storage'] = report_path

    # 2. Send Slack notification with summary
    slack_message = {
        "channel": ReportDistribution.SLACK_CHANNEL,
        "text": f"*Janitor Report - {report.date}*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary*\n"
                           f"- Evaluated: {report.evaluated_count}\n"
                           f"- Retired: {report.retired_count}\n"
                           f"- Protected: {report.protected_count}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Full Report"},
                        "url": report.public_url
                    }
                ]
            }
        ]
    }
    await slack.post_message(slack_message)
    results['slack'] = ReportDistribution.SLACK_CHANNEL

    # 3. Send email for significant events only
    if report.retired_count > 10 or report.has_warnings:
        await email.send(
            to=ReportDistribution.EMAIL_RECIPIENTS,
            subject=f"[Action Required] Janitor Report - {report.date}",
            body=report.to_html()
        )
        results['email'] = ReportDistribution.EMAIL_RECIPIENTS

    return results
```

### Report Storage Schema

```sql
-- Store reports for historical analysis
CREATE TABLE janitor_reports (
    report_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date DATE NOT NULL UNIQUE,
    evaluated_count INTEGER NOT NULL,
    retired_implementations INTEGER NOT NULL,
    retired_specs INTEGER NOT NULL,
    protected_count INTEGER NOT NULL,
    report_markdown TEXT NOT NULL,
    storage_path VARCHAR(500),
    distributed_to JSONB,  -- {"slack": "#channel", "email": [...], "storage": "gs://..."}
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_janitor_reports_date ON janitor_reports(report_date DESC);
```

## Dependent System Notifications

### Notification Events

When strategies are retired, dependent systems must be notified to update their state:

```python
class RetirementNotifier:
    """Notify dependent systems of retirement events."""

    DEPENDENT_SYSTEMS = [
        "signal-router",      # Stop routing signals from retired strategies
        "portfolio-manager",  # Adjust position allocations
        "alert-system",       # Update alert configurations
        "dashboard",          # Refresh UI state
    ]

    async def notify_retirement(
        self,
        impl_id: str,
        reason: str
    ) -> dict:
        """
        Notify all dependent systems of a retirement.
        """
        notification = {
            "event": "strategy_retired",
            "impl_id": impl_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

        results = {}
        for system in self.DEPENDENT_SYSTEMS:
            try:
                await self.publish_event(system, notification)
                results[system] = "notified"
            except Exception as e:
                results[system] = f"failed: {str(e)}"
                # Log but don't fail retirement
                logger.error(f"Failed to notify {system}: {e}")

        return results

    async def publish_event(self, system: str, notification: dict):
        """Publish to Pub/Sub topic for the system."""
        topic = f"projects/tradestream/topics/{system}-events"
        await pubsub.publish(topic, notification)
```

### Retirement Event Schema

```json
{
  "event": "strategy_retired",
  "impl_id": "uuid",
  "spec_id": "uuid",
  "symbol": "BTC/USD",
  "reason": "Declining performance, better alternatives exist",
  "timestamp": "2026-02-01T03:15:00Z",
  "metadata": {
    "final_sharpe": 0.23,
    "final_accuracy": 0.41,
    "age_days": 245,
    "signal_count": 234
  }
}
```

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
- [ ] Reactivation workflow allows recovery of retired strategies
- [ ] Market regime detection defers retirement for regime-specific strategies
- [ ] Batch limits prevent mass retirement events
- [ ] Report distribution to Slack, email, and GCS storage
- [ ] Dependent systems notified on retirement events

## Metrics

- `janitor_candidates_evaluated` - Implementations checked
- `janitor_implementations_retired` - Implementations retired
- `janitor_specs_retired` - Specs retired
- `janitor_canonical_protected` - CANONICAL specs that would have retired
- `janitor_run_duration_seconds` - Time per run
- `janitor_reactivations` - Strategies reactivated
- `janitor_regime_deferrals` - Retirements deferred due to market regime

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
    ├── test_canonical_protection.py
    ├── test_reactivation.py
    └── test_regime_detection.py
```
