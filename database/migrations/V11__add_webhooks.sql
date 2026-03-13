-- Webhook registration and delivery tracking tables.

CREATE TABLE webhooks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url             TEXT NOT NULL,
    events          TEXT[] NOT NULL,
    secret          TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_webhooks_is_active ON webhooks (is_active);
CREATE INDEX idx_webhooks_events ON webhooks USING GIN (events);

CREATE TABLE webhook_deliveries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id      UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending, success, failed
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    response_code   INTEGER,
    response_body   TEXT,
    error_message   TEXT,
    next_retry_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_webhook_deliveries_webhook_id ON webhook_deliveries (webhook_id);
CREATE INDEX idx_webhook_deliveries_status ON webhook_deliveries (status);
CREATE INDEX idx_webhook_deliveries_created_at ON webhook_deliveries (created_at DESC);

-- Auto-update updated_at on webhooks
CREATE TRIGGER set_webhooks_updated_at
    BEFORE UPDATE ON webhooks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
