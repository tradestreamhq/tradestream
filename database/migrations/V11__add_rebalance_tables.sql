-- Portfolio rebalancing engine tables

CREATE TABLE rebalance_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    strategy VARCHAR(100),
    target_weight DECIMAL(10, 6) NOT NULL CHECK (target_weight >= 0 AND target_weight <= 1),
    min_weight DECIMAL(10, 6) NOT NULL DEFAULT 0 CHECK (min_weight >= 0),
    max_weight DECIMAL(10, 6) NOT NULL DEFAULT 1 CHECK (max_weight <= 1),
    rebalance_threshold DECIMAL(10, 6) NOT NULL DEFAULT 0.05,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (symbol, strategy)
);

CREATE TABLE rebalance_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    method VARCHAR(20) NOT NULL CHECK (method IN ('THRESHOLD', 'CALENDAR', 'HYBRID', 'MANUAL')),
    status VARCHAR(20) NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED', 'EXECUTED', 'CANCELLED')),
    weights_before JSONB NOT NULL,
    weights_after JSONB,
    proposed_orders JSONB NOT NULL,
    estimated_cost DECIMAL(20, 8) DEFAULT 0,
    triggered_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP
);

CREATE TABLE rebalance_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES rebalance_events(id),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity DECIMAL(20, 8) NOT NULL,
    reason VARCHAR(255),
    estimated_cost DECIMAL(20, 8) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rebalance_allocations_active ON rebalance_allocations(is_active);
CREATE INDEX idx_rebalance_events_triggered ON rebalance_events(triggered_at DESC);
CREATE INDEX idx_rebalance_orders_event ON rebalance_orders(event_id);
