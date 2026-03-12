-- Managed positions table for tracking position lifecycle across strategies.
CREATE TABLE managed_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('LONG', 'SHORT')),
    quantity DECIMAL(20, 8) NOT NULL,
    filled_quantity DECIMAL(20, 8) NOT NULL DEFAULT 0,
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    realized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'PARTIAL_FILL', 'FILLED', 'PARTIALLY_CLOSED', 'CLOSED')),
    strategy_name VARCHAR(100),
    asset_class VARCHAR(50) NOT NULL DEFAULT 'Other',
    signal_id UUID,
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    opened_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP
);

CREATE INDEX idx_managed_positions_symbol ON managed_positions(symbol);
CREATE INDEX idx_managed_positions_status ON managed_positions(status);
CREATE INDEX idx_managed_positions_strategy ON managed_positions(strategy_name);
CREATE INDEX idx_managed_positions_asset_class ON managed_positions(asset_class);
CREATE INDEX idx_managed_positions_opened_at ON managed_positions(opened_at DESC);
CREATE INDEX idx_managed_positions_signal_id ON managed_positions(signal_id);
