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
-- Calculate accuracy for recent decisions
SELECT
    symbol,
    action,
    COUNT(*) as total_decisions,
    COUNT(*) FILTER (WHERE hit_target = TRUE) as correct_decisions,
    COUNT(*) FILTER (WHERE hit_target = TRUE)::float / COUNT(*) as accuracy,
    AVG(actual_return) as avg_return
FROM agent_decisions
WHERE outcome_recorded = TRUE
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY symbol, action
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
- [ ] Tool calls JSONB supports arbitrary depth
- [ ] Old decisions queryable via API
- [ ] Can query top opportunities: `ORDER BY opportunity_score DESC`
- [ ] Session tracking works for user interactions
- [ ] Feedback table allows user input
- [ ] Outcome tracking fields populated by scheduled job
- [ ] Query performance acceptable (< 100ms for dashboard queries)

## Retention Policy

```sql
-- Optional: Partition by month for large-scale deployments
CREATE TABLE agent_decisions (
    -- ... columns ...
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE agent_decisions_2026_01 PARTITION OF agent_decisions
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- Archive old partitions
-- Decisions older than 90 days can be moved to cold storage
```

## File Structure

```
db/migrations/
├── V5__agent_decisions.sql
└── V5.1__agent_decisions_indexes.sql

services/decisions_service/
├── __init__.py
├── repository.py
├── models.py
└── queries.py
```
