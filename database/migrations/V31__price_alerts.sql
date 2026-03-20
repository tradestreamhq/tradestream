-- Price alerts for user-defined price notifications
CREATE TABLE IF NOT EXISTS price_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR NOT NULL,
    condition VARCHAR(10) NOT NULL CHECK (condition IN ('above', 'below', 'cross')),
    target_price DECIMAL(20,8) NOT NULL,
    reference_price DECIMAL(20,8),
    percentage DECIMAL(10,4),
    notification_channel VARCHAR(50) NOT NULL DEFAULT 'webhook',
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'triggered', 'expired', 'cancelled')),
    trigger_price DECIMAL(20,8),
    triggered_at TIMESTAMP,
    last_checked_price DECIMAL(20,8),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_price_alerts_symbol ON price_alerts(symbol);
CREATE INDEX IF NOT EXISTS idx_price_alerts_status ON price_alerts(status);
CREATE INDEX IF NOT EXISTS idx_price_alerts_symbol_status ON price_alerts(symbol, status);
CREATE INDEX IF NOT EXISTS idx_price_alerts_created_at ON price_alerts(created_at);

CREATE TRIGGER update_price_alerts_updated_at
    BEFORE UPDATE ON price_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
