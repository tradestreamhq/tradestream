-- Trading fees table for tracking commissions, exchange fees, funding, and spreads.
CREATE TABLE trading_fees (
    id BIGSERIAL PRIMARY KEY,
    trade_id VARCHAR(100) NOT NULL,
    strategy_id VARCHAR(100) NOT NULL,
    fee_type VARCHAR(20) NOT NULL CHECK (fee_type IN ('commission', 'exchange', 'funding', 'spread')),
    amount DECIMAL(20, 8) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trading_fees_strategy_id ON trading_fees(strategy_id);
CREATE INDEX idx_trading_fees_trade_id ON trading_fees(trade_id);
CREATE INDEX idx_trading_fees_fee_type ON trading_fees(fee_type);
CREATE INDEX idx_trading_fees_created_at ON trading_fees(created_at DESC);
