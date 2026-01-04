-- V2__add_strategy_specs.sql
-- Add strategy specification tables for config-based strategy definitions
-- Supports #1462 (Config-Based Strategies) and #1488 (ConfigurableStrategyFactory)

-- Strategy specifications - defines strategy structure (indicators, rules, parameters)
CREATE TABLE IF NOT EXISTS strategy_specs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    version INTEGER DEFAULT 1,
    description TEXT,
    complexity VARCHAR(50), -- 'simple', 'moderate', 'complex'

    -- Strategy definition
    indicators JSONB NOT NULL,        -- Indicator configurations
    entry_conditions JSONB NOT NULL,  -- Entry rule definitions
    exit_conditions JSONB NOT NULL,   -- Exit rule definitions
    parameters JSONB NOT NULL,        -- Parameter definitions with ranges

    -- Provenance tracking
    source VARCHAR(50) NOT NULL,      -- 'MIGRATED', 'LLM_GENERATED', 'USER_CREATED'
    source_citation TEXT,             -- Reference URL or book citation
    parent_spec_id UUID REFERENCES strategy_specs(id), -- For derived specs

    -- Metadata
    tags TEXT[],
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for strategy_specs
CREATE INDEX IF NOT EXISTS idx_strategy_specs_name ON strategy_specs(name);
CREATE INDEX IF NOT EXISTS idx_strategy_specs_source ON strategy_specs(source);
CREATE INDEX IF NOT EXISTS idx_strategy_specs_is_active ON strategy_specs(is_active);
CREATE INDEX IF NOT EXISTS idx_strategy_specs_created_at ON strategy_specs(created_at);
CREATE INDEX IF NOT EXISTS idx_strategy_specs_tags ON strategy_specs USING GIN(tags);

-- Strategy implementations - optimized parameter sets for a spec
CREATE TABLE IF NOT EXISTS strategy_implementations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,

    -- Implementation details
    parameters JSONB NOT NULL,          -- Resolved parameter values
    discovered_by VARCHAR(50) NOT NULL, -- 'GA', 'MANUAL', 'LLM', 'GRID_SEARCH'
    generation INTEGER,                 -- GA generation number if applicable

    -- Performance metrics (summary)
    backtest_metrics JSONB,    -- Summary metrics from backtesting
    paper_metrics JSONB,       -- Summary metrics from paper trading
    live_metrics JSONB,        -- Summary metrics from live trading

    -- Status and lifecycle
    status VARCHAR(20) NOT NULL DEFAULT 'CANDIDATE',  -- 'CANDIDATE', 'VALIDATED', 'DEPLOYED', 'RETIRED'
    deployed_at TIMESTAMP,
    retired_at TIMESTAMP,

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for strategy_implementations
CREATE INDEX IF NOT EXISTS idx_strategy_impl_spec_id ON strategy_implementations(spec_id);
CREATE INDEX IF NOT EXISTS idx_strategy_impl_discovered_by ON strategy_implementations(discovered_by);
CREATE INDEX IF NOT EXISTS idx_strategy_impl_status ON strategy_implementations(status);
CREATE INDEX IF NOT EXISTS idx_strategy_impl_created_at ON strategy_implementations(created_at);

-- Trigger to update updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_strategy_specs_updated_at
    BEFORE UPDATE ON strategy_specs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategy_implementations_updated_at
    BEFORE UPDATE ON strategy_implementations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
