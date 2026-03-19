-- User Strategy Builder: stores user-created strategy configurations.
-- These configs map to StrategyConfig / IndicatorConfig / ConditionConfig
-- and can be fed into ConfigDrivenStrategyBuilder for execution.

CREATE TABLE IF NOT EXISTS user_strategies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT DEFAULT '',
    category        VARCHAR(50) DEFAULT 'multi_indicator',
    indicators      JSONB NOT NULL DEFAULT '[]'::jsonb,
    entry_conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    exit_conditions  JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags            JSONB DEFAULT '[]'::jsonb,
    version         INTEGER NOT NULL DEFAULT 1,
    is_published    BOOLEAN DEFAULT FALSE,
    backtest_results JSONB,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_strategies_user ON user_strategies(user_id);
CREATE INDEX idx_user_strategies_category ON user_strategies(category);
CREATE INDEX idx_user_strategies_published ON user_strategies(is_published) WHERE is_published = TRUE;
