-- V7__enhance_agent_decisions.sql
-- Enhance agent_decisions table with full audit trail columns:
-- agent_name, decision_type, input/output context, success tracking,
-- and parent-child decision linking.

-- Make signal_id nullable (not all decisions are tied to a signal)
ALTER TABLE agent_decisions ALTER COLUMN signal_id DROP NOT NULL;

-- Add new columns (all nullable or with defaults for backward compatibility)
ALTER TABLE agent_decisions ADD COLUMN agent_name VARCHAR(100);
ALTER TABLE agent_decisions ADD COLUMN decision_type VARCHAR(100);
ALTER TABLE agent_decisions ADD COLUMN input_context JSONB;
ALTER TABLE agent_decisions ADD COLUMN output JSONB;
ALTER TABLE agent_decisions ADD COLUMN success BOOLEAN DEFAULT true;
ALTER TABLE agent_decisions ADD COLUMN error_message TEXT;
ALTER TABLE agent_decisions ADD COLUMN parent_decision_id UUID REFERENCES agent_decisions(id);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent_name ON agent_decisions(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision_type ON agent_decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_success ON agent_decisions(success);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_parent_id ON agent_decisions(parent_decision_id);
