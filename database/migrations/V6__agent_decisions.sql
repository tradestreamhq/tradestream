-- V6__agent_decisions.sql
-- Agent decision tracking table for AI-driven signal scoring

CREATE TABLE agent_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id) ON DELETE SET NULL,
    score DECIMAL(5,2),
    tier VARCHAR(20) CHECK (tier IN ('HOT','GOOD','NEUTRAL','LOW')),
    reasoning TEXT,
    tool_calls JSONB,
    model_used VARCHAR(100),
    latency_ms INTEGER,
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_decisions_created_at ON agent_decisions(created_at);
CREATE INDEX idx_agent_decisions_signal_id ON agent_decisions(signal_id);
