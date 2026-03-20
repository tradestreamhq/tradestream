-- Strategy Knowledge Graph: indicator relationships, market condition taxonomy,
-- strategy composition, and performance attribution tables.
-- Enables intelligent strategy recommendation and ensemble composition.

-- Indicator catalog: canonical list of all technical indicators.
CREATE TABLE indicator_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL UNIQUE,           -- e.g. 'RSI', 'MACD', 'SMA', 'EMA', 'BOLLINGER'
    category VARCHAR NOT NULL,              -- 'momentum', 'trend', 'volatility', 'volume', 'oscillator'
    description TEXT,
    default_params JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ic_category ON indicator_catalog(category);

-- Indicator relationships: which indicators complement or conflict with each other.
CREATE TABLE indicator_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator_a UUID NOT NULL REFERENCES indicator_catalog(id) ON DELETE CASCADE,
    indicator_b UUID NOT NULL REFERENCES indicator_catalog(id) ON DELETE CASCADE,
    relationship_type VARCHAR NOT NULL,     -- 'complementary', 'conflicting', 'redundant', 'confirming'
    strength DECIMAL NOT NULL DEFAULT 0.5,  -- 0.0 to 1.0
    reasoning TEXT,                         -- why this relationship exists
    evidence JSONB DEFAULT '{}',            -- correlation data, backtest evidence
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_indicator_pair UNIQUE (indicator_a, indicator_b),
    CONSTRAINT different_indicators CHECK (indicator_a != indicator_b)
);

CREATE INDEX idx_ir_indicator_a ON indicator_relationships(indicator_a);
CREATE INDEX idx_ir_indicator_b ON indicator_relationships(indicator_b);
CREATE INDEX idx_ir_type ON indicator_relationships(relationship_type);

-- Market condition taxonomy: structured classification of market states.
CREATE TABLE market_condition_taxonomy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trend VARCHAR NOT NULL,                 -- 'trending_up', 'trending_down', 'ranging'
    volatility VARCHAR NOT NULL,            -- 'high', 'medium', 'low'
    volume VARCHAR NOT NULL,                -- 'high', 'medium', 'low'
    sentiment VARCHAR NOT NULL DEFAULT 'neutral', -- 'bullish', 'bearish', 'neutral'
    description TEXT,
    typical_duration_hours INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_market_condition UNIQUE (trend, volatility, volume, sentiment)
);

CREATE INDEX idx_mct_trend ON market_condition_taxonomy(trend);
CREATE INDEX idx_mct_volatility ON market_condition_taxonomy(volatility);

-- Strategy-condition performance: how each strategy performs under each market condition.
CREATE TABLE strategy_condition_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    condition_id UUID NOT NULL REFERENCES market_condition_taxonomy(id) ON DELETE CASCADE,
    instrument VARCHAR NOT NULL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL,
    avg_return DECIMAL,
    sharpe_ratio DECIMAL,
    max_drawdown DECIMAL,
    avg_hold_duration INTERVAL,
    last_evaluated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_strategy_condition UNIQUE (strategy_spec_id, condition_id, instrument)
);

CREATE INDEX idx_scp_strategy ON strategy_condition_performance(strategy_spec_id);
CREATE INDEX idx_scp_condition ON strategy_condition_performance(condition_id);
CREATE INDEX idx_scp_instrument ON strategy_condition_performance(instrument);
CREATE INDEX idx_scp_sharpe ON strategy_condition_performance(sharpe_ratio DESC NULLS LAST);

-- Composite strategies: ensemble combinations of multiple strategy specs.
CREATE TABLE composite_strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL UNIQUE,
    description TEXT,
    combination_method VARCHAR NOT NULL,    -- 'majority_vote', 'weighted_average', 'unanimous', 'any'
    min_agreement DECIMAL DEFAULT 0.5,      -- minimum agreement threshold for signals
    created_by VARCHAR NOT NULL DEFAULT 'SYSTEM', -- 'SYSTEM', 'USER', 'LLM_GENERATED'
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cs_active ON composite_strategies(is_active);

-- Components of a composite strategy.
CREATE TABLE composite_strategy_components (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    composite_id UUID NOT NULL REFERENCES composite_strategies(id) ON DELETE CASCADE,
    strategy_spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    weight DECIMAL NOT NULL DEFAULT 1.0,
    role VARCHAR NOT NULL DEFAULT 'signal',  -- 'signal', 'filter', 'confirmation'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_composite_component UNIQUE (composite_id, strategy_spec_id)
);

CREATE INDEX idx_csc_composite ON composite_strategy_components(composite_id);
CREATE INDEX idx_csc_strategy ON composite_strategy_components(strategy_spec_id);

-- Performance attribution for composite strategies.
CREATE TABLE composite_performance_attribution (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    composite_id UUID NOT NULL REFERENCES composite_strategies(id) ON DELETE CASCADE,
    component_spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    instrument VARCHAR NOT NULL,
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    signals_generated INTEGER NOT NULL DEFAULT 0,
    signals_agreed INTEGER NOT NULL DEFAULT 0,      -- signals that aligned with composite decision
    contribution_pnl DECIMAL NOT NULL DEFAULT 0.0,  -- P&L attributed to this component
    contribution_pct DECIMAL,                        -- percentage of total composite P&L
    accuracy DECIMAL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cpa_composite ON composite_performance_attribution(composite_id);
CREATE INDEX idx_cpa_component ON composite_performance_attribution(component_spec_id);
CREATE INDEX idx_cpa_period ON composite_performance_attribution(period_start, period_end);

-- Strategy tags for knowledge graph edges.
CREATE TABLE strategy_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    tag VARCHAR NOT NULL,                   -- e.g. 'mean_reversion', 'trend_following', 'breakout'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_strategy_tag UNIQUE (strategy_spec_id, tag)
);

CREATE INDEX idx_st_strategy ON strategy_tags(strategy_spec_id);
CREATE INDEX idx_st_tag ON strategy_tags(tag);

-- Seed the indicator catalog with common indicators.
INSERT INTO indicator_catalog (name, category, description, default_params) VALUES
    ('RSI', 'momentum', 'Relative Strength Index - measures overbought/oversold conditions', '{"period": 14}'),
    ('MACD', 'momentum', 'Moving Average Convergence Divergence - trend and momentum', '{"fast": 12, "slow": 26, "signal": 9}'),
    ('SMA', 'trend', 'Simple Moving Average - smoothed price trend', '{"period": 20}'),
    ('EMA', 'trend', 'Exponential Moving Average - weighted price trend', '{"period": 20}'),
    ('BOLLINGER', 'volatility', 'Bollinger Bands - volatility envelope around moving average', '{"period": 20, "stddev": 2}'),
    ('ATR', 'volatility', 'Average True Range - measures market volatility', '{"period": 14}'),
    ('STOCHASTIC', 'oscillator', 'Stochastic Oscillator - momentum comparing closing price to range', '{"k_period": 14, "d_period": 3}'),
    ('ADX', 'trend', 'Average Directional Index - trend strength indicator', '{"period": 14}'),
    ('CCI', 'oscillator', 'Commodity Channel Index - identifies cyclical turns', '{"period": 20}'),
    ('OBV', 'volume', 'On-Balance Volume - cumulative volume-based momentum', '{}'),
    ('VWAP', 'volume', 'Volume Weighted Average Price - average price weighted by volume', '{}'),
    ('WILLIAMS_R', 'oscillator', 'Williams %R - overbought/oversold oscillator', '{"period": 14}'),
    ('MFI', 'volume', 'Money Flow Index - volume-weighted RSI', '{"period": 14}'),
    ('ICHIMOKU', 'trend', 'Ichimoku Cloud - multi-component trend system', '{"tenkan": 9, "kijun": 26, "senkou_b": 52}'),
    ('SUPERTREND', 'trend', 'SuperTrend - trend-following overlay indicator', '{"period": 10, "multiplier": 3}'),
    ('CLOSE', 'price', 'Closing price of the instrument', '{}'),
    ('OPEN', 'price', 'Opening price of the instrument', '{}'),
    ('HIGH', 'price', 'High price of the instrument', '{}'),
    ('LOW', 'price', 'Low price of the instrument', '{}');

-- Seed indicator relationships.
INSERT INTO indicator_relationships (indicator_a, indicator_b, relationship_type, strength, reasoning)
SELECT a.id, b.id, 'complementary', 0.8,
    'RSI momentum signals confirmed by MACD trend direction provide higher accuracy entries'
FROM indicator_catalog a, indicator_catalog b
WHERE a.name = 'RSI' AND b.name = 'MACD';

INSERT INTO indicator_relationships (indicator_a, indicator_b, relationship_type, strength, reasoning)
SELECT a.id, b.id, 'redundant', 0.7,
    'SMA and EMA both measure trend via moving averages; using both adds little new information'
FROM indicator_catalog a, indicator_catalog b
WHERE a.name = 'SMA' AND b.name = 'EMA';

INSERT INTO indicator_relationships (indicator_a, indicator_b, relationship_type, strength, reasoning)
SELECT a.id, b.id, 'complementary', 0.85,
    'Bollinger Band squeezes with RSI divergence identify high-probability reversal setups'
FROM indicator_catalog a, indicator_catalog b
WHERE a.name = 'BOLLINGER' AND b.name = 'RSI';

INSERT INTO indicator_relationships (indicator_a, indicator_b, relationship_type, strength, reasoning)
SELECT a.id, b.id, 'complementary', 0.75,
    'ATR provides volatility context for position sizing when combined with trend signals from ADX'
FROM indicator_catalog a, indicator_catalog b
WHERE a.name = 'ATR' AND b.name = 'ADX';

INSERT INTO indicator_relationships (indicator_a, indicator_b, relationship_type, strength, reasoning)
SELECT a.id, b.id, 'confirming', 0.7,
    'OBV volume confirmation strengthens MACD crossover signals'
FROM indicator_catalog a, indicator_catalog b
WHERE a.name = 'OBV' AND b.name = 'MACD';

INSERT INTO indicator_relationships (indicator_a, indicator_b, relationship_type, strength, reasoning)
SELECT a.id, b.id, 'redundant', 0.65,
    'RSI and Stochastic both measure momentum oscillation; combining provides marginal benefit'
FROM indicator_catalog a, indicator_catalog b
WHERE a.name = 'RSI' AND b.name = 'STOCHASTIC';

INSERT INTO indicator_relationships (indicator_a, indicator_b, relationship_type, strength, reasoning)
SELECT a.id, b.id, 'complementary', 0.9,
    'ADX trend strength filtering with MACD directional signals produces strong trend-following setups'
FROM indicator_catalog a, indicator_catalog b
WHERE a.name = 'ADX' AND b.name = 'MACD';

INSERT INTO indicator_relationships (indicator_a, indicator_b, relationship_type, strength, reasoning)
SELECT a.id, b.id, 'complementary', 0.8,
    'MFI volume-weighted momentum with Bollinger Band mean reversion identifies volume-confirmed entries'
FROM indicator_catalog a, indicator_catalog b
WHERE a.name = 'MFI' AND b.name = 'BOLLINGER';

-- Seed market condition taxonomy with all combinations.
INSERT INTO market_condition_taxonomy (trend, volatility, volume, sentiment, description) VALUES
    ('trending_up', 'high', 'high', 'bullish', 'Strong uptrend with high volatility and volume - momentum strategies excel'),
    ('trending_up', 'high', 'medium', 'bullish', 'Uptrend with high volatility - trend following with wide stops'),
    ('trending_up', 'medium', 'high', 'bullish', 'Steady uptrend with strong volume - ideal for trend following'),
    ('trending_up', 'medium', 'medium', 'bullish', 'Moderate uptrend - balanced approach works'),
    ('trending_up', 'low', 'medium', 'bullish', 'Calm uptrend - tight trailing stops effective'),
    ('trending_up', 'low', 'low', 'neutral', 'Weak uptrend with low conviction - caution advised'),
    ('trending_down', 'high', 'high', 'bearish', 'Strong downtrend with panic selling - reversal strategies risky'),
    ('trending_down', 'high', 'medium', 'bearish', 'Volatile downtrend - short-biased momentum works'),
    ('trending_down', 'medium', 'high', 'bearish', 'Steady downtrend with volume - trend following short side'),
    ('trending_down', 'medium', 'medium', 'bearish', 'Moderate downtrend - defensive positioning'),
    ('trending_down', 'low', 'medium', 'bearish', 'Slow grind down - mean reversion can work at extremes'),
    ('trending_down', 'low', 'low', 'neutral', 'Low-energy decline - watch for base formation'),
    ('ranging', 'high', 'high', 'neutral', 'Choppy range with volume - mean reversion with wide bands'),
    ('ranging', 'high', 'medium', 'neutral', 'Volatile range - oscillator strategies with confirmation'),
    ('ranging', 'medium', 'high', 'neutral', 'Active range trading - support/resistance plays'),
    ('ranging', 'medium', 'medium', 'neutral', 'Classic range - RSI and Bollinger Band strategies ideal'),
    ('ranging', 'low', 'medium', 'neutral', 'Tight range - breakout preparation, low opportunity'),
    ('ranging', 'low', 'low', 'neutral', 'Consolidation phase - wait for breakout or use tight ranges');
