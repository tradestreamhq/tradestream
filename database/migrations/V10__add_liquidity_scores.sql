-- Liquidity scoring table for tracking asset liquidity over time.
CREATE TABLE IF NOT EXISTS liquidity_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    score DECIMAL(6, 2) NOT NULL,
    category VARCHAR(10) NOT NULL CHECK (category IN ('high', 'medium', 'low')),
    volume_component DECIMAL(6, 2) NOT NULL,
    spread_component DECIMAL(6, 2) NOT NULL,
    depth_component DECIMAL(6, 2) NOT NULL,
    frequency_component DECIMAL(6, 2) NOT NULL,
    scored_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_liquidity_scores_symbol ON liquidity_scores (symbol);
CREATE INDEX idx_liquidity_scores_symbol_scored_at ON liquidity_scores (symbol, scored_at DESC);
CREATE INDEX idx_liquidity_scores_category ON liquidity_scores (category);
