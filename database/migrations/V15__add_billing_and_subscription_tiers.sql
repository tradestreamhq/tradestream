-- Billing tables for Stripe subscription management.
-- Tracks customer accounts, subscription tiers, and payment events.

CREATE TABLE IF NOT EXISTS billing_customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_customer_id TEXT UNIQUE NOT NULL,
    email           TEXT NOT NULL,
    telegram_chat_id TEXT,
    api_key         TEXT UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id         UUID NOT NULL REFERENCES billing_customers(id),
    stripe_subscription_id TEXT UNIQUE NOT NULL,
    tier                TEXT NOT NULL CHECK (tier IN ('free', 'pro', 'enterprise')),
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'past_due', 'cancelled', 'trialing', 'incomplete')),
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS billing_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_event_id TEXT UNIQUE NOT NULL,
    event_type      TEXT NOT NULL,
    subscription_id UUID REFERENCES billing_subscriptions(id),
    payload         JSONB,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Track daily signal usage for free tier limits
CREATE TABLE IF NOT EXISTS signal_usage (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES billing_customers(id),
    signal_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    signal_count    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (customer_id, signal_date)
);

CREATE INDEX idx_billing_customers_stripe ON billing_customers (stripe_customer_id);
CREATE INDEX idx_billing_customers_email ON billing_customers (email);
CREATE INDEX idx_billing_customers_telegram ON billing_customers (telegram_chat_id) WHERE telegram_chat_id IS NOT NULL;
CREATE INDEX idx_billing_subs_customer ON billing_subscriptions (customer_id);
CREATE INDEX idx_billing_subs_stripe ON billing_subscriptions (stripe_subscription_id);
CREATE INDEX idx_billing_subs_status ON billing_subscriptions (status) WHERE status = 'active';
CREATE INDEX idx_billing_events_type ON billing_events (event_type);
CREATE INDEX idx_signal_usage_customer_date ON signal_usage (customer_id, signal_date);

-- Link signal_subscriptions to billing_customers
ALTER TABLE signal_subscriptions ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES billing_customers(id);
CREATE INDEX IF NOT EXISTS idx_signal_subs_customer ON signal_subscriptions (customer_id) WHERE customer_id IS NOT NULL;
