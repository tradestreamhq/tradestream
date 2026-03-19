-- Strategy Marketplace and Leaderboard tables
-- Supports browsing, ranking, subscribing, comparing, and rating strategies.

-- ----------------------------------------------------------------
-- Strategy categories enum-like reference
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO strategy_categories (name, label, description) VALUES
    ('trend_following', 'Trend Following', 'Strategies that follow market trends'),
    ('mean_reversion', 'Mean Reversion', 'Strategies that trade around a mean price'),
    ('momentum', 'Momentum', 'Strategies based on price momentum'),
    ('breakout', 'Breakout', 'Strategies that trade breakouts from ranges'),
    ('multi_indicator', 'Multi-Indicator', 'Strategies combining multiple indicators'),
    ('volatility', 'Volatility', 'Strategies based on volatility patterns'),
    ('statistical', 'Statistical', 'Quantitative / statistical strategies')
ON CONFLICT (name) DO NOTHING;

-- ----------------------------------------------------------------
-- Marketplace listings
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketplace_listings (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id       UUID NOT NULL,
    name              TEXT NOT NULL,
    author            TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    category          TEXT NOT NULL DEFAULT 'multi_indicator',
    tags              TEXT[] NOT NULL DEFAULT '{}',
    performance_stats JSONB NOT NULL DEFAULT '{}',
    price             NUMERIC(12, 2) NOT NULL DEFAULT 0,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    subscribers_count INTEGER NOT NULL DEFAULT 0,
    avg_rating        NUMERIC(3, 2) NOT NULL DEFAULT 0,
    rating_count      INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_ml_category ON marketplace_listings (category) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_ml_subscribers ON marketplace_listings (subscribers_count DESC) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_ml_rating ON marketplace_listings (avg_rating DESC) WHERE is_active = TRUE;

-- ----------------------------------------------------------------
-- Marketplace subscriptions
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketplace_subscriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id  UUID NOT NULL REFERENCES marketplace_listings(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (listing_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_ms_user ON marketplace_subscriptions (user_id);

-- ----------------------------------------------------------------
-- Marketplace ratings
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marketplace_ratings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id  UUID NOT NULL REFERENCES marketplace_listings(id) ON DELETE CASCADE,
    user_id     TEXT NOT NULL,
    score       SMALLINT NOT NULL CHECK (score >= 1 AND score <= 5),
    review      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (listing_id, user_id)
);

-- ----------------------------------------------------------------
-- Leaderboard snapshots (daily materialized rankings)
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id       UUID NOT NULL,
    period            TEXT NOT NULL CHECK (period IN ('daily', 'weekly', 'monthly', 'all_time')),
    rank              INTEGER NOT NULL,
    total_return_pct  NUMERIC(10, 4) NOT NULL DEFAULT 0,
    sharpe_ratio      NUMERIC(8, 4) NOT NULL DEFAULT 0,
    win_rate          NUMERIC(6, 4) NOT NULL DEFAULT 0,
    max_drawdown_pct  NUMERIC(10, 4) NOT NULL DEFAULT 0,
    trade_count       INTEGER NOT NULL DEFAULT 0,
    consistency_score NUMERIC(6, 4) NOT NULL DEFAULT 0,
    snapshot_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (strategy_id, period, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_ls_period_date ON leaderboard_snapshots (period, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_ls_rank ON leaderboard_snapshots (period, snapshot_date, rank);

-- ----------------------------------------------------------------
-- Strategy creator attribution
-- ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_creators (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    bio           TEXT,
    avatar_url    TEXT,
    strategies_count INTEGER NOT NULL DEFAULT 0,
    total_subscribers INTEGER NOT NULL DEFAULT 0,
    verified      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
