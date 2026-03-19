-- Learning Engine v2: Market regime detection, strategy weight optimization,
-- parameter adaptation, and A/B testing tables.
-- Addresses Issues #1482 and #1475.

-- Market regime snapshots detected by the regime detector.
CREATE TABLE market_regimes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument VARCHAR NOT NULL,
    regime_type VARCHAR NOT NULL,  -- 'trending_up', 'trending_down', 'ranging', 'volatile', 'quiet'
    confidence DECIMAL NOT NULL DEFAULT 0.0,
    indicators JSONB NOT NULL DEFAULT '{}',  -- volatility, trend_strength, volume_ratio, etc.
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_market_regimes_instrument ON market_regimes(instrument);
CREATE INDEX idx_market_regimes_type ON market_regimes(regime_type);
CREATE INDEX idx_market_regimes_started ON market_regimes(started_at);
CREATE INDEX idx_market_regimes_instrument_active ON market_regimes(instrument, ended_at)
    WHERE ended_at IS NULL;

-- Rolling performance metrics per strategy per regime.
CREATE TABLE strategy_regime_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    regime_type VARCHAR NOT NULL,
    instrument VARCHAR NOT NULL,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    trade_count INTEGER NOT NULL DEFAULT 0,
    win_count INTEGER NOT NULL DEFAULT 0,
    total_pnl DECIMAL NOT NULL DEFAULT 0.0,
    avg_pnl_percent DECIMAL,
    sharpe_ratio DECIMAL,
    max_drawdown DECIMAL,
    win_rate DECIMAL,
    avg_hold_duration INTERVAL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_srp_strategy ON strategy_regime_performance(strategy_spec_id);
CREATE INDEX idx_srp_regime ON strategy_regime_performance(regime_type);
CREATE INDEX idx_srp_instrument ON strategy_regime_performance(instrument);
CREATE INDEX idx_srp_composite ON strategy_regime_performance(strategy_spec_id, regime_type, instrument);

-- Dynamic strategy weights based on regime and recent performance.
CREATE TABLE strategy_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    instrument VARCHAR NOT NULL,
    regime_type VARCHAR NOT NULL,
    weight DECIMAL NOT NULL DEFAULT 1.0,
    previous_weight DECIMAL,
    reason TEXT,
    effective_from TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sw_strategy ON strategy_weights(strategy_spec_id);
CREATE INDEX idx_sw_instrument_regime ON strategy_weights(instrument, regime_type);
CREATE INDEX idx_sw_active ON strategy_weights(effective_until)
    WHERE effective_until IS NULL;

-- Parameter adaptations applied to strategies.
CREATE TABLE parameter_adaptations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    instrument VARCHAR NOT NULL,
    regime_type VARCHAR NOT NULL,
    original_parameters JSONB NOT NULL,
    adapted_parameters JSONB NOT NULL,
    adaptation_rules JSONB NOT NULL DEFAULT '{}',  -- which rules triggered this
    status VARCHAR NOT NULL DEFAULT 'active',  -- 'active', 'reverted', 'superseded'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pa_strategy ON parameter_adaptations(strategy_spec_id);
CREATE INDEX idx_pa_instrument_regime ON parameter_adaptations(instrument, regime_type);
CREATE INDEX idx_pa_status ON parameter_adaptations(status);

-- Regime change alerts log.
CREATE TABLE regime_change_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument VARCHAR NOT NULL,
    previous_regime VARCHAR NOT NULL,
    new_regime VARCHAR NOT NULL,
    confidence DECIMAL NOT NULL DEFAULT 0.0,
    favored_strategies JSONB DEFAULT '[]',  -- strategies that perform well in new regime
    unfavored_strategies JSONB DEFAULT '[]',
    alert_metadata JSONB DEFAULT '{}',
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rca_instrument ON regime_change_alerts(instrument);
CREATE INDEX idx_rca_created ON regime_change_alerts(created_at);

-- A/B test experiments for parameter adaptations.
CREATE TABLE ab_test_experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_spec_id UUID NOT NULL REFERENCES strategy_specs(id) ON DELETE CASCADE,
    instrument VARCHAR NOT NULL,
    control_parameters JSONB NOT NULL,
    treatment_parameters JSONB NOT NULL,
    hypothesis TEXT,
    status VARCHAR NOT NULL DEFAULT 'running',  -- 'running', 'completed', 'cancelled'
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ab_strategy ON ab_test_experiments(strategy_spec_id);
CREATE INDEX idx_ab_status ON ab_test_experiments(status);

-- Individual observations within an A/B test.
CREATE TABLE ab_test_observations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES ab_test_experiments(id) ON DELETE CASCADE,
    variant VARCHAR NOT NULL,  -- 'control' or 'treatment'
    pnl_percent DECIMAL,
    pnl_absolute DECIMAL,
    signal_type VARCHAR,
    entry_price DECIMAL,
    exit_price DECIMAL,
    hold_duration INTERVAL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_abo_experiment ON ab_test_observations(experiment_id);
CREATE INDEX idx_abo_variant ON ab_test_observations(variant);

-- Adaptation audit log for dashboard.
CREATE TABLE adaptation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR NOT NULL,  -- 'regime_change', 'weight_update', 'param_adaptation', 'ab_test_result'
    instrument VARCHAR,
    strategy_spec_id UUID REFERENCES strategy_specs(id) ON DELETE SET NULL,
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_al_event_type ON adaptation_log(event_type);
CREATE INDEX idx_al_instrument ON adaptation_log(instrument);
CREATE INDEX idx_al_created ON adaptation_log(created_at);
