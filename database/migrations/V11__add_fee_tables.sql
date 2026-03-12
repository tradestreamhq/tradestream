-- Fee schedules and trade fee tracking

CREATE TABLE fee_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange VARCHAR(100) NOT NULL,
    fee_model VARCHAR(20) NOT NULL CHECK (fee_model IN ('MAKER_TAKER', 'FLAT', 'TIERED')),
    maker_rate DECIMAL(10, 6),
    taker_rate DECIMAL(10, 6),
    flat_fee DECIMAL(20, 8),
    tiers JSONB,
    fee_currency VARCHAR(20) NOT NULL DEFAULT 'USD',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_fee_schedule_exchange UNIQUE (exchange)
);

CREATE TABLE trade_fees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID,
    strategy_id UUID,
    exchange VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    size DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    is_maker BOOLEAN NOT NULL DEFAULT FALSE,
    fee_amount DECIMAL(20, 8) NOT NULL,
    fee_rate DECIMAL(10, 6) NOT NULL,
    fee_currency VARCHAR(20) NOT NULL DEFAULT 'USD',
    fee_model VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trade_fees_strategy_id ON trade_fees (strategy_id);
CREATE INDEX idx_trade_fees_exchange ON trade_fees (exchange);
CREATE INDEX idx_trade_fees_created_at ON trade_fees (created_at);
CREATE INDEX idx_trade_fees_strategy_month ON trade_fees (strategy_id, date_trunc('month', created_at));

CREATE TRIGGER update_fee_schedules_updated_at
    BEFORE UPDATE ON fee_schedules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
