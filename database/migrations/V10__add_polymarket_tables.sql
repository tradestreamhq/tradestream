-- Polymarket market metadata
CREATE TABLE IF NOT EXISTS polymarket_markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id VARCHAR NOT NULL UNIQUE,
    condition_id VARCHAR NOT NULL,
    question TEXT NOT NULL,
    description TEXT,
    resolution_source VARCHAR,
    end_date TIMESTAMP,
    volume DOUBLE PRECISION NOT NULL DEFAULT 0,
    liquidity DOUBLE PRECISION NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    closed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_polymarket_markets_market_id ON polymarket_markets(market_id);
CREATE INDEX IF NOT EXISTS idx_polymarket_markets_active ON polymarket_markets(active);
CREATE INDEX IF NOT EXISTS idx_polymarket_markets_end_date ON polymarket_markets(end_date);

-- Polymarket tokens (YES/NO outcomes per market)
CREATE TABLE IF NOT EXISTS polymarket_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id VARCHAR NOT NULL UNIQUE,
    market_id VARCHAR NOT NULL REFERENCES polymarket_markets(market_id),
    outcome VARCHAR NOT NULL,
    price DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_polymarket_tokens_market_id ON polymarket_tokens(market_id);

-- Wallet activity tracking for insider detection
CREATE TABLE IF NOT EXISTS polymarket_wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address VARCHAR NOT NULL UNIQUE,
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    avg_position_size DOUBLE PRECISION NOT NULL DEFAULT 0,
    market_count INTEGER NOT NULL DEFAULT 0,
    total_volume DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_polymarket_wallets_address ON polymarket_wallets(wallet_address);
CREATE INDEX IF NOT EXISTS idx_polymarket_wallets_first_seen ON polymarket_wallets(first_seen);

-- Triggers for updated_at
CREATE TRIGGER update_polymarket_markets_updated_at
    BEFORE UPDATE ON polymarket_markets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_polymarket_tokens_updated_at
    BEFORE UPDATE ON polymarket_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_polymarket_wallets_updated_at
    BEFORE UPDATE ON polymarket_wallets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
