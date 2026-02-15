# Database Migrations Specification

## Goal

Create SQL migrations V6-V12 to support the viral trading signal platform including users, authentication, settings, notifications, providers, social features, achievements, and referrals.

## Target Behavior

All migrations follow Flyway naming conventions and are executed automatically during Helm deployment. Each migration is idempotent and can be safely re-run.

## Migration Overview

| Version | File | Purpose |
|---------|------|---------|
| V6 | `V6__add_users.sql` | Users, auth tokens, OAuth |
| V7 | `V7__add_user_settings.sql` | Settings, watchlists, saved views |
| V8 | `V8__add_notifications.sql` | Notification channels, preferences |
| V9 | `V9__add_providers.sql` | Providers, follows, reactions |
| V10 | `V10__add_achievements.sql` | Streaks, badges, achievements |
| V11 | `V11__add_referrals.sql` | Referral tracking, rewards |
| V12 | `V12__add_prediction_markets.sql` | Prediction market support (Q2) |

## V6: Users & Authentication

**File**: `database/migrations/V6__add_users.sql`

### Tables

```sql
-- Core users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    password_hash VARCHAR(255),
    oauth_provider VARCHAR(50),  -- 'google', 'github', NULL for email
    oauth_id VARCHAR(255),
    display_name VARCHAR(100),
    avatar_url TEXT,
    bio TEXT,
    is_provider BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(oauth_provider, oauth_id)
);

-- Email verification tokens
CREATE TABLE email_verification_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Password reset tokens
CREATE TABLE password_reset_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- JWT refresh tokens for token rotation
CREATE TABLE refresh_tokens (
    token_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    device_info JSONB,  -- user agent, IP, etc.
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id);
CREATE INDEX idx_users_provider ON users(is_provider) WHERE is_provider = TRUE;
CREATE INDEX idx_email_tokens_user ON email_verification_tokens(user_id);
CREATE INDEX idx_email_tokens_token ON email_verification_tokens(token);
CREATE INDEX idx_email_tokens_expires ON email_verification_tokens(expires_at) WHERE used_at IS NULL;
CREATE INDEX idx_password_tokens_user ON password_reset_tokens(user_id);
CREATE INDEX idx_password_tokens_token ON password_reset_tokens(token);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### Constraints

- `email` must be unique when not NULL
- `oauth_provider` + `oauth_id` combination must be unique
- Password required for email signup, NULL for OAuth
- Token expiry enforced at application level

## V7: User Settings

**File**: `database/migrations/V7__add_user_settings.sql`

### Tables

```sql
-- User preferences
CREATE TABLE user_settings (
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
CREATE TABLE user_watchlists (
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
CREATE TABLE saved_views (
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

-- Indexes
CREATE INDEX idx_watchlists_user ON user_watchlists(user_id);
CREATE INDEX idx_watchlists_symbol ON user_watchlists(symbol);
CREATE INDEX idx_saved_views_user ON saved_views(user_id);
CREATE INDEX idx_saved_views_default ON saved_views(user_id, is_default) WHERE is_default = TRUE;

-- Triggers
CREATE TRIGGER update_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

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

CREATE TRIGGER create_settings_on_user_insert
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION create_user_settings();
```

## V8: Notifications

**File**: `database/migrations/V8__add_notifications.sql`

### Tables

```sql
-- Notification channels (push, telegram, discord, email)
CREATE TABLE notification_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    channel_type VARCHAR(20) NOT NULL
        CHECK (channel_type IN ('push', 'telegram', 'discord', 'email', 'webhook')),
    channel_config JSONB NOT NULL DEFAULT '{}',
    /*
    channel_config examples:
    - push: {"subscription": {...web push subscription...}}
    - telegram: {"chat_id": "123456789", "bot_verified": true}
    - discord: {"webhook_url": "https://discord.com/api/webhooks/..."}
    - email: {"verified": true}  -- uses user's email
    - webhook: {"url": "https://...", "secret": "..."}
    */
    enabled BOOLEAN DEFAULT TRUE,
    verified BOOLEAN DEFAULT FALSE,
    last_sent_at TIMESTAMP WITH TIME ZONE,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, channel_type)  -- one channel per type per user
);

-- Notification preferences
CREATE TABLE notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    min_opportunity_score DECIMAL(3,2) DEFAULT 0.70
        CHECK (min_opportunity_score >= 0 AND min_opportunity_score <= 1),
    notify_on_buy BOOLEAN DEFAULT TRUE,
    notify_on_sell BOOLEAN DEFAULT TRUE,
    notify_on_hold BOOLEAN DEFAULT FALSE,
    notify_on_followed_provider BOOLEAN DEFAULT TRUE,
    notify_on_achievement BOOLEAN DEFAULT TRUE,
    notify_on_streak_risk BOOLEAN DEFAULT TRUE,  -- "You might lose your streak!"
    quiet_hours_enabled BOOLEAN DEFAULT FALSE,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '08:00',
    quiet_hours_tz VARCHAR(50) DEFAULT 'UTC',
    max_notifications_per_hour INTEGER DEFAULT 10,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Notification history (for analytics and debugging)
CREATE TABLE notification_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    channel_type VARCHAR(20) NOT NULL,
    notification_type VARCHAR(50) NOT NULL,
    /*
    notification_type values:
    - signal_alert
    - provider_signal
    - achievement_unlocked
    - streak_at_risk
    - streak_lost
    - referral_signup
    - welcome
    */
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'delivered', 'failed', 'skipped')),
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_notification_channels_user ON notification_channels(user_id);
CREATE INDEX idx_notification_channels_type ON notification_channels(channel_type, enabled) WHERE enabled = TRUE;
CREATE INDEX idx_notification_history_user ON notification_history(user_id);
CREATE INDEX idx_notification_history_status ON notification_history(status) WHERE status = 'pending';
CREATE INDEX idx_notification_history_created ON notification_history(created_at);

-- Triggers
CREATE TRIGGER update_notification_channels_updated_at
    BEFORE UPDATE ON notification_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notification_preferences_updated_at
    BEFORE UPDATE ON notification_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-create preferences row when user is created
CREATE OR REPLACE FUNCTION create_notification_preferences()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO notification_preferences (user_id) VALUES (NEW.user_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER create_prefs_on_user_insert
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION create_notification_preferences();
```

## V9: Providers & Social

**File**: `database/migrations/V9__add_providers.sql`

### Tables

```sql
-- Provider profiles (extends users who opt-in)
CREATE TABLE providers (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    display_name VARCHAR(100) NOT NULL,
    bio TEXT,
    strategy_description TEXT,
    avatar_url TEXT,
    banner_url TEXT,
    website_url TEXT,
    twitter_handle VARCHAR(50),
    risk_level VARCHAR(20) DEFAULT 'moderate'
        CHECK (risk_level IN ('conservative', 'moderate', 'aggressive')),
    specialties VARCHAR(50)[] DEFAULT '{}',  -- ['crypto', 'forex', 'predictions']

    -- Computed stats (updated by background job)
    total_signals INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    win_rate DECIMAL(5,4) DEFAULT 0,  -- 0.6734 = 67.34%
    avg_return DECIMAL(8,4) DEFAULT 0,  -- 0.0423 = 4.23%
    total_return DECIMAL(10,4) DEFAULT 0,
    sharpe_ratio DECIMAL(6,4),
    max_drawdown DECIMAL(5,4),
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,

    -- Social stats
    follower_count INTEGER DEFAULT 0,
    signal_likes_total INTEGER DEFAULT 0,

    -- Verification
    is_verified BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP WITH TIME ZONE,
    verification_level VARCHAR(20) DEFAULT 'none'
        CHECK (verification_level IN ('none', 'basic', 'pro', 'elite')),

    -- Monetization (Q3+)
    is_premium BOOLEAN DEFAULT FALSE,
    subscription_price_monthly DECIMAL(10,2),
    stripe_account_id VARCHAR(255),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Provider signals (links signals to providers)
CREATE TABLE provider_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(user_id) ON DELETE CASCADE,
    signal_id UUID NOT NULL REFERENCES signals(signal_id) ON DELETE CASCADE,

    -- Optional provider commentary
    commentary TEXT,

    -- Outcome tracking
    outcome VARCHAR(20) CHECK (outcome IN ('PROFIT', 'LOSS', 'BREAKEVEN', 'PENDING')),
    actual_return DECIMAL(8,4),
    closed_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(provider_id, signal_id)
);

-- Follows (user follows provider)
CREATE TABLE follows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider_id UUID NOT NULL REFERENCES providers(user_id) ON DELETE CASCADE,

    -- Preferences for this follow
    notify_on_signal BOOLEAN DEFAULT TRUE,
    copy_trades BOOLEAN DEFAULT FALSE,  -- Future: auto-copy
    copy_percentage DECIMAL(5,2),  -- % of provider's position size

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(follower_id, provider_id)
);

-- Signal reactions (likes, comments)
CREATE TABLE signal_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL REFERENCES signals(signal_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    reaction_type VARCHAR(20) NOT NULL
        CHECK (reaction_type IN ('like', 'fire', 'rocket', 'sad')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(signal_id, user_id, reaction_type)
);

-- Signal comments
CREATE TABLE signal_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL REFERENCES signals(signal_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    parent_id UUID REFERENCES signal_comments(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_edited BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_providers_verified ON providers(is_verified) WHERE is_verified = TRUE;
CREATE INDEX idx_providers_win_rate ON providers(win_rate DESC);
CREATE INDEX idx_providers_followers ON providers(follower_count DESC);
CREATE INDEX idx_providers_streak ON providers(current_streak DESC);

CREATE INDEX idx_provider_signals_provider ON provider_signals(provider_id);
CREATE INDEX idx_provider_signals_signal ON provider_signals(signal_id);
CREATE INDEX idx_provider_signals_created ON provider_signals(created_at DESC);

CREATE INDEX idx_follows_follower ON follows(follower_id);
CREATE INDEX idx_follows_provider ON follows(provider_id);
CREATE INDEX idx_follows_created ON follows(created_at DESC);

CREATE INDEX idx_reactions_signal ON signal_reactions(signal_id);
CREATE INDEX idx_reactions_user ON signal_reactions(user_id);

CREATE INDEX idx_comments_signal ON signal_comments(signal_id);
CREATE INDEX idx_comments_user ON signal_comments(user_id);
CREATE INDEX idx_comments_parent ON signal_comments(parent_id);

-- Triggers
CREATE TRIGGER update_providers_updated_at
    BEFORE UPDATE ON providers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Update follower count on follow/unfollow
CREATE OR REPLACE FUNCTION update_follower_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE providers SET follower_count = follower_count + 1
        WHERE user_id = NEW.provider_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE providers SET follower_count = follower_count - 1
        WHERE user_id = OLD.provider_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_follower_count_trigger
    AFTER INSERT OR DELETE ON follows
    FOR EACH ROW
    EXECUTE FUNCTION update_follower_count();

-- Materialized views for leaderboards
CREATE MATERIALIZED VIEW leaderboard_top_providers AS
SELECT
    p.user_id,
    p.display_name,
    p.avatar_url,
    p.win_rate,
    p.avg_return,
    p.follower_count,
    p.current_streak,
    p.is_verified,
    p.verification_level,
    ROW_NUMBER() OVER (ORDER BY p.follower_count DESC) as rank_followers,
    ROW_NUMBER() OVER (ORDER BY p.win_rate DESC) as rank_win_rate,
    ROW_NUMBER() OVER (ORDER BY p.avg_return DESC) as rank_return,
    ROW_NUMBER() OVER (ORDER BY p.current_streak DESC) as rank_streak
FROM providers p
WHERE p.total_signals >= 10;  -- Minimum signals to rank

CREATE UNIQUE INDEX idx_leaderboard_user ON leaderboard_top_providers(user_id);

-- Refresh leaderboard hourly (scheduled via cron/k8s job)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY leaderboard_top_providers;
```

## V10: Achievements & Streaks

**File**: `database/migrations/V10__add_achievements.sql`

### Tables

```sql
-- Achievement definitions
CREATE TABLE achievement_definitions (
    id VARCHAR(50) PRIMARY KEY,  -- 'first_win', 'streak_7', etc.
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL
        CHECK (category IN ('trading', 'social', 'engagement', 'provider', 'special')),
    icon VARCHAR(10) NOT NULL,  -- emoji
    points INTEGER DEFAULT 0,
    rarity VARCHAR(20) DEFAULT 'common'
        CHECK (rarity IN ('common', 'uncommon', 'rare', 'epic', 'legendary')),
    requirement_type VARCHAR(50) NOT NULL,
    requirement_value INTEGER NOT NULL,
    /*
    requirement_type examples:
    - win_count: 1, 10, 100
    - streak_days: 7, 30, 100, 365
    - follower_count: 10, 100, 1000
    - signal_count: 10, 100, 1000
    - referral_count: 1, 5, 10
    */
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- User achievements (unlocked)
CREATE TABLE user_achievements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    achievement_id VARCHAR(50) NOT NULL REFERENCES achievement_definitions(id),
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notified BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, achievement_id)
);

-- User streaks (active tracking)
CREATE TABLE user_streaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    streak_type VARCHAR(50) NOT NULL
        CHECK (streak_type IN ('login', 'profitable_signal', 'analysis_post', 'provider_signal')),
    current_count INTEGER DEFAULT 0,
    longest_count INTEGER DEFAULT 0,
    last_activity_date DATE,
    streak_started_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, streak_type)
);

-- Streak history (for analytics)
CREATE TABLE streak_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    streak_type VARCHAR(50) NOT NULL,
    final_count INTEGER NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_user_achievements_user ON user_achievements(user_id);
CREATE INDEX idx_user_achievements_achievement ON user_achievements(achievement_id);
CREATE INDEX idx_user_achievements_unnotified ON user_achievements(notified) WHERE notified = FALSE;

CREATE INDEX idx_user_streaks_user ON user_streaks(user_id);
CREATE INDEX idx_user_streaks_type ON user_streaks(streak_type);
CREATE INDEX idx_user_streaks_active ON user_streaks(last_activity_date);

CREATE INDEX idx_streak_history_user ON streak_history(user_id);

-- Insert default achievements
INSERT INTO achievement_definitions (id, name, description, category, icon, points, rarity, requirement_type, requirement_value, sort_order) VALUES
-- Trading achievements
('first_signal', 'First Signal', 'Received your first trading signal', 'trading', '🎯', 10, 'common', 'signal_count', 1, 1),
('win_1', 'First Win', 'Your first profitable signal', 'trading', '🏆', 25, 'common', 'win_count', 1, 2),
('win_10', 'Getting Started', '10 profitable signals', 'trading', '📈', 50, 'uncommon', 'win_count', 10, 3),
('win_100', 'Consistent Winner', '100 profitable signals', 'trading', '💰', 200, 'rare', 'win_count', 100, 4),
('win_1000', 'Trading Master', '1000 profitable signals', 'trading', '👑', 1000, 'legendary', 'win_count', 1000, 5),

-- Streak achievements
('streak_7', 'Week Warrior', '7-day login streak', 'engagement', '🔥', 50, 'common', 'streak_days', 7, 10),
('streak_30', 'Monthly Dedication', '30-day login streak', 'engagement', '💪', 150, 'uncommon', 'streak_days', 30, 11),
('streak_100', 'Century Club', '100-day login streak', 'engagement', '⭐', 500, 'rare', 'streak_days', 100, 12),
('streak_365', 'Year of Commitment', '365-day login streak', 'engagement', '💎', 2000, 'legendary', 'streak_days', 365, 13),

-- Social achievements
('follower_10', 'Building Community', '10 followers', 'social', '👥', 50, 'common', 'follower_count', 10, 20),
('follower_100', 'Rising Star', '100 followers', 'social', '🌟', 200, 'uncommon', 'follower_count', 100, 21),
('follower_1000', 'Influencer', '1000 followers', 'social', '🚀', 1000, 'rare', 'follower_count', 1000, 22),
('follower_10000', 'Legend', '10000 followers', 'social', '🏛️', 5000, 'legendary', 'follower_count', 10000, 23),

-- Provider achievements
('provider_first', 'Signal Provider', 'Published your first signal', 'provider', '📡', 100, 'uncommon', 'provider_signal_count', 1, 30),
('provider_verified', 'Verified Provider', 'Earned verified status', 'provider', '✅', 500, 'rare', 'verified', 1, 31),

-- Referral achievements
('referral_1', 'Sharing is Caring', 'First successful referral', 'social', '🤝', 100, 'common', 'referral_count', 1, 40),
('referral_5', 'Growth Hacker', '5 successful referrals', 'social', '📢', 300, 'uncommon', 'referral_count', 5, 41),
('referral_10', 'Ambassador', '10 successful referrals', 'social', '🎖️', 750, 'rare', 'referral_count', 10, 42);

-- Trigger for updated_at
CREATE TRIGGER update_user_streaks_updated_at
    BEFORE UPDATE ON user_streaks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

## V11: Referrals

**File**: `database/migrations/V11__add_referrals.sql`

### Tables

```sql
-- Referral codes
CREATE TABLE referral_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    code VARCHAR(20) NOT NULL UNIQUE,  -- 'KING42', auto-generated
    custom_code VARCHAR(20) UNIQUE,  -- User's custom code (premium feature)
    uses_count INTEGER DEFAULT 0,
    max_uses INTEGER,  -- NULL = unlimited
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Referral tracking
CREATE TABLE referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    referee_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    referral_code_id UUID NOT NULL REFERENCES referral_codes(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'qualified', 'rewarded', 'rejected')),
    /*
    Status flow:
    - pending: Referee signed up
    - qualified: Referee completed required action (e.g., first signal)
    - rewarded: Both parties received rewards
    - rejected: Fraud detected or violation
    */
    referee_reward_amount DECIMAL(10,2),
    referrer_reward_amount DECIMAL(10,2),
    referrer_rewarded_at TIMESTAMP WITH TIME ZONE,
    referee_rewarded_at TIMESTAMP WITH TIME ZONE,
    qualified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(referee_id)  -- Each user can only be referred once
);

-- Referral rewards ledger
CREATE TABLE referral_rewards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    referral_id UUID NOT NULL REFERENCES referrals(id),
    reward_type VARCHAR(20) NOT NULL
        CHECK (reward_type IN ('credit', 'cash', 'subscription')),
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processed', 'paid', 'failed')),
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Referral tiers (gamification)
CREATE TABLE referral_tiers (
    id VARCHAR(20) PRIMARY KEY,  -- 'bronze', 'silver', 'gold'
    name VARCHAR(50) NOT NULL,
    min_referrals INTEGER NOT NULL,
    referrer_reward DECIMAL(10,2) NOT NULL,
    referee_reward DECIMAL(10,2) NOT NULL,
    bonus_percentage DECIMAL(5,2) DEFAULT 0,  -- Revenue share for gold+
    icon VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_referral_codes_user ON referral_codes(user_id);
CREATE INDEX idx_referral_codes_code ON referral_codes(code);
CREATE INDEX idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX idx_referrals_referee ON referrals(referee_id);
CREATE INDEX idx_referrals_status ON referrals(status);
CREATE INDEX idx_referral_rewards_user ON referral_rewards(user_id);

-- Insert default tiers
INSERT INTO referral_tiers (id, name, min_referrals, referrer_reward, referee_reward, bonus_percentage, icon) VALUES
('bronze', 'Bronze', 1, 25.00, 25.00, 0, '🥉'),
('silver', 'Silver', 5, 50.00, 25.00, 0, '🥈'),
('gold', 'Gold', 10, 75.00, 50.00, 5.00, '🥇');

-- Function to generate referral code
CREATE OR REPLACE FUNCTION generate_referral_code()
RETURNS TRIGGER AS $$
DECLARE
    new_code VARCHAR(20);
    attempts INTEGER := 0;
BEGIN
    LOOP
        -- Generate code: 6 alphanumeric chars
        new_code := upper(substr(md5(random()::text), 1, 6));

        -- Check if unique
        IF NOT EXISTS (SELECT 1 FROM referral_codes WHERE code = new_code) THEN
            INSERT INTO referral_codes (user_id, code) VALUES (NEW.user_id, new_code);
            EXIT;
        END IF;

        attempts := attempts + 1;
        IF attempts > 10 THEN
            RAISE EXCEPTION 'Could not generate unique referral code';
        END IF;
    END LOOP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Auto-create referral code when user is created
CREATE TRIGGER create_referral_code_on_user_insert
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION generate_referral_code();
```

## V12: Prediction Markets (Q2)

**File**: `database/migrations/V12__add_prediction_markets.sql`

### Tables

```sql
-- Prediction market platforms
CREATE TABLE prediction_platforms (
    id VARCHAR(20) PRIMARY KEY,  -- 'kalshi', 'polymarket'
    name VARCHAR(100) NOT NULL,
    api_base_url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Prediction markets
CREATE TABLE prediction_markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_id VARCHAR(20) NOT NULL REFERENCES prediction_platforms(id),
    external_market_id VARCHAR(100) NOT NULL,  -- Platform's market ID
    category VARCHAR(50) NOT NULL
        CHECK (category IN ('economics', 'crypto', 'politics', 'regulatory', 'sports', 'other')),
    title TEXT NOT NULL,
    description TEXT,
    question TEXT NOT NULL,
    settlement_date TIMESTAMP WITH TIME ZONE,
    current_yes_price DECIMAL(5,4),  -- 0.0000 to 1.0000
    current_no_price DECIMAL(5,4),
    volume_24h DECIMAL(18,2),
    total_volume DECIMAL(18,2),
    is_active BOOLEAN DEFAULT TRUE,
    settled BOOLEAN DEFAULT FALSE,
    settlement_value DECIMAL(5,4),  -- Final outcome
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(platform_id, external_market_id)
);

-- Prediction market price history
CREATE TABLE prediction_market_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES prediction_markets(id) ON DELETE CASCADE,
    yes_price DECIMAL(5,4) NOT NULL,
    no_price DECIMAL(5,4) NOT NULL,
    volume DECIMAL(18,2),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Prediction signals
CREATE TABLE prediction_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES prediction_markets(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES strategies(strategy_id),  -- Optional: GA-discovered
    signal_type VARCHAR(10) NOT NULL
        CHECK (signal_type IN ('BUY_YES', 'BUY_NO', 'SELL_YES', 'SELL_NO')),
    entry_price DECIMAL(5,4) NOT NULL,
    target_price DECIMAL(5,4),
    stop_loss_price DECIMAL(5,4),
    confidence DECIMAL(3,2) NOT NULL,
    opportunity_score DECIMAL(5,2),
    reasoning JSONB NOT NULL,
    /*
    reasoning example:
    {
        "summary": "Probability RSI oversold at 32",
        "indicators": [
            {"name": "ProbabilityRSI", "value": 32, "signal": "oversold"},
            {"name": "BollingerBand", "position": "below_lower"}
        ],
        "risk_metrics": {
            "max_loss": 0.68,
            "max_gain": 0.32,
            "kelly_size": 0.08
        }
    }
    */
    outcome VARCHAR(20) CHECK (outcome IN ('PROFIT', 'LOSS', 'BREAKEVEN', 'PENDING', 'EXPIRED')),
    actual_return DECIMAL(8,4),
    closed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_prediction_markets_platform ON prediction_markets(platform_id);
CREATE INDEX idx_prediction_markets_category ON prediction_markets(category);
CREATE INDEX idx_prediction_markets_settlement ON prediction_markets(settlement_date);
CREATE INDEX idx_prediction_markets_active ON prediction_markets(is_active) WHERE is_active = TRUE;

CREATE INDEX idx_prediction_prices_market ON prediction_market_prices(market_id);
CREATE INDEX idx_prediction_prices_time ON prediction_market_prices(recorded_at DESC);

CREATE INDEX idx_prediction_signals_market ON prediction_signals(market_id);
CREATE INDEX idx_prediction_signals_created ON prediction_signals(created_at DESC);
CREATE INDEX idx_prediction_signals_outcome ON prediction_signals(outcome);

-- Insert default platforms
INSERT INTO prediction_platforms (id, name, api_base_url) VALUES
('kalshi', 'Kalshi', 'https://trading-api.kalshi.com'),
('polymarket', 'Polymarket', 'https://gamma-api.polymarket.com');

-- Triggers
CREATE TRIGGER update_prediction_markets_updated_at
    BEFORE UPDATE ON prediction_markets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

## File Structure

```
database/migrations/
├── V1__baseline_strategies_table.sql    # Existing
├── V2__add_strategy_specs.sql           # Existing
├── V3__add_strategy_performance.sql     # Existing
├── V4__add_signals.sql                  # Existing
├── V5__add_walkforward_validation.sql   # Existing
├── V6__add_users.sql                    # NEW
├── V7__add_user_settings.sql            # NEW
├── V8__add_notifications.sql            # NEW
├── V9__add_providers.sql                # NEW
├── V10__add_achievements.sql            # NEW
├── V11__add_referrals.sql               # NEW
└── V12__add_prediction_markets.sql      # NEW (Q2)
```

## Constraints

- All migrations must be idempotent (safe to re-run)
- Use `IF NOT EXISTS` for table creation
- Foreign keys must reference existing tables
- Indexes should be created for all foreign keys
- Triggers must handle both INSERT and UPDATE/DELETE where applicable
- Use `TIMESTAMP WITH TIME ZONE` for all timestamps
- UUIDs for primary keys (except lookup tables)

## Acceptance Criteria

- [ ] V6: Users table created with email and OAuth support
- [ ] V6: Email verification tokens working
- [ ] V6: Password reset tokens working
- [ ] V6: Refresh token rotation working
- [ ] V7: User settings auto-created on user insert
- [ ] V7: Watchlist CRUD operations working
- [ ] V7: Saved views with JSON filters working
- [ ] V8: Notification channels supporting push, telegram, discord
- [ ] V8: Notification preferences with quiet hours
- [ ] V9: Provider profiles linked to users
- [ ] V9: Follow/unfollow updates follower_count automatically
- [ ] V9: Leaderboard materialized view created
- [ ] V10: Achievement definitions seeded
- [ ] V10: User achievements tracking unlocked badges
- [ ] V10: Streak tracking for multiple streak types
- [ ] V11: Referral codes auto-generated for new users
- [ ] V11: Referral tiers seeded (bronze, silver, gold)
- [ ] V12: Prediction market tables created
- [ ] V12: Platform configurations seeded (Kalshi, Polymarket)
- [ ] All migrations run successfully via Flyway
- [ ] All indexes created for query optimization
- [ ] All triggers functioning correctly

## Notes

### Migration Execution

Migrations are executed automatically during Helm deployment via the database migration job:

```yaml
# charts/tradestream/templates/database-migration.yaml
# Flyway runs all pending migrations on startup
```

### Materialized View Refresh

The leaderboard materialized view should be refreshed hourly:

```sql
-- Scheduled via K8s CronJob
REFRESH MATERIALIZED VIEW CONCURRENTLY leaderboard_top_providers;
```

### Data Migration Considerations

- Existing `signals` table is referenced by `provider_signals`
- Existing `strategies` table is referenced by `prediction_signals`
- No data migration needed for existing tables
