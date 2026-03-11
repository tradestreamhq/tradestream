"""Baseline schema consolidating Flyway V1-V9 migrations.

This migration captures the complete TradeStream database schema as of V9.
On existing databases, stamp this revision without running: alembic stamp 001

Revision ID: 001
Revises: None
Create Date: 2026-03-11

"""

from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Complete schema DDL matching Flyway V1-V9 migrations.
# Uses IF NOT EXISTS / IF NOT EXISTS throughout so this is a no-op on
# databases that already have the schema from Flyway.

UPGRADE_SQL = """
-- =============================================================
-- V1: Strategies table
-- =============================================================
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

CREATE INDEX IF NOT EXISTS idx_strategies_symbol ON Strategies(symbol);
CREATE INDEX IF NOT EXISTS idx_strategies_strategy_type ON Strategies(strategy_type);
CREATE INDEX IF NOT EXISTS idx_strategies_current_score ON Strategies(current_score);
CREATE INDEX IF NOT EXISTS idx_strategies_is_active ON Strategies(is_active);
CREATE INDEX IF NOT EXISTS idx_strategies_discovery_symbol ON Strategies(discovery_symbol);
CREATE INDEX IF NOT EXISTS idx_strategies_created_at ON Strategies(created_at);

-- =============================================================
-- V2: Strategy specs and implementations
-- =============================================================
CREATE TABLE IF NOT EXISTS strategy_specs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    version INTEGER DEFAULT 1,
    description TEXT,
    complexity VARCHAR(50),
    indicators JSONB NOT NULL,
    entry_conditions JSONB NOT NULL,
    exit_conditions JSONB NOT NULL,
    parameters JSONB NOT NULL,
    source VARCHAR(50) NOT NULL,
    source_citation TEXT,
    parent_spec_id UUID REFERENCES strategy_specs(id),
    tags TEXT[],
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_specs_name ON strategy_specs(name);
CREATE INDEX IF NOT EXISTS idx_strategy_specs_source ON strategy_specs(source);
CREATE INDEX IF NOT EXISTS idx_strategy_specs_is_active ON strategy_specs(is_active);
CREATE INDEX IF NOT EXISTS idx_strategy_specs_created_at ON strategy_specs(created_at);
CREATE INDEX IF NOT EXISTS idx_strategy_specs_tags ON strategy_specs USING GIN(tags);

CREATE TABLE IF NOT EXISTS strategy_implementations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    parameters JSONB NOT NULL,
    discovered_by VARCHAR(50) NOT NULL,
    generation INTEGER,
    backtest_metrics JSONB,
    paper_metrics JSONB,
    live_metrics JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'CANDIDATE',
    deployed_at TIMESTAMP,
    retired_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_impl_spec_id ON strategy_implementations(spec_id);
CREATE INDEX IF NOT EXISTS idx_strategy_impl_discovered_by ON strategy_implementations(discovered_by);
CREATE INDEX IF NOT EXISTS idx_strategy_impl_status ON strategy_implementations(status);
CREATE INDEX IF NOT EXISTS idx_strategy_impl_created_at ON strategy_implementations(created_at);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_strategy_specs_updated_at ON strategy_specs;
CREATE TRIGGER update_strategy_specs_updated_at
    BEFORE UPDATE ON strategy_specs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_strategy_implementations_updated_at ON strategy_implementations;
CREATE TRIGGER update_strategy_implementations_updated_at
    BEFORE UPDATE ON strategy_implementations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================
-- V3: Strategy performance
-- =============================================================
CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    implementation_id UUID NOT NULL REFERENCES strategy_implementations(id) ON DELETE CASCADE,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    calmar_ratio DECIMAL(10,4),
    win_rate DECIMAL(5,4),
    profit_factor DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    avg_drawdown DECIMAL(10,4),
    volatility DECIMAL(10,4),
    var_95 DECIMAL(10,4),
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    avg_trade_duration_seconds BIGINT,
    avg_profit_per_trade DECIMAL(20,8),
    total_return DECIMAL(10,4),
    annualized_return DECIMAL(10,4),
    environment VARCHAR(20) NOT NULL,
    instrument VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20),
    raw_metrics JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_perf_impl_id ON strategy_performance(implementation_id);
CREATE INDEX IF NOT EXISTS idx_perf_impl_date ON strategy_performance(implementation_id, period_start);
CREATE INDEX IF NOT EXISTS idx_perf_environment ON strategy_performance(environment);
CREATE INDEX IF NOT EXISTS idx_perf_instrument ON strategy_performance(instrument);
CREATE INDEX IF NOT EXISTS idx_perf_created_at ON strategy_performance(created_at);

-- =============================================================
-- V4: Signals
-- =============================================================
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    spec_id UUID REFERENCES strategy_specs(id) ON DELETE SET NULL,
    implementation_id UUID REFERENCES strategy_implementations(id) ON DELETE SET NULL,
    instrument VARCHAR(50) NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    strength DECIMAL(5,4),
    price DECIMAL(20,8) NOT NULL,
    bid_price DECIMAL(20,8),
    ask_price DECIMAL(20,8),
    volume DECIMAL(20,8),
    stop_loss DECIMAL(20,8),
    take_profit DECIMAL(20,8),
    position_size DECIMAL(10,4),
    outcome VARCHAR(20),
    exit_price DECIMAL(20,8),
    exit_time TIMESTAMP,
    pnl DECIMAL(20,8),
    pnl_percent DECIMAL(10,4),
    notified_at TIMESTAMP,
    notification_channels TEXT[],
    timeframe VARCHAR(20),
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_instrument ON signals(instrument);
CREATE INDEX IF NOT EXISTS idx_signals_instrument_time ON signals(instrument, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_spec_id ON signals(spec_id);
CREATE INDEX IF NOT EXISTS idx_signals_impl_id ON signals(implementation_id);
CREATE INDEX IF NOT EXISTS idx_signals_outcome ON signals(outcome);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_instrument_type_time ON signals(instrument, signal_type, created_at DESC);

-- =============================================================
-- V5: Walk-forward validation
-- =============================================================
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS oos_sharpe DOUBLE PRECISION;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS oos_return DOUBLE PRECISION;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS sharpe_degradation DOUBLE PRECISION;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS oos_sharpe_std_dev DOUBLE PRECISION;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20);
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS wf_windows_count INTEGER;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS validation_rejection_reason TEXT;
ALTER TABLE Strategies ADD COLUMN IF NOT EXISTS validated_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_strategies_validation_status ON Strategies(validation_status);
CREATE INDEX IF NOT EXISTS idx_strategies_validated_approved
    ON Strategies(validation_status, oos_sharpe DESC)
    WHERE validation_status = 'APPROVED';

CREATE TABLE IF NOT EXISTS walk_forward_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES Strategies(strategy_id) ON DELETE CASCADE,
    in_sample_sharpe DOUBLE PRECISION NOT NULL,
    out_of_sample_sharpe DOUBLE PRECISION NOT NULL,
    sharpe_degradation DOUBLE PRECISION NOT NULL,
    oos_sharpe_std_dev DOUBLE PRECISION,
    in_sample_return DOUBLE PRECISION,
    out_of_sample_return DOUBLE PRECISION,
    return_degradation DOUBLE PRECISION,
    train_window_bars INTEGER NOT NULL,
    test_window_bars INTEGER NOT NULL,
    step_bars INTEGER NOT NULL,
    windows_count INTEGER NOT NULL,
    validation_status VARCHAR(20) NOT NULL,
    rejection_reason TEXT,
    window_results JSONB,
    validated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wf_strategy_id ON walk_forward_results(strategy_id);
CREATE INDEX IF NOT EXISTS idx_wf_validated_at ON walk_forward_results(validated_at);
CREATE INDEX IF NOT EXISTS idx_wf_status ON walk_forward_results(validation_status);

-- =============================================================
-- V6: Agent decisions
-- =============================================================
CREATE TABLE IF NOT EXISTS agent_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id) ON DELETE CASCADE,
    score DECIMAL(10,4),
    tier VARCHAR(50),
    reasoning TEXT,
    tool_calls JSONB,
    model_used VARCHAR(100),
    latency_ms INTEGER,
    tokens_used INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_signal_id ON agent_decisions(signal_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created_at ON agent_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_tier ON agent_decisions(tier);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_model ON agent_decisions(model_used);

-- =============================================================
-- V7: Enhanced agent decisions
-- =============================================================
-- Note: signal_id is nullable from V7 onward (handled by V6 CREATE with REFERENCES, no NOT NULL)
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS agent_name VARCHAR(100);
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS decision_type VARCHAR(100);
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS input_context JSONB;
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS output JSONB;
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS success BOOLEAN DEFAULT true;
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS parent_decision_id UUID REFERENCES agent_decisions(id);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent_name ON agent_decisions(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision_type ON agent_decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_success ON agent_decisions(success);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_parent_id ON agent_decisions(parent_decision_id);

-- =============================================================
-- V8: Paper trades
-- =============================================================
CREATE TABLE IF NOT EXISTS paper_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8) NOT NULL,
    pnl DECIMAL(20, 8),
    opened_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,
    status VARCHAR(10) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED'))
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_signal_id ON paper_trades(signal_id);
CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_trades(status);
CREATE INDEX IF NOT EXISTS idx_paper_trades_opened_at ON paper_trades(opened_at DESC);

-- =============================================================
-- V9: Paper portfolio
-- =============================================================
CREATE TABLE IF NOT EXISTS paper_portfolio (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL UNIQUE,
    quantity DECIMAL(20, 8) NOT NULL DEFAULT 0,
    avg_entry_price DECIMAL(20, 8) NOT NULL DEFAULT 0,
    unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_portfolio_symbol ON paper_portfolio(symbol);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    # Downgrade drops all tables in reverse dependency order.
    # WARNING: This destroys all data. Only use in development.
    op.execute(
        """
    DROP TABLE IF EXISTS paper_portfolio CASCADE;
    DROP TABLE IF EXISTS paper_trades CASCADE;
    DROP TABLE IF EXISTS agent_decisions CASCADE;
    DROP TABLE IF EXISTS walk_forward_results CASCADE;
    DROP TABLE IF EXISTS signals CASCADE;
    DROP TABLE IF EXISTS strategy_performance CASCADE;
    DROP TABLE IF EXISTS strategy_implementations CASCADE;
    DROP TABLE IF EXISTS strategy_specs CASCADE;
    DROP TABLE IF EXISTS Strategies CASCADE;
    DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
    """
    )
