-- V10__add_risk_snapshots.sql
-- Add portfolio-level risk snapshot table for periodic risk calculations

CREATE TABLE IF NOT EXISTS risk_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Portfolio-level metrics
    total_exposure DECIMAL(20,8) NOT NULL,
    net_position DECIMAL(20,8) NOT NULL,
    portfolio_value DECIMAL(20,8) NOT NULL,

    -- Risk metrics
    var_95 DECIMAL(20,8),           -- Value at Risk 95% confidence
    var_99 DECIMAL(20,8),           -- Value at Risk 99% confidence
    max_drawdown DECIMAL(10,4),     -- Maximum drawdown (fraction)
    current_drawdown DECIMAL(10,4), -- Current drawdown from peak

    -- Ratios
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),

    -- Concentration
    strategy_concentrations JSONB,  -- {"strategy_id": pct, ...}
    correlation_matrix JSONB,       -- Strategy return correlation matrix

    -- Metadata
    strategy_count INTEGER NOT NULL DEFAULT 0,
    snapshot_type VARCHAR(20) NOT NULL DEFAULT 'PERIODIC', -- 'PERIODIC', 'ON_DEMAND'
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_snap_created ON risk_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_risk_snap_type ON risk_snapshots(snapshot_type);

COMMENT ON TABLE risk_snapshots IS 'Periodic portfolio-level risk metric snapshots for historical tracking and trend analysis.';
