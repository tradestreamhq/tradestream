# Agent Decisions Schema Specification

## Goal

Database schema for persisting agent decisions and reasoning traces, enabling historical analysis, debugging, and user review of all agent activity.

## Schema

### Main Table: agent_decisions

```sql
CREATE TABLE agent_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session context (NULL for autonomous runs)
    session_id UUID,
    user_id UUID,

    -- Signal identification
    symbol VARCHAR(50) NOT NULL,
    action VARCHAR(20) NOT NULL,  -- BUY, SELL, HOLD

    -- Confidence and scoring
    confidence DECIMAL(5,4) NOT NULL,  -- 0.0000 - 1.0000
    opportunity_score DECIMAL(5,2) NOT NULL,  -- 0.00 - 100.00
    opportunity_tier VARCHAR(20),  -- HOT, GOOD, NEUTRAL, LOW
    opportunity_factors JSONB,  -- Breakdown of score factors

    -- Input context
    query TEXT,  -- User question (NULL for autonomous)
    symbols_analyzed TEXT[],  -- All symbols in this batch

    -- Reasoning and analysis
    reasoning TEXT NOT NULL,  -- LLM-generated reasoning summary
    strategy_breakdown JSONB,  -- Individual strategy signals
    market_context JSONB,  -- Price, volume, volatility at decision time

    -- Tool execution trace
    tool_calls JSONB NOT NULL,  -- Full tool call/result trace

    -- Validation (from Portfolio Advisor)
    validation_status VARCHAR(20),  -- valid, invalid, warning
    validation_warnings TEXT[],
    max_position_size DECIMAL(20,8),

    -- Model and performance
    model_used VARCHAR(100),  -- e.g., "google/gemini-3.0-flash"
    agent_type VARCHAR(50),  -- signal-generator, portfolio-advisor, etc.
    latency_ms INTEGER,
    tokens_input INTEGER,
    tokens_output INTEGER,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,  -- For TTL if needed

    -- Outcome tracking (filled in later)
    outcome_recorded BOOLEAN DEFAULT FALSE,
    actual_return DECIMAL(8,4),
    hit_target BOOLEAN
);

-- Indexes for common queries
CREATE INDEX idx_agent_decisions_symbol ON agent_decisions(symbol);
CREATE INDEX idx_agent_decisions_created ON agent_decisions(created_at DESC);
CREATE INDEX idx_agent_decisions_opportunity ON agent_decisions(opportunity_score DESC);
CREATE INDEX idx_agent_decisions_action ON agent_decisions(action);
CREATE INDEX idx_agent_decisions_session ON agent_decisions(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_agent_decisions_user ON agent_decisions(user_id) WHERE user_id IS NOT NULL;

-- Composite index for dashboard queries
CREATE INDEX idx_agent_decisions_dashboard ON agent_decisions(
    created_at DESC,
    opportunity_score DESC
) WHERE action IN ('BUY', 'SELL');

-- GIN indexes for JSONB queries (tool call analysis, strategy filtering)
CREATE INDEX idx_agent_decisions_tool_calls_gin ON agent_decisions USING GIN (tool_calls jsonb_path_ops);
CREATE INDEX idx_agent_decisions_strategy_breakdown_gin ON agent_decisions USING GIN (strategy_breakdown jsonb_path_ops);
```

### JSONB Size Constraints

To prevent unbounded JSONB growth and ensure predictable query performance:

| Field | Max Size | Enforcement |
|-------|----------|-------------|
| `tool_calls` | 100KB | Application-level validation |
| `strategy_breakdown` | 50KB | Application-level validation |
| `opportunity_factors` | 10KB | Application-level validation |
| `market_context` | 10KB | Application-level validation |

**Tool Calls Limits:**
- Maximum 50 tool calls per decision
- Each tool call result truncated to 5KB if larger
- Large results should reference external storage (S3/GCS) via URL

```python
MAX_TOOL_CALLS = 50
MAX_TOOL_CALL_RESULT_SIZE = 5 * 1024  # 5KB
MAX_TOOL_CALLS_TOTAL_SIZE = 100 * 1024  # 100KB

def validate_tool_calls(tool_calls: dict) -> dict:
    """Validate and truncate tool calls to fit size constraints."""
    calls = tool_calls.get("calls", [])

    if len(calls) > MAX_TOOL_CALLS:
        calls = calls[:MAX_TOOL_CALLS]
        tool_calls["truncated"] = True
        tool_calls["original_count"] = len(calls)

    for call in calls:
        result = json.dumps(call.get("result", {}))
        if len(result) > MAX_TOOL_CALL_RESULT_SIZE:
            call["result"] = {"truncated": True, "size": len(result)}

    tool_calls["calls"] = calls
    return tool_calls
```

### Tool Calls JSONB Structure

```json
{
  "calls": [
    {
      "id": "call_001",
      "tool": "get_top_strategies",
      "server": "strategy-mcp",
      "parameters": {
        "symbol": "ETH/USD",
        "limit": 5
      },
      "result": {
        "strategies": [
          {"id": "strat_abc", "name": "RSI_REVERSAL", "score": 0.89},
          {"id": "strat_def", "name": "MACD_CROSS", "score": 0.85}
        ]
      },
      "latency_ms": 45,
      "timestamp": "2026-02-01T12:34:56.123Z"
    },
    {
      "id": "call_002",
      "tool": "get_strategy_signal",
      "server": "strategy-mcp",
      "parameters": {
        "strategy_id": "strat_abc",
        "symbol": "ETH/USD"
      },
      "result": {
        "signal": "BUY",
        "confidence": 0.85,
        "triggered_at": "2026-02-01T12:34:00Z"
      },
      "latency_ms": 32,
      "timestamp": "2026-02-01T12:34:56.200Z"
    }
  ],
  "total_latency_ms": 77,
  "tools_called": ["get_top_strategies", "get_strategy_signal"]
}
```

### Opportunity Factors JSONB Structure

```json
{
  "confidence": {
    "value": 0.82,
    "normalized": 0.82,
    "contribution": 20.5,
    "weight": 0.25
  },
  "expected_return": {
    "value": 0.032,
    "normalized": 0.64,
    "contribution": 19.2,
    "weight": 0.30
  },
  "consensus": {
    "value": 0.80,
    "normalized": 0.80,
    "contribution": 16.0,
    "weight": 0.20
  },
  "volatility": {
    "value": 0.021,
    "normalized": 0.70,
    "contribution": 10.5,
    "weight": 0.15
  },
  "freshness": {
    "value": 2,
    "normalized": 0.97,
    "contribution": 9.7,
    "weight": 0.10
  },
  "total_score": 75.9
}
```

### Strategy Breakdown JSONB Structure

```json
{
  "strategies_analyzed": 5,
  "strategies_bullish": 4,
  "strategies_bearish": 1,
  "strategies_neutral": 0,
  "breakdown": [
    {
      "strategy_id": "strat_abc",
      "name": "RSI_REVERSAL",
      "signal": "BUY",
      "score": 0.89,
      "confidence": 0.85,
      "parameters": {"rsiPeriod": 14, "oversold": 30}
    },
    {
      "strategy_id": "strat_def",
      "name": "MACD_CROSS",
      "signal": "BUY",
      "score": 0.85,
      "confidence": 0.78
    }
  ],
  "top_strategy": "RSI_REVERSAL"
}
```

### Market Context JSONB Structure

```json
{
  "current_price": 2450.50,
  "price_change_1h": 0.023,
  "price_change_24h": 0.045,
  "volume_24h": 15000000000,
  "volume_ratio": 1.45,
  "volatility_1h": 0.018,
  "volatility_24h": 0.032,
  "timestamp": "2026-02-01T12:34:56Z"
}
```

## Supporting Tables

### Agent Sessions

```sql
CREATE TABLE agent_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    source VARCHAR(50),  -- web, telegram, slack, api
    started_at TIMESTAMP DEFAULT NOW(),
    last_activity_at TIMESTAMP DEFAULT NOW(),
    decisions_count INTEGER DEFAULT 0,
    metadata JSONB
);

CREATE INDEX idx_sessions_user ON agent_sessions(user_id);
CREATE INDEX idx_sessions_activity ON agent_sessions(last_activity_at DESC);
```

### Decision Outcomes (separated for write contention)

To avoid row-level contention when updating outcome data on existing decisions, outcomes are tracked in a separate table:

```sql
CREATE TABLE decision_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(decision_id),

    -- Outcome data (filled in by scheduled job)
    actual_return DECIMAL(8,4),
    hit_target BOOLEAN,
    exit_price DECIMAL(20,8),
    exit_timestamp TIMESTAMP,

    -- Performance metrics
    max_drawdown DECIMAL(8,4),
    time_to_target_ms INTEGER,

    -- Metadata
    recorded_at TIMESTAMP DEFAULT NOW(),
    recorded_by VARCHAR(50)  -- 'outcome-tracker-job', 'manual', etc.
);

CREATE UNIQUE INDEX idx_decision_outcomes_decision ON decision_outcomes(decision_id);
CREATE INDEX idx_decision_outcomes_recorded ON decision_outcomes(recorded_at DESC);
```

**Benefits of Separate Table:**
- Insert-only pattern avoids row locks on agent_decisions
- Allows multiple outcome snapshots if needed
- Cleaner separation of concerns (decision vs. outcome)
- Better cache behavior for read-heavy decision queries

### Decision Feedback (for learning)

```sql
CREATE TABLE decision_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(decision_id),
    user_id UUID,
    feedback_type VARCHAR(20),  -- helpful, not_helpful, incorrect, executed
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_feedback_decision ON decision_feedback(decision_id);
```

## Query Performance Optimization

### Index Strategy Summary

| Query Pattern | Index Used | Expected Performance |
|---------------|------------|---------------------|
| Dashboard (recent + high opportunity) | `idx_agent_decisions_dashboard` | < 10ms |
| By symbol | `idx_agent_decisions_symbol` | < 5ms |
| By time range | `idx_agent_decisions_created` | < 20ms |
| Tool call analysis (JSONB) | `idx_agent_decisions_tool_calls_gin` | < 50ms |
| Strategy containment queries | `idx_agent_decisions_strategy_breakdown_gin` | < 50ms |

### GIN Index Usage Examples

```sql
-- Find decisions that used a specific tool (uses GIN index)
SELECT * FROM agent_decisions
WHERE tool_calls @> '{"tools_called": ["get_top_strategies"]}';

-- Find decisions with specific strategy in breakdown
SELECT * FROM agent_decisions
WHERE strategy_breakdown @> '{"top_strategy": "RSI_REVERSAL"}';

-- Find decisions where a specific tool was called
SELECT * FROM agent_decisions
WHERE tool_calls->'calls' @> '[{"tool": "get_strategy_signal"}]';
```

### Query Optimization Tips

1. **Always include time bounds** - Partitioning and indexes work best with `created_at` filters
2. **Use JSONB containment** - `@>` operator uses GIN index, `->>'key'` does not
3. **Avoid SELECT *** - Fetch only needed columns, especially for large JSONB fields
4. **Paginate results** - Use `LIMIT` and cursor-based pagination for large result sets

## Queries

### Get Recent Decisions for Dashboard

```sql
SELECT
    decision_id,
    symbol,
    action,
    confidence,
    opportunity_score,
    opportunity_tier,
    reasoning,
    strategy_breakdown,
    created_at
FROM agent_decisions
WHERE created_at >= NOW() - INTERVAL '24 hours'
  AND action IN ('BUY', 'SELL')
ORDER BY opportunity_score DESC, created_at DESC
LIMIT 50;
```

### Get Decisions by Symbol

```sql
SELECT *
FROM agent_decisions
WHERE symbol = $1
  AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC
LIMIT 20;
```

### Get High-Opportunity Decisions

```sql
SELECT *
FROM agent_decisions
WHERE opportunity_score >= 80
  AND created_at >= NOW() - INTERVAL '1 hour'
ORDER BY opportunity_score DESC;
```

### Analyze Tool Call Performance

```sql
SELECT
    tool_call->>'tool' as tool_name,
    AVG((tool_call->>'latency_ms')::int) as avg_latency_ms,
    COUNT(*) as call_count
FROM agent_decisions,
     jsonb_array_elements(tool_calls->'calls') as tool_call
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY tool_call->>'tool'
ORDER BY avg_latency_ms DESC;
```

### Track Model Usage

```sql
SELECT
    model_used,
    agent_type,
    COUNT(*) as decisions,
    AVG(latency_ms) as avg_latency_ms,
    SUM(tokens_input) as total_input_tokens,
    SUM(tokens_output) as total_output_tokens
FROM agent_decisions
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY model_used, agent_type
ORDER BY decisions DESC;
```

### Outcome Tracking Query

```sql
-- Calculate accuracy for recent decisions (using separate outcomes table)
SELECT
    d.symbol,
    d.action,
    COUNT(*) as total_decisions,
    COUNT(*) FILTER (WHERE o.hit_target = TRUE) as correct_decisions,
    COUNT(*) FILTER (WHERE o.hit_target = TRUE)::float / COUNT(*) as accuracy,
    AVG(o.actual_return) as avg_return,
    AVG(o.max_drawdown) as avg_drawdown
FROM agent_decisions d
JOIN decision_outcomes o ON d.decision_id = o.decision_id
WHERE d.created_at >= NOW() - INTERVAL '30 days'
GROUP BY d.symbol, d.action
ORDER BY accuracy DESC;
```

## Migration

```sql
-- V5__agent_decisions.sql

-- Main decisions table
CREATE TABLE IF NOT EXISTS agent_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID,
    user_id UUID,
    symbol VARCHAR(50) NOT NULL,
    action VARCHAR(20) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    opportunity_score DECIMAL(5,2) NOT NULL,
    opportunity_tier VARCHAR(20),
    opportunity_factors JSONB,
    query TEXT,
    symbols_analyzed TEXT[],
    reasoning TEXT NOT NULL,
    strategy_breakdown JSONB,
    market_context JSONB,
    tool_calls JSONB NOT NULL,
    validation_status VARCHAR(20),
    validation_warnings TEXT[],
    max_position_size DECIMAL(20,8),
    model_used VARCHAR(100),
    agent_type VARCHAR(50),
    latency_ms INTEGER,
    tokens_input INTEGER,
    tokens_output INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    outcome_recorded BOOLEAN DEFAULT FALSE,
    actual_return DECIMAL(8,4),
    hit_target BOOLEAN
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol ON agent_decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created ON agent_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_opportunity ON agent_decisions(opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_action ON agent_decisions(action);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_session ON agent_decisions(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_decisions_user ON agent_decisions(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_decisions_dashboard ON agent_decisions(created_at DESC, opportunity_score DESC) WHERE action IN ('BUY', 'SELL');

-- GIN indexes for JSONB queries
CREATE INDEX IF NOT EXISTS idx_agent_decisions_tool_calls_gin ON agent_decisions USING GIN (tool_calls jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_strategy_breakdown_gin ON agent_decisions USING GIN (strategy_breakdown jsonb_path_ops);

-- Decision outcomes table (separated from main table to avoid write contention)
CREATE TABLE IF NOT EXISTS decision_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(decision_id),
    actual_return DECIMAL(8,4),
    hit_target BOOLEAN,
    exit_price DECIMAL(20,8),
    exit_timestamp TIMESTAMP,
    max_drawdown DECIMAL(8,4),
    time_to_target_ms INTEGER,
    recorded_at TIMESTAMP DEFAULT NOW(),
    recorded_by VARCHAR(50)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_decision_outcomes_decision ON decision_outcomes(decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_recorded ON decision_outcomes(recorded_at DESC);

-- Sessions table
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    source VARCHAR(50),
    started_at TIMESTAMP DEFAULT NOW(),
    last_activity_at TIMESTAMP DEFAULT NOW(),
    decisions_count INTEGER DEFAULT 0,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON agent_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_activity ON agent_sessions(last_activity_at DESC);

-- Feedback table
CREATE TABLE IF NOT EXISTS decision_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(decision_id),
    user_id UUID,
    feedback_type VARCHAR(20),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_decision ON decision_feedback(decision_id);
```

## API Integration

### Save Decision

```python
async def save_decision(decision: AgentDecision, db) -> str:
    """Save agent decision to database."""
    decision_id = await db.fetchval("""
        INSERT INTO agent_decisions
        (session_id, user_id, symbol, action, confidence, opportunity_score,
         opportunity_tier, opportunity_factors, query, reasoning,
         strategy_breakdown, market_context, tool_calls, model_used,
         agent_type, latency_ms, tokens_input, tokens_output)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        RETURNING decision_id
    """,
        decision.session_id,
        decision.user_id,
        decision.symbol,
        decision.action,
        decision.confidence,
        decision.opportunity_score,
        decision.opportunity_tier,
        json.dumps(decision.opportunity_factors),
        decision.query,
        decision.reasoning,
        json.dumps(decision.strategy_breakdown),
        json.dumps(decision.market_context),
        json.dumps(decision.tool_calls),
        decision.model_used,
        decision.agent_type,
        decision.latency_ms,
        decision.tokens_input,
        decision.tokens_output
    )

    return str(decision_id)
```

### Query Decisions

```python
async def get_recent_decisions(
    symbol: Optional[str] = None,
    min_opportunity_score: float = 0,
    limit: int = 50,
    db = None
) -> list[AgentDecision]:
    """Query recent decisions with filters."""
    query = """
        SELECT * FROM agent_decisions
        WHERE created_at >= NOW() - INTERVAL '24 hours'
          AND opportunity_score >= $1
    """
    params = [min_opportunity_score]

    if symbol:
        query += " AND symbol = $2"
        params.append(symbol)

    query += " ORDER BY opportunity_score DESC, created_at DESC LIMIT $" + str(len(params) + 1)
    params.append(limit)

    rows = await db.fetch(query, *params)
    return [AgentDecision.from_row(row) for row in rows]
```

## Acceptance Criteria

- [ ] Migration runs without errors on existing database
- [ ] Indexes support queries by symbol, time range, and opportunity score
- [ ] GIN indexes support JSONB containment queries for tool call analysis
- [ ] Tool calls JSONB supports arbitrary depth with size validation
- [ ] JSONB size limits enforced at application layer
- [ ] Old decisions queryable via API
- [ ] Can query top opportunities: `ORDER BY opportunity_score DESC`
- [ ] Session tracking works for user interactions
- [ ] Feedback table allows user input
- [ ] Outcome tracking uses separate table (no contention with decision inserts)
- [ ] Retention policy automatically archives decisions > 90 days
- [ ] Query performance acceptable (< 100ms for dashboard queries)
- [ ] JSONB queries using GIN index (< 50ms for tool call analysis)

## Retention Policy

### Data Lifecycle

| Age | Storage | Access Pattern |
|-----|---------|----------------|
| 0-30 days | Hot (primary DB) | Real-time queries, dashboards |
| 30-90 days | Warm (primary DB) | Historical analysis, debugging |
| 90-365 days | Cold (archive) | Compliance, audits |
| >365 days | Deleted or long-term archive | Regulatory requirements only |

### Partitioning Strategy

```sql
-- Partition by month for large-scale deployments
CREATE TABLE agent_decisions (
    -- ... columns ...
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE agent_decisions_2026_01 PARTITION OF agent_decisions
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE agent_decisions_2026_02 PARTITION OF agent_decisions
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
```

### Automated Cleanup Job

```sql
-- Run daily: Archive decisions older than 90 days
-- Step 1: Export to cold storage (S3/GCS)
COPY (
    SELECT * FROM agent_decisions
    WHERE created_at < NOW() - INTERVAL '90 days'
) TO PROGRAM 'aws s3 cp - s3://tradestream-archive/decisions/$(date +%Y-%m-%d).csv';

-- Step 2: Delete archived data
DELETE FROM agent_decisions
WHERE created_at < NOW() - INTERVAL '90 days';

-- Step 3: Reclaim space
VACUUM ANALYZE agent_decisions;
```

### Retention Configuration

```yaml
# config/retention.yaml
agent_decisions:
  hot_retention_days: 30
  warm_retention_days: 90
  archive_enabled: true
  archive_destination: s3://tradestream-archive/decisions/
  delete_after_archive: true
  vacuum_after_delete: true
```

## File Structure

```
db/migrations/
├── V5__agent_decisions.sql           # Main table + B-tree indexes
├── V5.1__agent_decisions_gin.sql     # GIN indexes for JSONB
├── V5.2__decision_outcomes.sql       # Separate outcomes table
└── V5.3__agent_decisions_partitions.sql  # Partitioning (optional)

services/decisions_service/
├── __init__.py
├── repository.py
├── models.py
├── queries.py
├── validation.py                     # JSONB size validation
└── retention.py                      # Cleanup/archive jobs

config/
└── retention.yaml                    # Retention policy configuration
```
