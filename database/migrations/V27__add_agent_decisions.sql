-- Agent decisions table for persisting autonomous signal generation decisions
-- with full reasoning chains, tool call traces, and risk check results.

CREATE TABLE IF NOT EXISTS agent_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID,
    user_id UUID,
    symbol VARCHAR(50) NOT NULL,
    action VARCHAR(20) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    opportunity_score DECIMAL(5,2) NOT NULL DEFAULT 0,
    opportunity_tier VARCHAR(20),
    opportunity_factors JSONB,
    query TEXT,
    symbols_analyzed TEXT[],
    reasoning TEXT NOT NULL,
    strategy_breakdown JSONB,
    market_context JSONB,
    tool_calls JSONB NOT NULL DEFAULT '{"calls":[]}'::jsonb,
    validation_status VARCHAR(20),
    validation_warnings TEXT[],
    max_position_size DECIMAL(20,8),
    model_used VARCHAR(100),
    agent_type VARCHAR(50),
    latency_ms INTEGER,
    tokens_input INTEGER,
    tokens_output INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP,
    outcome_recorded BOOLEAN DEFAULT FALSE,
    actual_return DECIMAL(8,4),
    hit_target BOOLEAN,

    -- Autonomous pipeline fields
    risk_approved BOOLEAN DEFAULT FALSE,
    risk_rejection_reasons TEXT[],
    position_size_pct DECIMAL(5,2) DEFAULT 0,
    fusion_agreement_ratio DECIMAL(5,4) DEFAULT 0,
    conflict_resolution VARCHAR(50),
    source_signals JSONB
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

-- GIN indexes for JSONB containment queries
CREATE INDEX IF NOT EXISTS idx_agent_decisions_tool_calls_gin ON agent_decisions USING GIN (tool_calls jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_strategy_breakdown_gin ON agent_decisions USING GIN (strategy_breakdown jsonb_path_ops);

-- Decision outcomes table (separated to avoid write contention)
CREATE TABLE IF NOT EXISTS decision_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(decision_id),
    actual_return DECIMAL(8,4),
    hit_target BOOLEAN,
    exit_price DECIMAL(20,8),
    exit_timestamp TIMESTAMP,
    max_drawdown DECIMAL(8,4),
    time_to_target_ms INTEGER,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    recorded_by VARCHAR(50)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_decision_outcomes_decision ON decision_outcomes(decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_recorded ON decision_outcomes(recorded_at DESC);

-- Agent sessions table
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    source VARCHAR(50),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMP NOT NULL DEFAULT NOW(),
    decisions_count INTEGER DEFAULT 0,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON agent_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_activity ON agent_sessions(last_activity_at DESC);

-- Decision feedback table (for learning)
CREATE TABLE IF NOT EXISTS decision_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(decision_id),
    user_id UUID,
    feedback_type VARCHAR(20),
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_decision ON decision_feedback(decision_id);
