-- Portfolio snapshots for historical analysis and reporting.
CREATE TABLE portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL UNIQUE,
    total_equity DECIMAL(20, 8) NOT NULL,
    cash_balance DECIMAL(20, 8) NOT NULL DEFAULT 0,
    margin_used DECIMAL(20, 8) NOT NULL DEFAULT 0,
    daily_change DECIMAL(20, 8),
    daily_change_pct DECIMAL(10, 4),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE portfolio_snapshot_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES portfolio_snapshots(id) ON DELETE CASCADE,
    symbol VARCHAR(50) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    market_value DECIMAL(20, 8) NOT NULL,
    UNIQUE (snapshot_id, symbol)
);

CREATE INDEX idx_portfolio_snapshots_date ON portfolio_snapshots(snapshot_date);
CREATE INDEX idx_snapshot_positions_snapshot_id ON portfolio_snapshot_positions(snapshot_id);
