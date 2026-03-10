-- Paper portfolio table for tracking aggregate simulated positions.
CREATE TABLE paper_portfolio (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL UNIQUE,
    quantity DECIMAL(20, 8) NOT NULL DEFAULT 0,
    avg_entry_price DECIMAL(20, 8) NOT NULL DEFAULT 0,
    unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_paper_portfolio_symbol ON paper_portfolio(symbol);
