-- Signal reasoning: stores human-readable explanations for why each trading signal was produced.
-- Captures indicator values, market context, historical patterns, and risk factors at signal time.

CREATE TABLE IF NOT EXISTS signal_reasoning (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    signal_type VARCHAR(10) NOT NULL,  -- BUY, SELL

    -- Contributing factors (JSONB array of indicator snapshots)
    contributing_factors JSONB NOT NULL DEFAULT '[]',

    -- Indicator values at signal time
    indicator_values JSONB NOT NULL DEFAULT '{}',

    -- Market context at signal time
    market_context JSONB NOT NULL DEFAULT '{}',

    -- Confidence breakdown by component
    confidence_breakdown JSONB NOT NULL DEFAULT '{}',

    -- Generated natural language explanation
    explanation_text TEXT NOT NULL,

    -- Historical pattern context
    historical_context TEXT,

    -- Risk factors and warnings
    risk_factors JSONB NOT NULL DEFAULT '[]',

    -- Validation level at time of signal
    validation_level VARCHAR(20) NOT NULL DEFAULT 'candidate',

    -- Expected return with confidence interval
    expected_return DECIMAL(8,4),
    expected_return_ci_lower DECIMAL(8,4),
    expected_return_ci_upper DECIMAL(8,4),
    predicted_timeframe_hours INTEGER,

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signal_reasoning_signal_id ON signal_reasoning(signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_reasoning_strategy ON signal_reasoning(strategy_name);
CREATE INDEX IF NOT EXISTS idx_signal_reasoning_symbol ON signal_reasoning(symbol);
CREATE INDEX IF NOT EXISTS idx_signal_reasoning_created ON signal_reasoning(created_at DESC);
