-- V11__add_strategy_versions.sql
-- Add strategy version tracking table for parameter change history and rollback

CREATE TABLE IF NOT EXISTS strategy_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,

    -- Full snapshot of strategy state at this version
    parameters JSONB NOT NULL,
    indicators JSONB NOT NULL,
    entry_conditions JSONB NOT NULL,
    exit_conditions JSONB NOT NULL,

    -- Audit fields
    changed_by VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    change_reason TEXT,

    UNIQUE (strategy_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_strategy_versions_strategy_id ON strategy_versions(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_versions_changed_at ON strategy_versions(changed_at);

-- Auto-create a version snapshot when strategy_specs is updated
CREATE OR REPLACE FUNCTION create_strategy_version()
RETURNS TRIGGER AS $$
DECLARE
    next_version INTEGER;
BEGIN
    -- Only create version if tracked fields actually changed
    IF OLD.parameters IS DISTINCT FROM NEW.parameters
       OR OLD.indicators IS DISTINCT FROM NEW.indicators
       OR OLD.entry_conditions IS DISTINCT FROM NEW.entry_conditions
       OR OLD.exit_conditions IS DISTINCT FROM NEW.exit_conditions
    THEN
        SELECT COALESCE(MAX(version_number), 0) + 1
        INTO next_version
        FROM strategy_versions
        WHERE strategy_id = NEW.id;

        INSERT INTO strategy_versions
            (strategy_id, version_number, parameters, indicators,
             entry_conditions, exit_conditions, changed_by, change_reason)
        VALUES
            (NEW.id, next_version, NEW.parameters, NEW.indicators,
             NEW.entry_conditions, NEW.exit_conditions, 'system', 'auto-versioned on update');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER strategy_specs_version_trigger
    AFTER UPDATE ON strategy_specs
    FOR EACH ROW
    EXECUTE FUNCTION create_strategy_version();
