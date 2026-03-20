-- V5.2__decision_outcomes.sql
-- Separate outcomes table to avoid write contention on agent_decisions.

CREATE TABLE IF NOT EXISTS decision_outcomes (
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_decision_outcomes_decision
    ON decision_outcomes(decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_recorded
    ON decision_outcomes(recorded_at DESC);

-- Agent sessions table
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    source VARCHAR(50),  -- web, telegram, slack, api
    started_at TIMESTAMP DEFAULT NOW(),
    last_activity_at TIMESTAMP DEFAULT NOW(),
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
    feedback_type VARCHAR(20),  -- helpful, not_helpful, incorrect, executed
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_decision ON decision_feedback(decision_id);
