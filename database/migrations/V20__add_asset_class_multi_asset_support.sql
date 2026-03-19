-- V20__add_asset_class_multi_asset_support.sql
-- Add asset_class support for multi-asset market data generalization.
-- Supports #1471 (Market Data Generalization) and #1466 (Non-Chart-Based Strategy Support)

-- Asset class type for strategies and signals
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'asset_class_type') THEN
        CREATE TYPE asset_class_type AS ENUM ('crypto', 'stocks', 'forex', 'commodities');
    END IF;
END
$$;

-- Add asset_class to signals table
ALTER TABLE signals
    ADD COLUMN IF NOT EXISTS asset_class asset_class_type NOT NULL DEFAULT 'crypto';

-- Add asset_class to strategies table
ALTER TABLE strategies
    ADD COLUMN IF NOT EXISTS asset_class asset_class_type NOT NULL DEFAULT 'crypto';

-- Add asset_class to strategy_performance table
ALTER TABLE strategy_performance
    ADD COLUMN IF NOT EXISTS asset_class asset_class_type NOT NULL DEFAULT 'crypto';

-- Asset metadata table for multi-asset trading characteristics
CREATE TABLE IF NOT EXISTS asset_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    asset_class asset_class_type NOT NULL,
    exchange VARCHAR(100),
    description TEXT,

    -- Trading hours
    trading_hours_timezone VARCHAR(50),
    market_open VARCHAR(10),
    market_close VARCHAR(10),

    -- Precision and sizing
    tick_size DECIMAL(20,10),
    lot_size DECIMAL(20,10),
    price_precision INTEGER,
    quantity_precision INTEGER,

    -- Margin requirements
    margin_requirement DECIMAL(10,4),
    maintenance_margin DECIMAL(10,4),

    -- Currency pair components
    base_currency VARCHAR(20),
    quote_currency VARCHAR(20) DEFAULT 'USD',

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE(symbol, asset_class)
);

-- Indexes for asset_class lookups
CREATE INDEX IF NOT EXISTS idx_signals_asset_class ON signals(asset_class);
CREATE INDEX IF NOT EXISTS idx_strategies_asset_class ON strategies(asset_class);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_asset_class ON strategy_performance(asset_class);
CREATE INDEX IF NOT EXISTS idx_asset_metadata_symbol ON asset_metadata(symbol);
CREATE INDEX IF NOT EXISTS idx_asset_metadata_asset_class ON asset_metadata(asset_class);

COMMENT ON TABLE asset_metadata IS 'Trading characteristics per instrument and asset class. Used by multi-asset strategy engine.';
