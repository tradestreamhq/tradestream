-- Trading Leaderboard tables for ranking traders by performance.
-- Supports opt-in privacy, periodic snapshots, and filtering.

CREATE TABLE trader_profiles (
    user_id UUID PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    leaderboard_visible BOOLEAN NOT NULL DEFAULT FALSE,
    strategy_type VARCHAR(50),
    asset_class VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trader_profiles_visible ON trader_profiles(leaderboard_visible);
CREATE INDEX idx_trader_profiles_strategy_type ON trader_profiles(strategy_type);
CREATE INDEX idx_trader_profiles_asset_class ON trader_profiles(asset_class);

CREATE TABLE leaderboard_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES trader_profiles(user_id),
    period VARCHAR(20) NOT NULL CHECK (period IN ('daily', 'weekly', 'monthly', 'all_time')),
    total_return_pct DECIMAL(12, 6) NOT NULL DEFAULT 0,
    sharpe_ratio DECIMAL(10, 6),
    win_rate DECIMAL(6, 4),
    consistency_score DECIMAL(6, 4),
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    rank INTEGER,
    percentile DECIMAL(6, 4),
    snapshot_date DATE NOT NULL DEFAULT CURRENT_DATE,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, period, snapshot_date)
);

CREATE INDEX idx_leaderboard_snapshots_period ON leaderboard_snapshots(period);
CREATE INDEX idx_leaderboard_snapshots_date ON leaderboard_snapshots(snapshot_date DESC);
CREATE INDEX idx_leaderboard_snapshots_rank ON leaderboard_snapshots(period, snapshot_date, rank);
CREATE INDEX idx_leaderboard_snapshots_user_period ON leaderboard_snapshots(user_id, period);
