-- Learning Engine tables for historical performance self-reflection.
-- Tracks decision outcomes, performance patterns, and bias detection.

CREATE TABLE decision_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES agent_decisions(id),
    instrument VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    entry_price DECIMAL,
    exit_price DECIMAL,
    exit_timestamp TIMESTAMP WITH TIME ZONE,
    pnl_absolute DECIMAL,
    pnl_percent DECIMAL,
    hold_duration INTERVAL,
    exit_reason VARCHAR,
    market_context JSONB,
    lessons_learned TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_decision_outcomes_decision_id ON decision_outcomes(decision_id);
CREATE INDEX idx_decision_outcomes_instrument ON decision_outcomes(instrument);
CREATE INDEX idx_decision_outcomes_action ON decision_outcomes(action);
CREATE INDEX idx_decision_outcomes_created_at ON decision_outcomes(created_at);

CREATE TABLE performance_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_type VARCHAR NOT NULL,
    instrument VARCHAR,
    description TEXT NOT NULL,
    frequency INTEGER DEFAULT 0,
    avg_pnl_impact DECIMAL,
    mitigation_strategy TEXT,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_performance_patterns_type ON performance_patterns(pattern_type);
CREATE INDEX idx_performance_patterns_instrument ON performance_patterns(instrument);
