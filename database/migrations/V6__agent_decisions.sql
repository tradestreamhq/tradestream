-- V6__agent_decisions.sql
-- Agent decisions and reasoning traces schema
-- Part of: Agent-First Realtime Dashboard (Issue #1749)

-- ============================================================================
-- AGENT SESSIONS
-- ============================================================================
-- Tracks user sessions across different channels (web, telegram, slack, api)

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

-- ============================================================================
-- AGENT DECISIONS
-- ============================================================================
-- Main table for storing agent decisions with full reasoning traces

CREATE TABLE agent_decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session context (NULL for autonomous runs)
    session_id UUID REFERENCES agent_sessions(session_id),
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

    -- Constraints
    CONSTRAINT chk_action CHECK (action IN ('BUY', 'SELL', 'HOLD')),
    CONSTRAINT chk_confidence CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT chk_opportunity_score CHECK (opportunity_score >= 0 AND opportunity_score <= 100)
);

-- Standard indexes
CREATE INDEX idx_agent_decisions_symbol ON agent_decisions(symbol);
CREATE INDEX idx_agent_decisions_created ON agent_decisions(created_at DESC);
CREATE INDEX idx_agent_decisions_opportunity ON agent_decisions(opportunity_score DESC);
CREATE INDEX idx_agent_decisions_action ON agent_decisions(action);
CREATE INDEX idx_agent_decisions_session ON agent_decisions(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX idx_agent_decisions_user ON agent_decisions(user_id) WHERE user_id IS NOT NULL;

-- Composite index for dashboard queries (recent + high opportunity BUY/SELL)
CREATE INDEX idx_agent_decisions_dashboard ON agent_decisions(
    created_at DESC,
    opportunity_score DESC
) WHERE action IN ('BUY', 'SELL');

-- GIN indexes for JSONB queries (tool call analysis, strategy filtering)
CREATE INDEX idx_agent_decisions_tool_calls_gin ON agent_decisions USING GIN (tool_calls jsonb_path_ops);
CREATE INDEX idx_agent_decisions_strategy_breakdown_gin ON agent_decisions USING GIN (strategy_breakdown jsonb_path_ops);

-- ============================================================================
-- DECISION OUTCOMES
-- ============================================================================
-- Separated from agent_decisions to avoid row-level contention when updating
-- Filled in by scheduled outcome tracker job

CREATE TABLE decision_outcomes (
    outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(decision_id) ON DELETE CASCADE,

    -- Outcome data
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

-- ============================================================================
-- DECISION FEEDBACK
-- ============================================================================
-- User feedback for learning and improvement

CREATE TABLE decision_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(decision_id) ON DELETE CASCADE,
    user_id UUID,
    feedback_type VARCHAR(20),  -- helpful, not_helpful, incorrect, executed
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT chk_feedback_type CHECK (
        feedback_type IN ('helpful', 'not_helpful', 'incorrect', 'executed')
    )
);

CREATE INDEX idx_feedback_decision ON decision_feedback(decision_id);
CREATE INDEX idx_feedback_user ON decision_feedback(user_id) WHERE user_id IS NOT NULL;

-- ============================================================================
-- COMMENTS / DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE agent_decisions IS 'Stores all agent decisions with full reasoning traces for dashboard display and historical analysis';
COMMENT ON TABLE decision_outcomes IS 'Tracks actual outcomes of decisions, separated to avoid write contention';
COMMENT ON TABLE decision_feedback IS 'User feedback on decisions for learning system improvement';
COMMENT ON TABLE agent_sessions IS 'Tracks user sessions across web, telegram, slack, and API channels';

COMMENT ON COLUMN agent_decisions.tool_calls IS 'Full tool call trace as JSONB. Max 50 calls, 100KB total. See SPEC for structure.';
COMMENT ON COLUMN agent_decisions.opportunity_factors IS 'Breakdown of opportunity score calculation. See SPEC for structure.';
COMMENT ON COLUMN agent_decisions.strategy_breakdown IS 'Individual strategy signals and scores. See SPEC for structure.';
