-- V4__add_signals.sql
-- Add signals table for trading signal history
-- Supports #1485 (Signal Notification Service)

-- Trading signals - historical record of all generated signals
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Strategy reference (optional - signals can exist without full strategy)
    spec_id UUID REFERENCES strategy_specs(id) ON DELETE SET NULL,
    implementation_id UUID REFERENCES strategy_implementations(id) ON DELETE SET NULL,

    -- Signal details
    instrument VARCHAR(50) NOT NULL,
    signal_type VARCHAR(20) NOT NULL, -- 'BUY', 'SELL', 'HOLD', 'CLOSE_LONG', 'CLOSE_SHORT'
    strength DECIMAL(5,4),            -- Signal confidence/strength 0.0-1.0

    -- Price information at signal time
    price DECIMAL(20,8) NOT NULL,
    bid_price DECIMAL(20,8),
    ask_price DECIMAL(20,8),
    volume DECIMAL(20,8),

    -- Risk parameters (if applicable)
    stop_loss DECIMAL(20,8),
    take_profit DECIMAL(20,8),
    position_size DECIMAL(10,4),

    -- Outcome tracking (filled in later)
    outcome VARCHAR(20),              -- 'PROFIT', 'LOSS', 'BREAKEVEN', 'PENDING', 'CANCELLED'
    exit_price DECIMAL(20,8),
    exit_time TIMESTAMP,
    pnl DECIMAL(20,8),
    pnl_percent DECIMAL(10,4),

    -- Notification tracking
    notified_at TIMESTAMP,
    notification_channels TEXT[],     -- ['telegram', 'email', 'webhook']

    -- Metadata
    timeframe VARCHAR(20),
    metadata JSONB,                   -- Additional signal-specific data
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for signals
CREATE INDEX IF NOT EXISTS idx_signals_instrument ON signals(instrument);
CREATE INDEX IF NOT EXISTS idx_signals_instrument_time ON signals(instrument, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_spec_id ON signals(spec_id);
CREATE INDEX IF NOT EXISTS idx_signals_impl_id ON signals(implementation_id);
CREATE INDEX IF NOT EXISTS idx_signals_outcome ON signals(outcome);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at DESC);

-- Composite index for signal queries
CREATE INDEX IF NOT EXISTS idx_signals_instrument_type_time ON signals(instrument, signal_type, created_at DESC);

-- Partition hint for future
COMMENT ON TABLE signals IS 'Trading signal history. Consider partitioning by created_at for high-frequency signal generation.';
