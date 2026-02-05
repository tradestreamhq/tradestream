-- V8: Notifications
-- Purpose: Notification channels, preferences, and history

-- Notification channels (push, telegram, discord, email)
CREATE TABLE IF NOT EXISTS notification_channels (
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
CREATE TABLE IF NOT EXISTS notification_preferences (
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
CREATE TABLE IF NOT EXISTS notification_history (
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

-- Indexes for notification_channels
CREATE INDEX IF NOT EXISTS idx_notification_channels_user ON notification_channels(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_channels_type ON notification_channels(channel_type, enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_notification_channels_verified ON notification_channels(user_id, verified) WHERE verified = TRUE;

-- Indexes for notification_preferences
CREATE INDEX IF NOT EXISTS idx_notification_prefs_score ON notification_preferences(min_opportunity_score);

-- Indexes for notification_history
CREATE INDEX IF NOT EXISTS idx_notification_history_user ON notification_history(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_history_status ON notification_history(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_notification_history_created ON notification_history(created_at);
CREATE INDEX IF NOT EXISTS idx_notification_history_type ON notification_history(notification_type);

-- Triggers for updated_at (reuses function from V6)
DROP TRIGGER IF EXISTS update_notification_channels_updated_at ON notification_channels;
CREATE TRIGGER update_notification_channels_updated_at
    BEFORE UPDATE ON notification_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_notification_preferences_updated_at ON notification_preferences;
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

DROP TRIGGER IF EXISTS create_prefs_on_user_insert ON users;
CREATE TRIGGER create_prefs_on_user_insert
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION create_notification_preferences();
