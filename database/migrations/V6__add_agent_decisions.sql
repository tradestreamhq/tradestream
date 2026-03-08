-- V6__add_agent_decisions.sql
-- Add agent_decisions table for tracking AI agent decision history
-- Supports signal-mcp service for decision logging

CREATE TABLE IF NOT EXISTS agent_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    score DECIMAL(10,4),
    tier VARCHAR(50),
    reasoning TEXT,
    tool_calls JSONB,
    model_used VARCHAR(100),
    latency_ms INTEGER,
    tokens_used INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for agent_decisions
CREATE INDEX IF NOT EXISTS idx_agent_decisions_signal_id ON agent_decisions(signal_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created_at ON agent_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_tier ON agent_decisions(tier);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_model ON agent_decisions(model_used);
