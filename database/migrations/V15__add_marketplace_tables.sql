-- Strategy Marketplace tables

CREATE TABLE IF NOT EXISTS marketplace_listings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id     UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    author          VARCHAR(255) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    performance_stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    price           NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    subscribers_count INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(strategy_id)
);

CREATE TABLE IF NOT EXISTS marketplace_subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      UUID NOT NULL REFERENCES marketplace_listings(id) ON DELETE CASCADE,
    user_id         VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(listing_id, user_id)
);

CREATE TABLE IF NOT EXISTS marketplace_ratings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      UUID NOT NULL REFERENCES marketplace_listings(id) ON DELETE CASCADE,
    user_id         VARCHAR(255) NOT NULL,
    score           INTEGER NOT NULL CHECK (score >= 1 AND score <= 5),
    review          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(listing_id, user_id)
);

CREATE INDEX idx_marketplace_listings_author ON marketplace_listings(author);
CREATE INDEX idx_marketplace_listings_active ON marketplace_listings(is_active);
CREATE INDEX idx_marketplace_listings_price ON marketplace_listings(price);
CREATE INDEX idx_marketplace_listings_created ON marketplace_listings(created_at);
CREATE INDEX idx_marketplace_subscriptions_user ON marketplace_subscriptions(user_id);
CREATE INDEX idx_marketplace_subscriptions_listing ON marketplace_subscriptions(listing_id);
CREATE INDEX idx_marketplace_ratings_listing ON marketplace_ratings(listing_id);

-- Auto-update updated_at triggers
CREATE TRIGGER set_marketplace_listings_updated_at
    BEFORE UPDATE ON marketplace_listings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_marketplace_ratings_updated_at
    BEFORE UPDATE ON marketplace_ratings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
