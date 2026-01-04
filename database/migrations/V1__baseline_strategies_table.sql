-- V1__baseline_strategies_table.sql
-- Baseline migration capturing existing Strategies table schema
-- This migration establishes the starting point for the migration framework

-- Strategy discoveries table - stores GA-discovered trading strategies
CREATE TABLE IF NOT EXISTS Strategies (
    strategy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR NOT NULL,
    strategy_type VARCHAR NOT NULL,
    parameters JSONB NOT NULL,
    first_discovered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_evaluated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    current_score DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    strategy_hash VARCHAR UNIQUE NOT NULL,
    discovery_symbol VARCHAR,
    discovery_start_time TIMESTAMP,
    discovery_end_time TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_strategies_symbol ON Strategies(symbol);
CREATE INDEX IF NOT EXISTS idx_strategies_strategy_type ON Strategies(strategy_type);
CREATE INDEX IF NOT EXISTS idx_strategies_current_score ON Strategies(current_score);
CREATE INDEX IF NOT EXISTS idx_strategies_is_active ON Strategies(is_active);
CREATE INDEX IF NOT EXISTS idx_strategies_discovery_symbol ON Strategies(discovery_symbol);
CREATE INDEX IF NOT EXISTS idx_strategies_created_at ON Strategies(created_at);
