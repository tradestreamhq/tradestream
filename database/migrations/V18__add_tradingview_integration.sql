-- TradingView Integration tables
-- Supports webhook-based signal ingestion from TradingView alerts
-- and connection management for the TradingView integration.

CREATE TABLE tradingview_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    webhook_token VARCHAR(255) NOT NULL UNIQUE,
    strategy_name VARCHAR(255),
    instrument VARCHAR(50),
    alert_mapping JSONB,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_tv_connections_webhook_token ON tradingview_connections (webhook_token);
CREATE INDEX idx_tv_connections_active ON tradingview_connections (active) WHERE active = true;
CREATE INDEX idx_tv_connections_strategy ON tradingview_connections (strategy_name) WHERE strategy_name IS NOT NULL;

CREATE TABLE tradingview_webhook_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tv_webhook_log_connection ON tradingview_webhook_log (connection_id, created_at DESC);
CREATE INDEX idx_tv_webhook_log_created ON tradingview_webhook_log (created_at DESC);
