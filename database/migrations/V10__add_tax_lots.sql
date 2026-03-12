-- Tax lot tracking tables for cost basis and realized gain/loss reporting.

CREATE TABLE IF NOT EXISTS tax_lots (
    lot_id       VARCHAR(36) PRIMARY KEY,
    symbol       VARCHAR(50)    NOT NULL,
    quantity     DECIMAL(20, 8) NOT NULL,
    cost_basis   DECIMAL(20, 8) NOT NULL,
    acquisition_date TIMESTAMP WITH TIME ZONE NOT NULL,
    remaining_quantity DECIMAL(20, 8) NOT NULL,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tax_lots_symbol ON tax_lots (symbol);
CREATE INDEX idx_tax_lots_symbol_remaining ON tax_lots (symbol, remaining_quantity)
    WHERE remaining_quantity > 0;

CREATE TABLE IF NOT EXISTS realized_gains (
    gain_id      VARCHAR(36) PRIMARY KEY,
    lot_id       VARCHAR(36)    NOT NULL REFERENCES tax_lots(lot_id),
    symbol       VARCHAR(50)    NOT NULL,
    quantity_disposed DECIMAL(20, 8) NOT NULL,
    cost_basis   DECIMAL(20, 8) NOT NULL,
    sale_price   DECIMAL(20, 8) NOT NULL,
    realized_gain DECIMAL(20, 8) NOT NULL,
    acquisition_date TIMESTAMP WITH TIME ZONE NOT NULL,
    disposal_date    TIMESTAMP WITH TIME ZONE NOT NULL,
    holding_period   VARCHAR(20) NOT NULL,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_realized_gains_symbol ON realized_gains (symbol);
CREATE INDEX idx_realized_gains_disposal ON realized_gains (disposal_date);
