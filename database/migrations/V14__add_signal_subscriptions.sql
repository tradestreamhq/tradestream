-- Signal subscriptions table for Phase 3 Signal MVP.
-- Tracks Telegram and webhook subscribers for signal delivery.

CREATE TABLE IF NOT EXISTS signal_subscriptions (
    id              UUID PRIMARY KEY,
    channel         TEXT NOT NULL CHECK (channel IN ('telegram', 'webhook')),
    endpoint        TEXT NOT NULL,
    strategies      TEXT[],          -- NULL means all strategies
    pairs           TEXT[],          -- NULL means all pairs
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

CREATE INDEX idx_signal_subs_active ON signal_subscriptions (active) WHERE active = true;
CREATE INDEX idx_signal_subs_channel ON signal_subscriptions (channel, endpoint);

-- Add strategy_name to signals table if it doesn't exist (supports Phase 3 queries).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'signals' AND column_name = 'strategy_name'
    ) THEN
        ALTER TABLE signals ADD COLUMN strategy_name TEXT;
        CREATE INDEX idx_signals_strategy_name ON signals (strategy_name);
    END IF;
END $$;
