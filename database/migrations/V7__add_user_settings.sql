-- V7: User Settings
-- Purpose: User preferences, watchlists, and saved views

-- User preferences
CREATE TABLE IF NOT EXISTS user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    risk_tolerance VARCHAR(20) DEFAULT 'moderate'
        CHECK (risk_tolerance IN ('conservative', 'moderate', 'aggressive')),
    min_opportunity_score DECIMAL(3,2) DEFAULT 0.60
        CHECK (min_opportunity_score >= 0 AND min_opportunity_score <= 1),
    default_action_filter VARCHAR(10)[] DEFAULT ARRAY['BUY', 'SELL', 'HOLD'],
    theme VARCHAR(20) DEFAULT 'dark'
        CHECK (theme IN ('dark', 'light', 'system')),
    timezone VARCHAR(50) DEFAULT 'UTC',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    onboarding_step INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User watchlists (symbols they track)
CREATE TABLE IF NOT EXISTS user_watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    notes TEXT,
    alert_enabled BOOLEAN DEFAULT TRUE,
    position_size DECIMAL(18,8),  -- optional position tracking
    entry_price DECIMAL(18,8),
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);

-- Saved filter views
CREATE TABLE IF NOT EXISTS saved_views (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    filters JSONB NOT NULL DEFAULT '{}',
    /*
    filters example:
    {
        "symbols": ["BTC/USD", "ETH/USD"],
        "actions": ["BUY"],
        "minOpportunityScore": 0.70,
        "strategyTypes": ["RSI_REVERSAL", "MACD_CROSS"]
    }
    */
    is_default BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for user_settings
CREATE INDEX IF NOT EXISTS idx_user_settings_risk ON user_settings(risk_tolerance);

-- Indexes for user_watchlists
CREATE INDEX IF NOT EXISTS idx_watchlists_user ON user_watchlists(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlists_symbol ON user_watchlists(symbol);
CREATE INDEX IF NOT EXISTS idx_watchlists_user_alert ON user_watchlists(user_id, alert_enabled) WHERE alert_enabled = TRUE;

-- Indexes for saved_views
CREATE INDEX IF NOT EXISTS idx_saved_views_user ON saved_views(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_views_default ON saved_views(user_id, is_default) WHERE is_default = TRUE;
CREATE INDEX IF NOT EXISTS idx_saved_views_sort ON saved_views(user_id, sort_order);

-- Triggers for updated_at (reuses function from V6)
DROP TRIGGER IF EXISTS update_user_settings_updated_at ON user_settings;
CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_saved_views_updated_at ON saved_views;
CREATE TRIGGER update_saved_views_updated_at
    BEFORE UPDATE ON saved_views
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-create settings row when user is created
CREATE OR REPLACE FUNCTION create_user_settings()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_settings (user_id) VALUES (NEW.user_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS create_settings_on_user_insert ON users;
CREATE TRIGGER create_settings_on_user_insert
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION create_user_settings();
