-- V11__add_strategy_versions.sql
-- Add strategy version history for audit trail and rollback support

CREATE TABLE IF NOT EXISTS strategy_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    config_snapshot JSONB NOT NULL,       -- Full snapshot of strategy config at this version
    change_description TEXT,              -- Human-readable description of what changed
    created_by VARCHAR(255),              -- User or system that created this version
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE(strategy_id, version_number)
);

-- Indexes for strategy_versions
CREATE INDEX IF NOT EXISTS idx_strategy_versions_strategy_id ON strategy_versions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_versions_created_at ON strategy_versions(created_at);
