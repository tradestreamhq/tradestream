-- V5__agent_decisions.sql
-- Main agent decisions table and B-tree indexes.

CREATE TABLE IF NOT EXISTS agent_decisions (
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
    opportunity_factors JSONB,

    -- Input context
    query TEXT,  -- User question (NULL for autonomous)
    symbols_analyzed TEXT[],

    -- Reasoning and analysis
    reasoning TEXT NOT NULL,
    strategy_breakdown JSONB,
    market_context JSONB,

    -- Tool execution trace
    tool_calls JSONB NOT NULL,

    -- Validation (from Portfolio Advisor)
    validation_status VARCHAR(20),  -- valid, invalid, warning
    validation_warnings TEXT[],
    max_position_size DECIMAL(20,8),

    -- Model and performance
    model_used VARCHAR(100),
    agent_type VARCHAR(50),
    latency_ms INTEGER,
    tokens_input INTEGER,
    tokens_output INTEGER,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,

    -- Outcome tracking (filled in later)
    outcome_recorded BOOLEAN DEFAULT FALSE,
    actual_return DECIMAL(8,4),
    hit_target BOOLEAN
);

-- B-tree indexes for common queries
CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol ON agent_decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created ON agent_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_opportunity ON agent_decisions(opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_action ON agent_decisions(action);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_session ON agent_decisions(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agent_decisions_user ON agent_decisions(user_id) WHERE user_id IS NOT NULL;

-- Composite index for dashboard queries
CREATE INDEX IF NOT EXISTS idx_agent_decisions_dashboard ON agent_decisions(
    created_at DESC,
    opportunity_score DESC
) WHERE action IN ('BUY', 'SELL');
