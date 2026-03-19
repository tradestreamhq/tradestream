-- Multi-channel signal delivery tables.
-- Supports delivery receipts, DLQ, and user channel preferences.

-- User channel preferences: which channels, filters, quiet hours
CREATE TABLE IF NOT EXISTS user_channel_preferences (
    user_id VARCHAR(255) NOT NULL,
    channel VARCHAR(50) NOT NULL,          -- telegram, discord, slack, email, sms, webhook
    channel_id VARCHAR(255) NOT NULL,      -- recipient: chat_id, webhook_url, email, phone
    enabled BOOLEAN DEFAULT TRUE,
    is_primary BOOLEAN DEFAULT FALSE,
    min_opportunity_score INTEGER DEFAULT 60,
    symbols TEXT[],                         -- NULL = all symbols
    actions TEXT[],                         -- NULL = all actions
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, channel)
);

-- User-level delivery preferences (deduplication, tier, fallback)
CREATE TABLE IF NOT EXISTS user_delivery_preferences (
    user_id VARCHAR(255) PRIMARY KEY,
    dedup_preference VARCHAR(20) DEFAULT 'primary_only',  -- primary_only, all_enabled, fallback_chain
    primary_channel VARCHAR(50),
    fallback_order TEXT[],
    tier VARCHAR(20) DEFAULT 'free',       -- free, pro, power
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Delivery receipts: tracks every delivery attempt
CREATE TABLE IF NOT EXISTS delivery_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,           -- pending, sent, delivered, read, failed
    external_message_id VARCHAR(255),
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(signal_id, user_id, channel)
);

CREATE INDEX IF NOT EXISTS idx_receipts_user ON delivery_receipts(user_id);
CREATE INDEX IF NOT EXISTS idx_receipts_signal ON delivery_receipts(signal_id);
CREATE INDEX IF NOT EXISTS idx_receipts_status ON delivery_receipts(status);
CREATE INDEX IF NOT EXISTS idx_receipts_created ON delivery_receipts(created_at);

-- Dead letter queue for failed deliveries
CREATE TABLE IF NOT EXISTS delivery_dlq (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    error_message TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    first_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, reprocessed, discarded
    discard_reason TEXT,
    reprocessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dlq_status ON delivery_dlq(status);
CREATE INDEX IF NOT EXISTS idx_dlq_channel ON delivery_dlq(channel);
CREATE INDEX IF NOT EXISTS idx_dlq_last_attempt ON delivery_dlq(last_attempt_at);
